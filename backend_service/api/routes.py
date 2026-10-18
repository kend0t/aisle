import hashlib
import logging
import os
import tempfile
import time
import uuid
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse, Response

from backend_service.db.firestore_client import EventRepository
from backend_service.dependencies import (
    get_analyzer,
    get_chat,
    get_insights,
    get_media,
    get_repo,
    get_storage,
)
from backend_service.models.chat import ChatRequest, ChatResponse, QuickPrompt
from backend_service.models.insights import InsightsResponse
from backend_service.models.interaction_event import (
    ConversionOutcome,
    InteractionEvent,
    InteractionType,
    ProcessClipRequest,
    ProcessClipResponse,
)
from backend_service.services.chat_service import CURATED_QUICK_PROMPTS, StoreChatService
from backend_service.services.clip_media import ClipMediaService
from backend_service.services.gemini_analyzer import GeminiAnalyzerService
from backend_service.services.insights_service import InsightsService
from backend_service.services.storage_service import StorageService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Events & Analytics"])


def _require_clip(repo: EventRepository, event_id: str) -> InteractionEvent:
    event = repo.get_event(event_id)
    if not event or not event.video_uri:
        raise HTTPException(status_code=404, detail="Video clip not found")
    return event


@router.post(
    "/events/process-clip",
    response_model=ProcessClipResponse,
    status_code=status.HTTP_200_OK,
    summary="Process video clip via Gemini and save metrics to Firestore",
)
def process_clip(
    payload: ProcessClipRequest,
    analyzer: GeminiAnalyzerService = Depends(get_analyzer),
    repo: EventRepository = Depends(get_repo),
) -> ProcessClipResponse:
    """
    Takes a video clip stored in GCS or locally, prompts Gemini for multimodal
    retail behavioral analysis, validates the output schema, and commits to Firestore.
    """
    event = analyzer.analyze_video_clip(
        video_uri=payload.video_uri,
        event_id=f"evt_{uuid.uuid4().hex[:10]}",
        zone_id=payload.zone_id,
        estimated_dwell_time_seconds=payload.estimated_dwell_time_seconds,
        timestamp=payload.timestamp,
    )
    return ProcessClipResponse(
        status="success",
        event=event,
        firestore_id=repo.save_event(event),
        message="Video clip analyzed and event stored successfully.",
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
    storage: StorageService = Depends(get_storage),
    analyzer: GeminiAnalyzerService = Depends(get_analyzer),
    repo: EventRepository = Depends(get_repo),
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
    start_total = time.time()

    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as temp_file:
        temp_file.write(await file.read())
        temp_path = temp_file.name
    try:
        video_uri = storage.upload_file(temp_path, f"clips/{event_id}{ext}")
        event = analyzer.analyze_video_clip(
            video_uri=video_uri,
            event_id=event_id,
            zone_id=zone_id,
            estimated_dwell_time_seconds=estimated_dwell_time_seconds,
        )
        event.total_latency_ms = int((time.time() - start_total) * 1000)
        return ProcessClipResponse(
            status="success",
            event=event,
            firestore_id=repo.save_event(event),
            message="Clip uploaded and analyzed successfully.",
        )
    finally:
        os.remove(temp_path)


@router.get(
    "/events",
    response_model=List[InteractionEvent],
    summary="Query interaction events with optional filtering",
    responses={304: {"description": "Events unchanged since the ETag in If-None-Match"}},
)
def list_events(
    request: Request,
    response: Response,
    zone_id: Optional[str] = Query(None, description="Filter by shelf/zone ID"),
    interaction_type: Optional[InteractionType] = Query(None, description="Filter by interaction type"),
    outcome: Optional[ConversionOutcome] = Query(None, description="Filter by conversion outcome"),
    limit: int = Query(50, ge=1, le=500, description="Max records to return"),
    repo: EventRepository = Depends(get_repo),
) -> Union[List[InteractionEvent], Response]:
    events = repo.list_events(zone_id=zone_id, interaction_type=interaction_type, outcome=outcome, limit=limit)

    # The dashboard polls this endpoint; an ETag lets the browser revalidate with a 304.
    fingerprint = "|".join(sorted(f"{e.event_id}:{e.created_at}:{','.join(e.behavior_tags)}" for e in events))
    etag = f'"{hashlib.sha1(fingerprint.encode()).hexdigest()}"'
    headers = {"ETag": etag, "Cache-Control": "no-cache"}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)
    response.headers.update(headers)
    return events


