import logging
import os
import tempfile
import time
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
import io

from backend_service.db.firestore_client import FirestoreRepository
from backend_service.models.interaction_event import (
    ConversionOutcome,
    InteractionEvent,
    InteractionType,
    ProcessClipRequest,
    ProcessClipResponse,
)
from backend_service.services.gemini_analyzer import GeminiAnalyzerService
from backend_service.services.storage_service import StorageService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Events & Analytics"])

# Dependency singletons
storage_service = StorageService()
gemini_analyzer = GeminiAnalyzerService(storage_service=storage_service)
firestore_repo = FirestoreRepository()


@router.post(
    "/events/process-clip",
    response_model=ProcessClipResponse,
    status_code=status.HTTP_200_OK,
    summary="Process video clip via Gemini 1.5 and save metrics to Firestore",
)
def process_clip(payload: ProcessClipRequest) -> ProcessClipResponse:
    """
    Takes a video clip stored in GCS or locally, prompts Gemini 1.5 for multimodal
    retail behavioral analysis, validates the output schema, and commits to Firestore.
    """
    event_id = f"evt_{uuid.uuid4().hex[:10]}"
    try:
        event = gemini_analyzer.analyze_video_clip(
            video_uri=payload.video_uri,
            event_id=event_id,
            zone_id=payload.zone_id,
            estimated_dwell_time_seconds=payload.estimated_dwell_time_seconds,
            timestamp=payload.timestamp,
        )
        doc_id = firestore_repo.save_event(event)

        return ProcessClipResponse(
            status="success",
            event=event,
            firestore_id=doc_id,
            message="Video clip analyzed and event stored successfully.",
        )
    except Exception as e:
        logger.error("Failed to process clip %s: %s", payload.video_uri, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process video clip: {str(e)}",
        )


@router.post(
    "/events/upload-and-process",
    response_model=ProcessClipResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload an MP4 clip from edge camera and process immediately",
)
async def upload_and_process(
    file: UploadFile = File(...),
    zone_id: str = Form("zone_default"),
    estimated_dwell_time_seconds: Optional[int] = Form(None),
) -> ProcessClipResponse:
    """
    Uploads a video clip from the edge node, persists it to GCS (or local staging),
    runs multimodal inference, and saves the metrics to Firestore.
    """
    if not file.filename.endswith((".mp4", ".mov", ".avi", ".mkv")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a supported video format (.mp4, .mov, etc.)",
        )

    event_id = f"evt_{uuid.uuid4().hex[:10]}"
    ext = os.path.splitext(file.filename)[1] or ".mp4"
    temp_filename = f"{event_id}{ext}"

    start_total = time.time()
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name

        # Upload to GCS / storage
        destination_blob = f"clips/{temp_filename}"
        video_uri = storage_service.upload_file(temp_path, destination_blob)

        # Analyze
        event = gemini_analyzer.analyze_video_clip(
            video_uri=video_uri,
            event_id=event_id,
            zone_id=zone_id,
            estimated_dwell_time_seconds=estimated_dwell_time_seconds,
        )
        event.total_latency_ms = int((time.time() - start_total) * 1000)
        doc_id = firestore_repo.save_event(event)

        return ProcessClipResponse(
            status="success",
            event=event,
            firestore_id=doc_id,
            message="Clip uploaded and analyzed successfully.",
        )
    except Exception as e:
        logger.error("Error handling clip upload: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload processing failed: {str(e)}",
        )
    finally:
        if "temp_path" in locals() and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


@router.get(
    "/events",
    response_model=List[InteractionEvent],
    summary="Query interaction events with optional filtering",
)
def list_events(
    zone_id: Optional[str] = Query(None, description="Filter by shelf/zone ID"),
    interaction_type: Optional[InteractionType] = Query(None, description="Filter by interaction type"),
    outcome: Optional[ConversionOutcome] = Query(None, description="Filter by conversion outcome"),
    limit: int = Query(50, ge=1, le=500, description="Max records to return"),
) -> List[InteractionEvent]:
    return firestore_repo.list_events(
        zone_id=zone_id,
        interaction_type=interaction_type,
        outcome=outcome,
        limit=limit,
    )


@router.get(
    "/events/{event_id}",
    response_model=InteractionEvent,
    summary="Fetch single interaction event by ID",
)
def get_event(event_id: str) -> InteractionEvent:
    event = firestore_repo.get_event(event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event with ID '{event_id}' not found.",
        )
    return event


@router.get(
    "/events/{event_id}/stream",
    summary="Stream video clip for browser video playback",
)
def stream_event_video(event_id: str):
    """Streams the raw video bytes from Cloud Storage directly to browser player."""
    event = firestore_repo.get_event(event_id)
    if not event or not event.video_uri:
        raise HTTPException(status_code=404, detail="Video clip not found")
    try:
        video_bytes = storage_service.resolve_video_bytes(event.video_uri)
        return StreamingResponse(
            io.BytesIO(video_bytes),
            media_type="video/mp4",
            headers={"Content-Disposition": f"inline; filename={event_id}.mp4"},
        )
    except Exception as e:
        logger.error("Failed to stream video for %s: %s", event_id, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/analytics/summary",
    response_model=Dict[str, Any],
    summary="Get aggregated retail metrics (abandonment rate, conversion rate, dwell time)",
)
def get_analytics_summary() -> Dict[str, Any]:
    return firestore_repo.get_summary()


@router.post(
    "/events/mock-trigger",
    response_model=ProcessClipResponse,
    summary="Simulate an edge zone trigger for testing without a live video",
)
def mock_trigger(
    zone_id: str = Query("aisle_3_shelf_eye_level"),
    dwell_time: int = Query(8, ge=3),
) -> ProcessClipResponse:
    """Quick testing helper to simulate an edge trigger."""
    event_id = f"evt_mock_{uuid.uuid4().hex[:8]}"
    event = gemini_analyzer.analyze_video_clip(
        video_uri="mock://sample_interaction.mp4",
        event_id=event_id,
        zone_id=zone_id,
        estimated_dwell_time_seconds=dwell_time,
    )
    doc_id = firestore_repo.save_event(event)
    return ProcessClipResponse(
        status="success",
        event=event,
        firestore_id=doc_id,
        message="Simulated mock event generated and committed.",
    )
