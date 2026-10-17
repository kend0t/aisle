import logging
import os
import tempfile
import time
import uuid
import io
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse, Response, StreamingResponse

from backend_service.db.firestore_client import FirestoreRepository
from backend_service.models.chat import ChatRequest, ChatResponse, QuickPrompt
from backend_service.models.insights import InsightsResponse
from backend_service.models.interaction_event import (
    ConversionOutcome,
    InteractionEvent,
    InteractionType,
    ProcessClipRequest,
    ProcessClipResponse,
)
from backend_service.services.chat_service import StoreChatService
from backend_service.services.gemini_analyzer import GeminiAnalyzerService
from backend_service.services.insights_service import InsightsService
from backend_service.services.storage_service import StorageService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Events & Analytics"])

# Dependency singletons
storage_service = StorageService()
gemini_analyzer = GeminiAnalyzerService(storage_service=storage_service)
firestore_repo = FirestoreRepository()
chat_service = StoreChatService(firestore_repo=firestore_repo)
insights_service = InsightsService(firestore_repo=firestore_repo, chat_service=chat_service)

CLIP_CACHE_DIR = Path("temp_uploads/clip_cache")



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


def ensure_h264_stream(file_path: Path) -> Path:
    """Verifies that the video uses H.264 (avc1) for HTML5 browser compatibility.
    If encoded in legacy mp4v/FMP4, transcodes on-the-fly for web playback."""
    try:
        import cv2

        cap = cv2.VideoCapture(str(file_path))
        fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
        codec = "".join([chr((fourcc >> 8 * i) & 0xFF) for i in range(4)]).upper()
        cap.release()

        if codec in ("H264", "AVC1", "X264"):
            return file_path

        h264_path = file_path.with_name(f"{file_path.stem}_browser.mp4")
        if h264_path.exists() and h264_path.stat().st_size > 0:
            return h264_path

        cap = cv2.VideoCapture(str(file_path))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        out_fourcc = cv2.VideoWriter_fourcc(*"avc1")
        out = cv2.VideoWriter(str(h264_path), out_fourcc, fps, (w, h))

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            out.write(frame)

        cap.release()
        out.release()
        return h264_path
    except Exception as e:
        logger.warning("Could not transcode video %s to H.264: %s", file_path, e)
        return file_path


def cache_clip_locally(event: InteractionEvent) -> Path:
    """Downloads the event's clip to the local cache once and returns its path."""
    CLIP_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cached_file = CLIP_CACHE_DIR / f"{event.event_id}.mp4"

    if not cached_file.exists() or cached_file.stat().st_size == 0:
        try:
            video_bytes = storage_service.resolve_video_bytes(event.video_uri)
            with open(cached_file, "wb") as f:
                f.write(video_bytes)
        except Exception as download_err:
            logger.warning("Could not download video from GCS (%s). Using sample clip fallback.", download_err)
            sample_file = Path("sample_retail_interaction.mp4")
            if sample_file.exists():
                import shutil
                shutil.copy2(sample_file, cached_file)
            else:
                raise download_err
    return cached_file


@router.get(
    "/events/{event_id}/stream",
    summary="Stream video clip for browser video playback with byte-range support",
)
def stream_event_video(event_id: str):
    """Streams video clip.
    In cloud environments (like Cloud Run), generates a direct Google Cloud Storage signed URL
    and redirects the browser (HTTP 307), enabling native HTTP 206 byte-range streaming via Google CDN
    with 0 MB container memory overhead and zero reliance on local disk cache.
    Falls back to local file streaming when running offline or locally."""
    event = firestore_repo.get_event(event_id)
    if not event or not event.video_uri:
        raise HTTPException(status_code=404, detail="Video clip not found")
    try:
        # 1. Cloud-Native Path: Direct GCS Signed URL Redirection
        if event.video_uri.startswith("gs://"):
            signed_url = storage_service.generate_signed_url(event.video_uri, expiration_minutes=60)
            if signed_url:
                logger.info("Redirecting %s stream to GCS Signed URL", event_id)
                return RedirectResponse(
                    url=signed_url,
                    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
                )

        # 2. Local Fallback Path: Stream from local disk or ephemeral cache
        cached_file = cache_clip_locally(event)

        # Ensure video is encoded in H.264 (avc1) for native browser playback
        playable_file = ensure_h264_stream(cached_file)

        # FileResponse natively handles HTTP 206 Partial Content, Range headers, and Content-Length
        return FileResponse(
            path=str(playable_file),
            media_type="video/mp4",
            filename=f"{event_id}.mp4",
            content_disposition_type="inline",
        )
    except Exception as e:
        logger.error("Failed to stream video for %s: %s", event_id, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/events/{event_id}/thumbnail",
    summary="JPEG still frame from the middle of the event's clip",
)
def get_event_thumbnail(event_id: str) -> Response:
    event = firestore_repo.get_event(event_id)
    if not event or not event.video_uri:
        raise HTTPException(status_code=404, detail="Video clip not found")

    thumb_file = CLIP_CACHE_DIR / f"{event_id}_thumb.jpg"
    if not thumb_file.exists() or thumb_file.stat().st_size == 0:
        try:
            import cv2

            clip_file = cache_clip_locally(event)
            cap = cv2.VideoCapture(str(clip_file))
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, frame_count // 2))
            ok, frame = cap.read()
            cap.release()
            if not ok:
                raise RuntimeError("could not read a frame from the clip")
            height, width = frame.shape[:2]
            target_width = 480
            frame = cv2.resize(frame, (target_width, int(height * target_width / width)))
            cv2.imwrite(str(thumb_file), frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        except Exception as e:
            logger.error("Failed to build thumbnail for %s: %s", event_id, e)
            raise HTTPException(status_code=500, detail=f"Could not build thumbnail: {e}")

    return FileResponse(
        path=str(thumb_file),
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get(
    "/analytics/summary",
    response_model=Dict[str, Any],
    summary="Get aggregated retail metrics (abandonment rate, conversion rate, dwell time)",
)
def get_analytics_summary() -> Dict[str, Any]:
    return firestore_repo.get_summary()


@router.get(
    "/chat/quick-prompts",
    response_model=List[QuickPrompt],
    summary="Get curated quick prompt cards answerable by store metrics",
)
def get_quick_prompts() -> List[QuickPrompt]:
    """Returns high-value sample prompts that are directly answerable by the gathered metrics."""
    return chat_service.get_quick_prompts()


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Ask questions to the grounded AIsle Retail Copilot",
)
def chat_with_copilot(payload: ChatRequest) -> ChatResponse:
    """Conversational endpoint grounded on live Firestore analytics and interaction logs."""
    response = chat_service.chat(payload)
    # Only keep citations that resolve to stored events, so every replay link works
    response.referenced_events = [
        event_id for event_id in response.referenced_events if firestore_repo.get_event(event_id)
    ]
    return response


@router.get(
    "/insights",
    response_model=InsightsResponse,
    summary="Ranked findings for a store manager, each backed by clips",
)
def get_insights() -> InsightsResponse:
    """Gemini-written findings, cached in memory until the stored events change."""
    return insights_service.get_insights()


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

