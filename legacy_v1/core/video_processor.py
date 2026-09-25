import numpy as np
from ultralytics import YOLO
import supervision as sv

class StoreTracker:
    def __init__(self, model_path, config_path, zones, zone_names, fps):
        self.model = YOLO(model_path)
        self.config_path = config_path
        self.zones = zones
        self.zone_names = zone_names
        self.fps = fps
        self.dwell_data = {}
        
        # Setup Annotators
        colors = sv.ColorPalette.DEFAULT
        self.box_annotator = sv.BoxAnnotator(thickness=2)
        self.label_annotator = sv.LabelAnnotator(text_thickness=1, text_scale=0.5)
        self.zone_annotators = [
            sv.PolygonZoneAnnotator(zone=z, color=colors.by_idx(i), thickness=2, text_thickness=1, text_scale=0.5)
            for i, z in enumerate(self.zones)
        ]

    def process_frame(self, frame: np.ndarray, frame_idx: int) -> np.ndarray:
        results = self.model.track(frame, persist=True, tracker=self.config_path, imgsz=1280, verbose=False)[0]
        
        if results.boxes is None or results.boxes.id is None:
            for za in self.zone_annotators:
                frame = za.annotate(scene=frame)
            return frame
            
        detections = sv.Detections.from_ultralytics(results)
        detections = detections[detections.class_id == 0]
        labels = []
        
        for i, track_id in enumerate(detections.tracker_id):
            current_zone = None
            for zone_idx, zone in enumerate(self.zones):
                if zone.trigger(detections=detections)[i]: 
                    current_zone = zone_idx
                    break
                    
            if track_id not in self.dwell_data:
                self.dwell_data[track_id] = {"current_zone": current_zone, "frames": 0, "history": []}
                
            record = self.dwell_data[track_id]
            
            if current_zone is not None:
                if record["current_zone"] == current_zone:
                    record["frames"] += 1
                else:
                    if record["current_zone"] is not None:
                        record["history"].append({
                            "zone": record["current_zone"],
                            "seconds": round(record["frames"] / self.fps, 1)
                        })
                    record["current_zone"] = current_zone
                    record["frames"] = 1
                    
            if record["current_zone"] is not None:
                labels.append(f"ID:{track_id} | Zone {current_zone} | {record['frames'] / self.fps:.1f}s")
            else:
                labels.append(f"ID:{track_id} | Transitioning")
                
        frame = self.box_annotator.annotate(scene=frame, detections=detections)
        frame = self.label_annotator.annotate(scene=frame, detections=detections, labels=labels)
        
        for i, za in enumerate(self.zone_annotators):
            frame = za.annotate(scene=frame, label=f"{self.zone_names[i]}: {self.zones[i].current_count}")
            
        return frame