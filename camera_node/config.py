import os
from dataclasses import dataclass, field
from typing import Dict, List, Tuple
from dotenv import load_dotenv

load_dotenv()


@dataclass
class EdgeConfig:
    """Configuration for Edge Camera Node & Interaction Detection."""

    backend_api_url: str = os.getenv("BACKEND_API_URL", "http://localhost:8000")
    use_direct_gcs_upload: bool = os.getenv("USE_DIRECT_GCS_UPLOAD", "false").lower() == "true"
    gcp_project_id: str = os.getenv("GCP_PROJECT_ID", "mock-gcp-project")
    gcs_bucket_name: str = os.getenv("GCS_BUCKET_NAME", "aisle-interaction-clips")
    google_application_credentials: str = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")

    dwell_threshold_seconds: float = float(os.getenv("DWELL_THRESHOLD_SECONDS", "3.0"))
    buffer_seconds: float = float(os.getenv("BUFFER_SECONDS", "6.0"))
    post_trigger_seconds: float = float(os.getenv("POST_TRIGGER_SECONDS", "5.0"))
    camera_id: str = os.getenv("CAMERA_ID", "cam_aisle_01")
    output_clips_dir: str = os.getenv("OUTPUT_CLIPS_DIR", "staged_clips")
    headless: bool = os.getenv("HEADLESS", "true").lower() == "true"

    # Default monitored retail zones (polygon coordinates [x, y] in pixel space)
    # Configured for MERL Shopping layout (Left Bay: Cereal, Right Bay: Snacks)
    zones: Dict[str, List[Tuple[int, int]]] = field(
        default_factory=lambda: {
            "left_bay_cereal": [(180, 250), (550, 250), (550, 520), (180, 520)],
            "right_bay_snacks": [(550, 250), (890, 250), (890, 520), (550, 520)],
        }
    )


def get_edge_config() -> EdgeConfig:
    return EdgeConfig()
