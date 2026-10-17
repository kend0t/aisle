import logging
import os
from pathlib import Path
from typing import Optional
from backend_service.config import get_settings

logger = logging.getLogger(__name__)


class StorageService:
    """Handles video clip storage operations in Google Cloud Storage with local fallback."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.bucket_name = self.settings.GCS_BUCKET_NAME
        self.project_id = self.settings.GCP_PROJECT_ID
        self._client = None
        self._bucket = None
        self._init_client()

    def _init_client(self) -> None:
        """Initializes the GCS client or falls back to local storage."""
        try:
            from google.cloud import storage

            # Check if GCP credentials or project are configured
            if self.settings.GOOGLE_APPLICATION_CREDENTIALS:
                self._client = storage.Client.from_service_account_json(
                    self.settings.GOOGLE_APPLICATION_CREDENTIALS,
                    project=self.project_id,
                )
            else:
                # Attempt default credentials
                self._client = storage.Client(project=self.project_id)

            self._bucket = self._client.bucket(self.bucket_name)
            logger.info("Successfully connected to Google Cloud Storage bucket: %s", self.bucket_name)
        except Exception as e:
            logger.warning(
                "Could not initialize GCS client (%s). Using local storage fallback in %s",
                e,
                self.settings.LOCAL_UPLOAD_DIR,
            )
            self._client = None
            self._bucket = None

    def upload_file(self, local_path: str, destination_blob_name: str) -> str:
        """
        Uploads a video file to GCS and returns its gs:// URI.
        Falls back to local file path if GCS is unavailable.
        """
        if not os.path.exists(local_path):
            raise FileNotFoundError(f"Source file not found at: {local_path}")

        if self._bucket is not None:
            try:
                blob = self._bucket.blob(destination_blob_name)
                blob.upload_from_filename(local_path, content_type="video/mp4")
                uri = f"gs://{self.bucket_name}/{destination_blob_name}"
                logger.info("Uploaded clip to GCS: %s", uri)
                return uri
            except Exception as e:
                logger.error("Failed to upload to GCS (%s). Falling back to local copy.", e)

        # Fallback: copy to local storage directory
        local_dir = Path(self.settings.LOCAL_UPLOAD_DIR)
        local_dir.mkdir(parents=True, exist_ok=True)
        dest_path = local_dir / Path(destination_blob_name).name
        if str(dest_path.resolve()) != str(Path(local_path).resolve()):
            import shutil
            shutil.copy2(local_path, dest_path)

        logger.info("Stored clip locally at: %s", dest_path)
        return str(dest_path.resolve())

    def resolve_video_bytes(self, video_uri: str) -> bytes:
        """
        Retrieves video bytes from either a GCS URI (gs://...) or a local file path.
        """
        if video_uri.startswith("gs://"):
            if self._client is None:
                raise RuntimeError(
                    f"GCS client is not configured to fetch gs:// URI: {video_uri}"
                )
            # Parse bucket and blob
            parts = video_uri.replace("gs://", "").split("/", 1)
            bucket_name = parts[0]
            blob_name = parts[1] if len(parts) > 1 else ""
            bucket = self._client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            return blob.download_as_bytes()

        # Local file path
        if not os.path.exists(video_uri):
            raise FileNotFoundError(f"Video file not found at: {video_uri}")

        with open(video_uri, "rb") as f:
            return f.read()

    def generate_signed_url(self, video_uri: str, expiration_minutes: int = 60) -> Optional[str]:
        """Generates a signed URL for web playback of a video clip."""
        if not video_uri or not video_uri.startswith("gs://"):
            return None
        if self._bucket is None:
            return None
        try:
            from datetime import timedelta
            parts = video_uri.replace("gs://", "").split("/", 1)
            blob_name = parts[1] if len(parts) > 1 else ""
            blob = self._bucket.blob(blob_name)
            return blob.generate_signed_url(
                version="v4",
                expiration=timedelta(minutes=expiration_minutes),
                method="GET",
            )
        except Exception as e:
            logger.warning("Could not generate signed URL for %s: %s", video_uri, e)
            return None
