from collections import deque
from datetime import datetime, timezone
import logging
import os
from pathlib import Path
import time
from typing import Dict, List, Optional, Tuple
import cv2
import numpy as np

from camera_node.config import EdgeConfig
from camera_node.uploader import ClipUploader
from camera_node.zones import RetailZone

logger = logging.getLogger(__name__)


class DwellTracker:
    """Tracks per-person dwell duration within monitored zones with grace period smoothing."""

    def __init__(self, track_id: int):
        self.track_id = track_id
        self.current_zone: Optional[str] = None
        self.entry_time: float = 0.0
        self.last_seen_time: float = 0.0
        self.dwell_seconds: float = 0.0
        self.triggered_zones: set = set()

    def update_zone(self, zone_id: Optional[str], current_time: float, grace_seconds: float = 1.2) -> Tuple[float, bool]:
        """
        Updates zone presence with hysteresis to handle temporary occlusions or bounding box jitter.
        """
        if zone_id is not None:
            if self.current_zone is None:
                # Fresh entry into zone
                self.current_zone = zone_id
                self.entry_time = current_time
                self.last_seen_time = current_time
                self.dwell_seconds = 0.0
                return 0.0, True
            elif self.current_zone != zone_id:
                # Moved to a different zone
                self.triggered_zones.discard(self.current_zone)
                self.current_zone = zone_id
                self.entry_time = current_time
                self.last_seen_time = current_time
                self.dwell_seconds = 0.0
                return 0.0, True
            else:
                # Continuing in current zone
                self.last_seen_time = current_time
                self.dwell_seconds = current_time - self.entry_time
                return self.dwell_seconds, False
        else:
            if self.current_zone is not None:
                if (current_time - self.last_seen_time) > grace_seconds:
                    # Genuinely departed after grace period: reset so they can trigger if they visit again
                    self.triggered_zones.discard(self.current_zone)
                    self.current_zone = None
                    self.dwell_seconds = 0.0
                    return 0.0, True
                else:
                    # Within grace period, keep accumulating dwell
                    self.dwell_seconds = self.last_seen_time - self.entry_time
                    return self.dwell_seconds, False
            return 0.0, False


