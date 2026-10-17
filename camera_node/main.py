import argparse
import logging
import os
import sys
import time
from typing import Optional
import cv2

from camera_node.config import get_edge_config
from camera_node.simulator import MockDetectionStream, generate_synthetic_retail_clip
from camera_node.trigger_engine import EdgeTriggerEngine
from camera_node.uploader import ClipUploader
from camera_node.zones import RetailZone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [camera_node]: %(message)s",
)
logger = logging.getLogger("aisle.camera_node")


def run_node(
    source: str = "synthetic",
    dwell_threshold: float = 3.0,
    backend_url: str = "http://localhost:8000",
    direct_gcs: bool = False,
    headless: bool = True,
    max_frames: Optional[int] = None,
) -> None:
    """Runs the camera node edge processing loop."""
    config = get_edge_config()
    config.dwell_threshold_seconds = dwell_threshold
    config.backend_api_url = backend_url
    config.use_direct_gcs_upload = direct_gcs
    config.headless = headless

    # Generate or resolve video source
    if source == "synthetic" or not os.path.exists(source):
        synthetic_path = "sample_retail_interaction.mp4"
        if not os.path.exists(synthetic_path):
            generate_synthetic_retail_clip(output_path=synthetic_path, duration_seconds=8, fps=20)
        source = synthetic_path

    logger.info("Opening video source: %s", source)
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        logger.error("Could not open video source: %s", source)
        sys.exit(1)

    fps = cap.get(cv2.CAP_PROP_FPS) or 20.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1280
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 720
    total_video_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1000000
    limit_frames = max_frames if max_frames is not None else total_video_frames
    logger.info("Feed resolution: %dx%d @ %.1f FPS (Processing up to %d frames)", width, height, fps, limit_frames)

    # Initialize zones
    zones = [
        RetailZone(zone_id=z_id, polygon=poly)
        for z_id, poly in config.zones.items()
    ]

    uploader = ClipUploader(config)
    engine = EdgeTriggerEngine(config=config, zones=zones, uploader=uploader, fps=fps)

    yolo_model = None
    mock_detector = None
    if source != "synthetic":
        try:
            from ultralytics import YOLO
            logger.info("Loading YOLOv8 person tracker for real video stream...")
            yolo_model = YOLO("yolov8n.pt")
        except Exception as e:
            logger.warning("Could not load YOLOv8 (%s). Falling back to mock detector.", e)
            mock_detector = MockDetectionStream(fps=fps)
    else:
        mock_detector = MockDetectionStream(fps=fps)

    frame_idx = 0
    start_sim_time = time.time()

    try:
        while cap.isOpened() and frame_idx < limit_frames:
            ret, frame = cap.read()
            if not ret:
                break

            frame_idx += 1
            # Current simulated timestamp
            sim_time = start_sim_time + (frame_idx / fps)

            # Retrieve detections
            detections = []
            if yolo_model is not None:
                try:
                    results = yolo_model.track(frame, classes=[0], persist=True, verbose=False)[0]
                    if results.boxes is not None and len(results.boxes) > 0:
                        boxes = results.boxes.xywh.cpu().numpy()
                        if results.boxes.id is not None:
                            track_ids = results.boxes.id.int().cpu().numpy()
                        else:
                            import numpy as np
                            track_ids = np.ones(len(boxes), dtype=int)
                        for box, tid in zip(boxes, track_ids):
                            cx, cy, bw, bh = box
                            x = int(cx - bw / 2)
                            y = int(cy - bh / 2)
                            detections.append((int(tid), (x, y, int(bw), int(bh))))
                except Exception as track_err:
                    logger.debug("Tracking frame error: %s", track_err)
            elif mock_detector is not None:
                detections = mock_detector.get_detections_for_frame(frame_idx)

            # Process frame through edge trigger engine
            annotated_frame = engine.process_frame(
                frame=frame,
                detections=detections,
                current_time=sim_time,
            )

            if not config.headless:
                cv2.imshow("AIsle Camera Node - Edge Dwell Monitor", annotated_frame)
                if cv2.waitKey(int(1000 / fps)) & 0xFF == ord("q"):
                    break

        engine.flush_pending()
        wall_clock_duration = max(0.001, time.time() - start_sim_time)
        eff_fps = frame_idx / wall_clock_duration
        feed_duration_s = frame_idx / fps
        total_clips_duration_s = getattr(engine, "total_extracted_seconds", 0.0)
        bw_savings = max(0.0, (1.0 - (total_clips_duration_s / max(0.1, feed_duration_s))) * 100.0)

        logger.info("Finished processing video feed. Processed %d frames.", frame_idx)

        print("\n" + "=" * 65)
        print("📊 CAMERA NODE EDGE BENCHMARK SUMMARY")
        print("=" * 65)
        print(f"🎬 Feed Processed:      {frame_idx} frames ({feed_duration_s:.1f}s video duration)")
        print(f"⏱️ Edge Compute Speed:  {eff_fps:.1f} FPS (Wall time: {wall_clock_duration:.1f}s)")
        print(f"📦 Clips Dispatched:    {getattr(engine, 'clips_dispatched_count', 0)} interaction clips ({total_clips_duration_s:.1f}s total)")
        print(f"💰 Cloud Egress Saved:  {bw_savings:.1f}% bandwidth/cost reduction vs 24/7 streaming")
        print("=" * 65 + "\n")

    finally:
        cap.release()
        if not config.headless:
            cv2.destroyAllWindows()


def main():
    parser = argparse.ArgumentParser(description="AIsle Edge Camera Node - Zone Dwell Trigger")
    parser.add_argument(
        "--source",
        default="synthetic",
        help="Path to MP4 video file, camera index, or 'synthetic'",
    )
    parser.add_argument(
        "--dwell",
        type=float,
        default=3.0,
        help="Dwell duration threshold in seconds before triggering (default: 3.0)",
    )
    parser.add_argument(
        "--backend",
        default="http://localhost:8000",
        help="Backend API URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--direct-gcs",
        action="store_true",
        help="Upload directly to GCS instead of backend multipart HTTP",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=True,
        help="Run without GUI window",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=None,
        help="Maximum frames to process (useful for quick testing, default: all frames)",
    )
    parser.add_argument(
        "--generate-sample",
        action="store_true",
        help="Generate synthetic retail sample MP4 and exit",
    )

    args = parser.parse_args()

    if args.generate_sample:
        out = generate_synthetic_retail_clip("sample_retail_interaction.mp4")
        print(f"Sample clip generated at: {out}")
        return

    run_node(
        source=args.source,
        dwell_threshold=args.dwell,
        backend_url=args.backend,
        direct_gcs=args.direct_gcs,
        headless=args.headless,
        max_frames=args.max_frames,
    )


if __name__ == "__main__":
    main()
