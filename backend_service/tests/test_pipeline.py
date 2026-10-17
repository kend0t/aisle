import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend_service.main import app
from camera_node.simulator import generate_synthetic_retail_clip

client = TestClient(app)


def test_health_check():
    """Verify backend health check returns 200 OK and expected keys."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "aisle-backend"


def test_mock_trigger_endpoint():
    """Test rapid simulation trigger."""
    response = client.post("/api/v1/events/mock-trigger?zone_id=endcap_promo_A&dwell_time=9")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    event = data["event"]
    assert event["zone_id"] == "endcap_promo_A"
    assert event["zone_dwell_time_seconds"] == 9
    assert "behavioral_summary" in event


def test_clip_upload_and_analysis_pipeline(tmp_path: Path):
    """Test full upload, video processing, and persistence pipeline."""
    clip_path = tmp_path / "test_interaction.mp4"
    generate_synthetic_retail_clip(output_path=str(clip_path), duration_seconds=3, fps=15)

    assert os.path.exists(clip_path)

    with open(clip_path, "rb") as f:
        response = client.post(
            "/api/v1/events/upload-and-process",
            files={"file": ("test_interaction.mp4", f, "video/mp4")},
            data={"zone_id": "aisle_3_shelf_top", "estimated_dwell_time_seconds": "5"},
        )

    assert response.status_code == 201
    result = response.json()
    assert result["status"] == "success"
    event = result["event"]
    assert event["zone_id"] == "aisle_3_shelf_top"
    assert event["zone_dwell_time_seconds"] == 5
    assert event["interaction_type"] in ["passed_by", "browsed", "examined", "compared"]
    assert event["conversion_outcome"] in ["taken", "returned", "none"]
    assert len(event["behavioral_summary"]) > 0


def test_events_query_and_analytics_summary():
    """Verify events can be listed and analytics summary aggregates metrics."""
    # List events
    res_list = client.get("/api/v1/events")
    assert res_list.status_code == 200
    events = res_list.json()
    assert len(events) >= 1

    # Analytics summary
    res_summary = client.get("/api/v1/analytics/summary")
    assert res_summary.status_code == 200
    summary = res_summary.json()
    assert summary["total_interactions"] >= 1
    assert "conversion_rate" in summary
    assert "abandonment_rate" in summary
    assert "average_dwell_time_seconds" in summary