class EdgeTriggerEngine:
    """
    Monitors person bounding boxes inside defined retail zones,
    buffers video frames, and extracts/dispatches video clips when dwell exceeds threshold.
    """

    def __init__(
        self,
        config: EdgeConfig,
        zones: List[RetailZone],
        uploader: Optional[ClipUploader] = None,
        fps: float = 20.0,
    ) -> None:
        self.config = config
        self.zones = zones
        self.uploader = uploader or ClipUploader(config)
        self.fps = fps
        self.buffer_size = int(self.config.buffer_seconds * self.fps)
        self.frame_buffer: deque = deque(maxlen=self.buffer_size)

        self.trackers: Dict[int, DwellTracker] = {}
        self.pending_captures: List[Dict[str, Any]] = []
        self.total_extracted_seconds: float = 0.0
        self.clips_dispatched_count: int = 0
        self.out_dir = Path(self.config.output_clips_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)

    def process_frame(
        self,
        frame: np.ndarray,
        detections: List[Tuple[int, Tuple[int, int, int, int]]],
        current_time: Optional[float] = None,
    ) -> np.ndarray:
        """
        Processes a single frame:
        - detections: list of (track_id, (x, y, w, h))
        - returns annotated frame
        """
        now = current_time if current_time is not None else time.time()
        self.frame_buffer.append(frame.copy())
        annotated_frame = frame.copy()

        # Update any pending in-flight clip captures with the new frame
        completed_captures = []
        for cap in self.pending_captures:
            cap["frames"].append(frame.copy())
            cap["remaining_post_frames"] -= 1
            if cap["remaining_post_frames"] <= 0:
                completed_captures.append(cap)

        for cap in completed_captures:
            self.pending_captures.remove(cap)
            self._save_and_dispatch_frames(
                frames=cap["frames"],
                track_id=cap["track_id"],
                zone_id=cap["zone_id"],
                dwell_time=cap["dwell_time"],
            )

        # Draw zones
        active_zones = set()

        seen_track_ids = set()
        for track_id, (x, y, w, h) in detections:
            seen_track_ids.add(track_id)
            # Anchor points: centroid (ideal for overhead cameras) and bottom-center (ideal for angled cameras)
            centroid = (x + w / 2, y + h / 2)
            bottom_center = (x + w / 2, y + h)

            # Determine which zone contains anchor
            detected_zone_id: Optional[str] = None
            for zone in self.zones:
                if zone.contains_point(centroid) or zone.contains_point(bottom_center):
                    detected_zone_id = zone.zone_id
                    active_zones.add(zone.zone_id)
                    break

            if track_id not in self.trackers:
                self.trackers[track_id] = DwellTracker(track_id)

            tracker = self.trackers[track_id]
            dwell_time, _ = tracker.update_zone(detected_zone_id, now)

            # Draw bbox and label
            cv2.rectangle(annotated_frame, (x, y), (x + w, y + h), (255, 165, 0), 2)
            label = f"ID {track_id}"
            if detected_zone_id:
                label += f" | {detected_zone_id} ({dwell_time:.1f}s)"
            cv2.putText(
                annotated_frame,
                label,
                (x, max(20, y - 10)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 0),
                1,
            )

            # Check if trigger condition is met (> threshold seconds and not yet triggered for this zone visit)
            if (
                detected_zone_id
                and dwell_time >= self.config.dwell_threshold_seconds
                and detected_zone_id not in tracker.triggered_zones
            ):
                post_sec = getattr(self.config, "post_trigger_seconds", 5.0)
                logger.info(
                    "TRIGGER ACTIVATED: Track %d dwelled for %.2fs in %s. Recording interaction (+%.1fs follow-through)...",
                    track_id,
                    dwell_time,
                    detected_zone_id,
                    post_sec,
                )
                tracker.triggered_zones.add(detected_zone_id)
                post_frames = int(post_sec * self.fps)
                self.pending_captures.append({
                    "track_id": track_id,
                    "zone_id": detected_zone_id,
                    "dwell_time": dwell_time,
                    "frames": list(self.frame_buffer),
                    "remaining_post_frames": post_frames,
                })

        # Update trackers for any tracks absent in this frame
        for tid, trk in list(self.trackers.items()):
            if tid not in seen_track_ids:
                trk.update_zone(None, now)

        # Draw retail zones
        for zone in self.zones:
            zone.draw(annotated_frame, active=zone.zone_id in active_zones)

        return annotated_frame

    def flush_pending(self) -> None:
        """Flushes any in-progress captures when video stream ends."""
        for cap in list(self.pending_captures):
            self.pending_captures.remove(cap)
            self._save_and_dispatch_frames(
                frames=cap["frames"],
                track_id=cap["track_id"],
                zone_id=cap["zone_id"],
                dwell_time=cap["dwell_time"],
            )

    def _save_and_dispatch_frames(
        self, frames: List[np.ndarray], track_id: int, zone_id: str, dwell_time: float
    ) -> Optional[str]:
        """Slices buffered and follow-through frames into an MP4 and triggers upload."""
        if not frames:
            logger.warning("Frame buffer is empty. Cannot extract clip.")
            return None

        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        clip_name = f"clip_{zone_id}_{timestamp_str}_id{track_id}.mp4"
        clip_path = str(self.out_dir / clip_name)

        first_frame = frames[0]
        h, w = first_frame.shape[:2]
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(clip_path, fourcc, self.fps, (w, h))

        try:
            for buf_frame in frames:
                writer.write(buf_frame)
            writer.release()
            logger.info("Successfully extracted complete interaction clip (%d frames, %.1fs) to: %s", len(frames), len(frames) / self.fps, clip_path)

            self.total_extracted_seconds += (len(frames) / self.fps)
            self.clips_dispatched_count += 1

            # Dispatch asynchronously or synchronously
            self.uploader.dispatch_clip(
                clip_path=clip_path,
                zone_id=zone_id,
                dwell_time_seconds=dwell_time,
            )
            return clip_path
        except Exception as e:
            logger.error("Failed to write video clip (%s)", e)
            if writer:
                writer.release()
            return None
