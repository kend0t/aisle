import logging
import os
import shutil
from datetime import timedelta
from pathlib import Path
from typing import Optional

from backend_service.config import Settings
from backend_service.errors import DataSourceError

logger = logging.getLogger(__name__)


class StorageService:
    """Video clip storage.

    With `use_gcs` the clips live in Cloud Storage and every failure raises
    DataSourceError. Without it (seed mode) uploads go to local disk.
    """

    def __init__(self, settings: Settings, use_gcs: bool) -> None:
        self.bucket_name = settings.GCS_BUCKET_NAME
        self.local_dir = Path(settings.LOCAL_UPLOAD_DIR)
        self._client = None
        self._bucket = None
        if not use_gcs:
            logger.info("Storing clips on local disk in %s", self.local_dir)
            return

        try:
            from google.cloud import storage

            if settings.GOOGLE_APPLICATION_CREDENTIALS:
                self._client = storage.Client.from_service_account_json(
                    settings.GOOGLE_APPLICATION_CREDENTIALS, project=settings.GCP_PROJECT_ID
                )
            else:
                self._client = storage.Client(project=settings.GCP_PROJECT_ID)
            self._bucket = self._client.bucket(self.bucket_name)
        except Exception as e:
            raise DataSourceError("Cloud Storage", "connection", e) from e
        logger.info("Using Cloud Storage bucket %s", self.bucket_name)

    def upload_file(self, local_path: str, destination_blob_name: str) -> str:
        """Stores a clip and returns its URI: gs://... with GCS, else a local path."""
        if not os.path.exists(local_path):
            raise FileNotFoundError(f"Source file not found at: {local_path}")

        if self._bucket is not None:
            try:
                self._bucket.blob(destination_blob_name).upload_from_filename(
                    local_path, content_type="video/mp4"
                )
            except Exception as e:
                raise DataSourceError("Cloud Storage", "upload", e) from e
            uri = f"gs://{self.bucket_name}/{destination_blob_name}"
            logger.info("Uploaded clip to %s", uri)
            return uri

        self.local_dir.mkdir(parents=True, exist_ok=True)
        dest_path = self.local_dir / Path(destination_blob_name).name
        if dest_path.resolve() != Path(local_path).resolve():
            shutil.copy2(local_path, dest_path)
        logger.info("Stored clip locally at %s", dest_path)
        return str(dest_path.resolve())

    def resolve_video_bytes(self, video_uri: str) -> bytes:
        """Reads clip bytes from a gs:// URI or a local file path."""
        if video_uri.startswith("gs://"):
            if self._client is None:
                raise DataSourceError("Cloud Storage", "download (not configured)")
            bucket_name, _, blob_name = video_uri.removeprefix("gs://").partition("/")
            try:
                return self._client.bucket(bucket_name).blob(blob_name).download_as_bytes()
            except Exception as e:
                raise DataSourceError("Cloud Storage", "download", e) from e

        if not os.path.exists(video_uri):
            raise FileNotFoundError(f"Video file not found at: {video_uri}")
        with open(video_uri, "rb") as f:
            return f.read()

    def generate_signed_url(self, video_uri: str, expiration_minutes: int = 60) -> Optional[str]:
        """Signed URL for direct browser playback, or None when signing is not possible.

        None is not an error: the caller streams the clip from the local cache instead.
        """
        if not video_uri.startswith("gs://") or self._bucket is None:
            return None
        try:
            blob = self._bucket.blob(video_uri.removeprefix("gs://").partition("/")[2])
            return blob.generate_signed_url(
                version="v4", expiration=timedelta(minutes=expiration_minutes), method="GET"
            )
        except Exception as e:
            logger.warning("Could not sign a URL for %s: %s", video_uri, e)
            return None
