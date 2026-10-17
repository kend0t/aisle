from typing import List, Tuple
import cv2
import numpy as np


class RetailZone:
    """Represents a monitored shelf or promotional polygon zone."""

    def __init__(self, zone_id: str, polygon: List[Tuple[int, int]], color=(0, 255, 0)):
        self.zone_id = zone_id
        self.polygon = np.array(polygon, dtype=np.int32)
        self.color = color

    def contains_point(self, point: Tuple[float, float]) -> bool:
        """Tests whether a point (x, y) falls inside this polygon zone."""
        # cv2.pointPolygonTest returns positive if inside, 0 on edge, negative if outside
        dist = cv2.pointPolygonTest(self.polygon, (float(point[0]), float(point[1])), False)
        return dist >= 0

    def draw(self, frame: np.ndarray, active: bool = False, label: str = "") -> np.ndarray:
        """Renders polygon boundary and label on the frame."""
        draw_color = (0, 0, 255) if active else self.color
        cv2.polylines(frame, [self.polygon], isClosed=True, color=draw_color, thickness=2)

        # Centroid for label
        moments = cv2.moments(self.polygon)
        if moments["m00"] != 0:
            cx = int(moments["m10"] / moments["m00"])
            cy = int(moments["m01"] / moments["m00"])
        else:
            cx, cy = self.polygon[0]

        text = f"{self.zone_id} {label}".strip()
        cv2.putText(
            frame,
            text,
            (cx - 50, cy),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
        return frame