@router.get(
    "/events/{event_id}",
    response_model=InteractionEvent,
    summary="Fetch single interaction event by ID",
)
def get_event(event_id: str, repo: EventRepository = Depends(get_repo)) -> InteractionEvent:
    event = repo.get_event(event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event with ID '{event_id}' not found.",
        )
    return event


@router.get(
    "/events/{event_id}/stream",
    summary="Stream video clip for browser video playback with byte-range support",
)
def stream_event_video(
    event_id: str,
    repo: EventRepository = Depends(get_repo),
    storage: StorageService = Depends(get_storage),
    media: ClipMediaService = Depends(get_media),
):
    """Streams video clip.
    In cloud environments (like Cloud Run), generates a direct Google Cloud Storage signed URL
    and redirects the browser (HTTP 307), enabling native HTTP 206 byte-range streaming via Google CDN
    with 0 MB container memory overhead and zero reliance on local disk cache.
    Falls back to local file streaming when the URL cannot be signed (for example with user ADC)."""
    event = _require_clip(repo, event_id)

    signed_url = storage.generate_signed_url(event.video_uri, expiration_minutes=60)
    if signed_url:
        return RedirectResponse(url=signed_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)

    # FileResponse natively handles HTTP 206 Partial Content, Range headers, and Content-Length
    return FileResponse(
        path=str(media.playable_clip(event)),
        media_type="video/mp4",
        filename=f"{event_id}.mp4",
        content_disposition_type="inline",
    )


@router.get(
    "/events/{event_id}/thumbnail",
    summary="JPEG still frame from the middle of the event's clip",
)
def get_event_thumbnail(
    event_id: str,
    repo: EventRepository = Depends(get_repo),
    media: ClipMediaService = Depends(get_media),
) -> FileResponse:
    event = _require_clip(repo, event_id)
    return FileResponse(
        path=str(media.thumbnail(event)),
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get(
    "/analytics/summary",
    response_model=Dict[str, Any],
    summary="Get aggregated retail metrics (abandonment rate, conversion rate, dwell time)",
)
def get_analytics_summary(repo: EventRepository = Depends(get_repo)) -> Dict[str, Any]:
    return repo.get_summary()


@router.get(
    "/chat/quick-prompts",
    response_model=List[QuickPrompt],
    summary="Get curated quick prompt cards answerable by store metrics",
)
def get_quick_prompts() -> List[QuickPrompt]:
    """Returns high-value sample prompts that are directly answerable by the gathered metrics."""
    return CURATED_QUICK_PROMPTS


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Ask questions to the grounded AIsle Retail Copilot",
)
def chat_with_copilot(payload: ChatRequest, chat: StoreChatService = Depends(get_chat)) -> ChatResponse:
    """Conversational endpoint grounded on the stored analytics and interaction logs."""
    return chat.chat(payload)


@router.get(
    "/insights",
    response_model=InsightsResponse,
    summary="Ranked findings for a store manager, each backed by clips",
)
def get_insights_route(insights: InsightsService = Depends(get_insights)) -> InsightsResponse:
    """Gemini-written findings, cached in memory until the stored events change."""
    return insights.get_insights()


@router.post(
    "/events/mock-trigger",
    response_model=ProcessClipResponse,
    summary="Simulate an edge zone trigger for testing without a live video",
)
def mock_trigger(
    zone_id: str = Query("aisle_3_shelf_eye_level"),
    dwell_time: int = Query(8, ge=3),
    analyzer: GeminiAnalyzerService = Depends(get_analyzer),
    repo: EventRepository = Depends(get_repo),
) -> ProcessClipResponse:
    """Quick testing helper to simulate an edge trigger."""
    event = analyzer.analyze_video_clip(
        video_uri="mock://sample_interaction.mp4",
        event_id=f"evt_mock_{uuid.uuid4().hex[:8]}",
        zone_id=zone_id,
        estimated_dwell_time_seconds=dwell_time,
    )
    return ProcessClipResponse(
        status="success",
        event=event,
        firestore_id=repo.save_event(event),
        message="Simulated mock event generated and committed.",
    )
