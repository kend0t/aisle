import supervision as sv
from config.store_zones import get_store_zones
from core.video_processor import StoreTracker
from core.analytics import generate_reports
from evaluation.evaluation import calculate_metrics

def run_pipeline():
    # 1. Configuration Paths
    video_source = "data/store_video.mp4"
    video_output = "output/output.mp4"
    csv_output = "output/system_output.csv"
    ground_truth_path = "evaluation/ground_truth.csv"
    eval_output_path = "evaluation/evaluation_metrics.csv"
    tracker_config = "config/custom_botsort.yaml"
    
    # 2. Initialize Setup
    zones, zone_names = get_store_zones()
    video_info = sv.VideoInfo.from_video_path(video_source)
    
    tracker = StoreTracker(
        model_path='yolov8m.pt',
        config_path=tracker_config,
        zones=zones,
        zone_names=zone_names,
        fps=video_info.fps
    )
    
    # 3. Process Video
    print("Starting video processing...")
    sv.process_video(
        source_path=video_source,
        target_path=video_output,
        callback=tracker.process_frame
    )
    
    # 4. Generate Reports
    generate_reports(tracker.dwell_data, zone_names, video_info.fps, csv_output)
    
    # 5. Automated Evaluation
    if os.path.exists(ground_truth_path):
        print("\nGround truth found. Starting automated evaluation...")
        calculate_metrics(csv_output, ground_truth_path, eval_output_path)
    else:
        print(f"\nEvaluation skipped: {ground_truth_path} not found.")

if __name__ == "__main__":
    run_pipeline()