import logging
import math
from pathlib import Path
from typing import List, Tuple
import cv2
import numpy as np

logger = logging.getLogger(__name__)


def generate_synthetic_retail_clip(
    output_path: str = "sample_retail_interaction.mp4",
    duration_seconds: int = 8,
    fps: int = 20,
    width: int = 1280,
    height: int = 720,
) -> str:
    """
    Synthesizes a realistic retail store overhead/shelf camera clip:
    - Renders store shelving units, aisle walkways, and products.
    - Animates a customer walking up to the shelf, stopping to examine a product,
      holding it up, and returning it to the shelf.
    """
    total_frames = duration_seconds * fps
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    logger.info("Generating synthetic retail interaction clip: %s (%ds, %d fps)", output_path, duration_seconds, fps)

    for frame_idx in range(total_frames):
        # Base background: store floor
        frame = np.full((height, width, 3), (235, 235, 235), dtype=np.uint8)

        # Draw tile grid floor lines
        for y in range(0, height, 80):
            cv2.line(frame, (0, y), (width, y), (215, 215, 215), 1)
        for x in range(0, width, 80):
            cv2.line(frame, (x, 0), (x, height), (215, 215, 215), 1)

        # Draw Shelf Unit (Right side)
        cv2.rectangle(frame, (700, 80), (1200, 640), (80, 70, 60), -1)
        cv2.rectangle(frame, (700, 80), (1200, 640), (40, 35, 30), 3)

        # Draw Shelf Tiers
        for tier_y in [180, 320, 460, 600]:
            cv2.line(frame, (700, tier_y), (1200, tier_y), (120, 110, 100), 4)

        # Draw Products on shelves
        for px in range(730, 1180, 50):
            cv2.rectangle(frame, (px, 120), (px + 30, 178), (40, 140, 240), -1)  # Top: orange boxes
            cv2.rectangle(frame, (px, 260), (px + 30, 318), (200, 120, 30), -1)  # Eye-level: blue bottles
            cv2.rectangle(frame, (px, 400), (px + 30, 458), (50, 180, 60), -1)   # Mid: green packages
            cv2.rectangle(frame, (px, 540), (px + 30, 598), (140, 40, 140), -1)  # Bottom: purple jars

        # Shelf Labeling
        cv2.putText(frame, "SHELF ZONE: AISLE 3 (HEALTH & BEAUTY)", (720, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (50, 50, 50), 2)
        cv2.putText(frame, "EYE-LEVEL PROMO DISPLAY", (720, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)

        # Shopper trajectory:
        # 0s - 2s: walks from left (x=100) towards shelf (x=620)
        # 2s - 6s: stops at shelf (dwells 4s), reaches arm out, picks up blue bottle, inspects, returns
        # 6s - 8s: walks downward/away
        progress = frame_idx / total_frames

        if progress < 0.25:  # Walking in
            t = progress / 0.25
            cx = int(100 + t * 520)
            cy = int(320 + math.sin(t * 8) * 15)
            action_text = "Approaching Shelf..."
            arm_reach = False
        elif progress < 0.75:  # Dwelling & Interacting
            cx = 620
            cy = 320
            t_dwell = (progress - 0.25) / 0.50
            if t_dwell < 0.4:
                action_text = f"Dwelling & Browsing (Dwell: {t_dwell*4:.1f}s)..."
                arm_reach = False
            elif t_dwell < 0.8:
                action_text = "EXAMINING ITEM: Picked up Blue Bottle"
                arm_reach = True
            else:
                action_text = "RETURNING ITEM to shelf"
                arm_reach = True
        else:  # Walking away
            t_out = (progress - 0.75) / 0.25
            cx = int(620 - t_out * 300)
            cy = int(320 + t_out * 200)
            action_text = "Exiting Zone..."
            arm_reach = False

        # Draw Shopper (overhead view: head circle + shoulder oval)
        # Shadow
        cv2.ellipse(frame, (cx + 5, cy + 8), (45, 25), 0, 0, 360, (190, 190, 190), -1)
        # Shoulders / Torso
        cv2.ellipse(frame, (cx, cy), (42, 22), 0, 0, 360, (60, 80, 120), -1)
        # Head
        cv2.circle(frame, (cx, cy), 18, (210, 180, 150), -1)
        # Hair
        cv2.ellipse(frame, (cx - 2, cy - 3), (17, 14), 0, 0, 360, (40, 30, 20), -1)

        # Arm reaching towards shelf during interaction
        if arm_reach:
            cv2.line(frame, (cx + 35, cy), (cx + 100, cy - 20), (210, 180, 150), 8)
            # Picked up item in hand
            cv2.rectangle(frame, (cx + 90, cy - 35), (cx + 115, cy - 5), (200, 120, 30), -1)

        # Overlay Camera Info Banner
        cv2.rectangle(frame, (0, 0), (width, 40), (30, 30, 30), -1)
        cv2.putText(
            frame,
            f"CAM 01 - AISLE 3 | FRAME {frame_idx:04d}/{total_frames:04d} | ACTION: {action_text}",
            (20, 26),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 255, 200),
            1,
            cv2.LINE_AA,
        )

        out.write(frame)

    out.release()
    logger.info("Sample video generated successfully at %s", output_path)
    return str(Path(output_path).resolve())


class MockDetectionStream:
    """Simulates an object detection stream with bounding boxes for testing."""

    def __init__(self, fps: float = 20.0):
        self.fps = fps
        self.frame_count = 0

    def get_detections_for_frame(self, frame_idx: int) -> List[Tuple[int, Tuple[int, int, int, int]]]:
        """
        Returns bounding boxes [(track_id, (x, y, w, h))] for frame_idx.
        Simulates Track 1 entering endcap_promo_A and dwelling.
        """
        # Time in seconds
        t = frame_idx / self.fps

        detections = []
        # Track 1: Customer lingering at shelf
        if 0.5 <= t <= 7.0:
            if t < 2.0:
                # Walking to zone
                x = int(150 + (t - 0.5) * 200)
                y = int(250)
            elif t < 6.0:
                # Stationary in zone (dwelling from t=2.0 to t=6.0 -> 4.0s dwell)
                x = 450
                y = 250
            else:
                # Leaving zone
                x = int(450 - (t - 6.0) * 150)
                y = int(250 + (t - 6.0) * 100)
            detections.append((1, (x, y, 80, 140)))

        return detections
