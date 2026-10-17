import logging
import os
from typing import Any, Dict, Optional
import requests
from camera_node.config import EdgeConfig

logger = logging.getLogger(__name__)


class ClipUploader:
    """Dispatches extracted interaction video clips to GCS or Backend Service."""

    def __init__(self, config: EdgeConfig) -> None:
        self.config = config
        self._gcs_client = None
        self._gcs_bucket = None
        if self.config.use_direct_gcs_upload:
            self._init_gcs()

    def _init_gcs(self) -> None:
        try:
            from google.cloud import storage

            if self.config.google_application_credentials:
                self._gcs_client = storage.Client.from_service_account_json(
                    self.config.google_application_credentials,
                    project=self.config.gcp_project_id,
                )
            else:
                self._gcs_client = storage.Client(project=self.config.gcp_project_id)
            self._gcs_bucket = self._gcs_client.bucket(self.config.gcs_bucket_name)
            logger.info("Direct GCS upload enabled with bucket: %s", self.config.gcs_bucket_name)
        except Exception as e:
            logger.warning("Could not initialize direct GCS upload client (%s). Using HTTP backend upload.", e)
            self.config.use_direct_gcs_upload = False

    def dispatch_clip(
        self,
        clip_path: str,
        zone_id: str,
        dwell_time_seconds: float,
    ) -> Optional[Dict[str, Any]]:
        """
        Uploads clip and triggers multimodal processing on backend.
        """
        if not os.path.exists(clip_path):
            logger.error("Clip path not found: %s", clip_path)
            return None

        # Mode A: Direct GCS upload + JSON webhook
        if self.config.use_direct_gcs_upload and self._gcs_bucket is not None:
            try:
                blob_name = f"clips/{os.path.basename(clip_path)}"
                blob = self._gcs_bucket.blob(blob_name)
                blob.upload_from_filename(clip_path, content_type="video/mp4")
                gcs_uri = f"gs://{self.config.gcs_bucket_name}/{blob_name}"
                logger.info("Directly uploaded clip to GCS: %s", gcs_uri)

                # Notify backend process-clip endpoint
                notify_url = f"{self.config.backend_api_url.rstrip('/')}/api/v1/events/process-clip"
                payload = {
                    "video_uri": gcs_uri,
                    "zone_id": zone_id,
                    "estimated_dwell_time_seconds": int(round(dwell_time_seconds)),
                }
                res = requests.post(notify_url, json=payload, timeout=30)
                res.raise_for_status()
                data = res.json()
                logger.info("Backend processing triggered successfully: %s", data.get("status"))
                return data
            except Exception as e:
                logger.error("Direct GCS upload/notification failed: %s", e)

        # Mode B: Direct HTTP Multipart upload to Backend API
        try:
            url = f"{self.config.backend_api_url.rstrip('/')}/api/v1/events/upload-and-process"
            logger.info("Uploading clip %s to backend at %s", clip_path, url)

            with open(clip_path, "rb") as video_file:
                files = {"file": (os.path.basename(clip_path), video_file, "video/mp4")}
                data = {
                    "zone_id": zone_id,
                    "estimated_dwell_time_seconds": str(int(round(dwell_time_seconds))),
                }
                response = requests.post(url, files=files, data=data, timeout=60)
                response.raise_for_status()
                result = response.json()
                evt = result.get("event", {})
                
                print("\n" + "=" * 65)
                print(f"🎯 GEMINI MULTIMODAL VIDEO ANALYSIS RESULT ({evt.get('event_id')})")
                print("=" * 65)
                print(f"📍 Zone:            {evt.get('zone_id')}")
                print(f"⏱️ Dwell Time:      {evt.get('zone_dwell_time_seconds')}s")
                print(f"👀 Engagement Type: {str(evt.get('interaction_type', '')).upper()}")
                print(f"🛒 Outcome:         {str(evt.get('conversion_outcome', '')).upper()}")
                print(f"🏷️ Product Engaged: {evt.get('product_category_engaged')}")
                print(f"👥 Demographic:     {evt.get('estimated_demographic')} (Group size: {evt.get('shopper_group_size')})")
                gem_lat = evt.get('gemini_latency_ms')
                tot_lat = evt.get('total_latency_ms')
                if gem_lat and tot_lat:
                    print(f"⚡ Cloud Latency:   Gemini Vision: {gem_lat}ms | End-to-End: {tot_lat}ms")
                print(f"\n📝 AI Behavioral Summary:")
                print(f"   \"{evt.get('behavioral_summary')}\"")
                print(f"\n💾 Saved to Firestore: document ID '{result.get('firestore_id')}'")
                print("=" * 65 + "\n")
                
                return result
        except Exception as e:
            logger.error("Failed to upload clip to backend service (%s)", e)
            return None
