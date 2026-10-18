import logging
import shutil
from pathlib import Path

import cv2

from backend_service.errors import DataSourceError
from backend_service.models.interaction_event import InteractionEvent
from backend_service.services.storage_service import StorageService

logger = logging.getLogger(__name__)

CLIP_CACHE_DIR = Path("temp_uploads/clip_cache")
SAMPLE_CLIP = Path("sample_retail_interaction.mp4")
THUMBNAIL_WIDTH = 480


class ClipMediaService:
    """Local copies of event clips for browser playback and thumbnails."""

    def __init__(self, storage: StorageService, allow_sample_clip: bool) -> None:
        self.storage = storage
        # Seed events point at clips that cannot be downloaded offline; only then is
        # the bundled sample clip an acceptable stand-in.
        self.allow_sample_clip = allow_sample_clip

    def local_clip(self, event: InteractionEvent) -> Path:
        """Downloads the event's clip to the local cache once and returns its path."""
        CLIP_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cached_file = CLIP_CACHE_DIR / f"{event.event_id}.mp4"
        if cached_file.exists() and cached_file.stat().st_size > 0:
            return cached_file

        try:
            cached_file.write_bytes(self.storage.resolve_video_bytes(event.video_uri))
        except (DataSourceError, FileNotFoundError):
            if not (self.allow_sample_clip and SAMPLE_CLIP.exists()):
                raise
            logger.info("Clip for %s not available offline; using the sample clip", event.event_id)
            shutil.copy2(SAMPLE_CLIP, cached_file)
        return cached_file

    def playable_clip(self, event: InteractionEvent) -> Path:
        """The cached clip, transcoded to H.264 when the browser cannot play its codec."""
        return ensure_h264(self.local_clip(event))

    def thumbnail(self, event: InteractionEvent) -> Path:
        """JPEG of the clip's middle frame, cached next to the clip."""
        thumb_file = CLIP_CACHE_DIR / f"{event.event_id}_thumb.jpg"
        if thumb_file.exists() and thumb_file.stat().st_size > 0:
            return thumb_file

        cap = cv2.VideoCapture(str(self.local_clip(event)))
        cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) // 2))
        ok, frame = cap.read()
        cap.release()
        if not ok:
            raise RuntimeError(f"Could not read a frame from the clip of {event.event_id}")

        height, width = frame.shape[:2]
        frame = cv2.resize(frame, (THUMBNAIL_WIDTH, int(height * THUMBNAIL_WIDTH / width)))
        cv2.imwrite(str(thumb_file), frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        return thumb_file


def ensure_h264(file_path: Path) -> Path:
    """Returns an H.264 (avc1) version of the clip for HTML5 playback.
    Legacy mp4v/FMP4 clips are transcoded once; the result is cached next to the source."""
    try:
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
        out = cv2.VideoWriter(str(h264_path), cv2.VideoWriter_fourcc(*"avc1"), fps, (w, h))
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
