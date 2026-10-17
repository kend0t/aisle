import json
import logging
import os
import re
import time
from typing import Any, Dict, Optional
from backend_service.config import get_settings
from backend_service.models.interaction_event import (
    ConversionOutcome,
    InteractionEvent,
    InteractionType,
)
from backend_service.services.storage_service import StorageService

logger = logging.getLogger(__name__)

BEHAVIOR_TAG_GUIDE = """- behavior_tags (include only behaviors clearly visible in the clip; use an empty list if none apply):
  - 'phone_check': Used a phone while at the shelf (photographing a product, checking a price).
  - 'compared_alternatives': Held or looked back and forth between two or more products.
  - 'low_shelf_reach': Bent down or crouched to reach a lower shelf.
  - 'label_inspection': Turned or held a product close to read its packaging.
  - 'carried_basket': Carried a basket or pushed a cart.
  - 'hesitated': Paused with a product in hand before deciding.
"""

SYSTEM_PROMPT = (
    """You are an expert AI retail behavioral analyst for in-store physical retail analytics.
You analyze short overhead or shelf-facing video clips of customer interactions with retail store shelves and displays.

Analyze the video and output a strict JSON object with EXACTLY the following fields:
{
  "event_id": "<string: use the provided event_id or generate a unique id>",
  "timestamp": "<string: ISO 8601 timestamp>",
  "zone_id": "<string: the retail zone identifier passed in context>",
  "zone_dwell_time_seconds": <integer: total seconds customer dwelled in the zone>,
  "interaction_type": "<one of: 'passed_by', 'browsed', 'examined', 'compared'>",
  "conversion_outcome": "<one of: 'taken', 'returned', 'none'>",
  "product_category_engaged": "<string: descriptive shelf section or product description>",
  "shopper_group_size": <integer: 1, 2, or more>,
  "estimated_demographic": "<one of: 'young_adult', 'adult', 'senior', 'unknown'>",
  "behavioral_summary": "<string: 1-2 sentence narrative detailing customer movement, hesitation, physical touches, and final action>",
  "behavior_tags": ["<zero or more of: 'phone_check', 'compared_alternatives', 'low_shelf_reach', 'label_inspection', 'carried_basket', 'hesitated'>"]
}

Definitions:
- interaction_type:
  - 'passed_by': Walked through zone without stopping.
  - 'browsed': Stopped and looked at shelf, no physical contact.
  - 'examined': Picked up an item to inspect (label, price, texture).
  - 'compared': Picked up multiple items or looked back and forth between alternatives.
- conversion_outcome:
  - 'taken': Placed in cart, basket, or held to purchase.
  - 'returned': Placed back onto the shelf (cart abandonment).
  - 'none': No product was physically removed.
"""
    + BEHAVIOR_TAG_GUIDE
    + """
Return ONLY the valid JSON object without markdown code blocks or additional commentary.
"""
)


class GeminiAnalyzerService:
    """Multimodal video interaction analyzer powered by Google Gemini 1.5."""

    def __init__(self, storage_service: Optional[StorageService] = None) -> None:
        self.settings = get_settings()
        self.storage = storage_service or StorageService()
        self._mode = "uninitialized"
        self._genai_client = None
        self._init_client()

    def _init_client(self) -> None:
        """Configures Google GenAI SDK (Vertex AI or API key) with fallback."""
        if self.settings.GOOGLE_APPLICATION_CREDENTIALS:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self.settings.GOOGLE_APPLICATION_CREDENTIALS

        # 1. Primary: Unified google.genai SDK with Vertex AI
        try:
            from google import genai

            # Try Vertex AI mode first if GCP project is set
            if self.settings.GCP_PROJECT_ID and self.settings.GCP_PROJECT_ID != "mock-gcp-project":
                self._genai_client = genai.Client(
                    vertexai=True,
                    project=self.settings.GCP_PROJECT_ID,
                    location=self.settings.GCP_REGION,
                )
                self._mode = "genai_vertex"
                logger.info(
                    "Initialized Gemini analyzer via google-genai Vertex AI (Model: %s, Project: %s)",
                    self.settings.GEMINI_MODEL,
                    self.settings.GCP_PROJECT_ID,
                )
                return
        except Exception as vertex_err:
            logger.info("google-genai Vertex AI init skipped/failed (%s)", vertex_err)

        # 2. Try google.genai with API key if configured
        if self.settings.GEMINI_API_KEY:
            try:
                from google import genai

                self._genai_client = genai.Client(api_key=self.settings.GEMINI_API_KEY)
                self._mode = "genai_apikey"
                logger.info("Initialized Gemini analyzer via google-genai API Key.")
                return
            except Exception as key_err:
                logger.warning("google-genai API key client failed: %s", key_err)

        # 3. Dry-run / mock simulation mode (allows local pipeline testing without credentials)
        self._mode = "mock_simulator"
        logger.info(
            "Operating in mock simulation mode (no live GCP project or GEMINI_API_KEY provided)."
        )

    def analyze_video_clip(
        self,
        video_uri: str,
        event_id: str,
        zone_id: str,
        estimated_dwell_time_seconds: Optional[int] = None,
        timestamp: Optional[str] = None,
    ) -> InteractionEvent:
        """
        Analyzes a video clip using Gemini 1.5 multimodal vision and validates into InteractionEvent.
        """
        prompt = (
            f"Event ID: {event_id}\n"
            f"Zone ID: {zone_id}\n"
            f"Estimated Edge Dwell Time: {estimated_dwell_time_seconds or 'Observe from video'} seconds.\n"
            f"Timestamp: {timestamp or 'Current'}\n\n"
            "Analyze the shopper behavior in this clip and return the JSON metric object."
        )

        raw_response_text: str = ""
        gemini_latency_ms = None

        try:
            start_gemini = time.time()
            if self._mode in ("genai_vertex", "genai_apikey"):
                raw_response_text = self._call_genai_client(video_uri, prompt)
            else:
                raw_response_text = self._generate_mock_analysis(
                    event_id=event_id,
                    zone_id=zone_id,
                    dwell_time=estimated_dwell_time_seconds or 7,
                    timestamp=timestamp,
                )
            gemini_latency_ms = int((time.time() - start_gemini) * 1000)

            # Clean and parse JSON
            parsed_data = self._clean_and_parse_json(raw_response_text)
            parsed_data["video_uri"] = video_uri
            parsed_data["gemini_latency_ms"] = gemini_latency_ms
            if not parsed_data.get("event_id"):
                parsed_data["event_id"] = event_id
            if not parsed_data.get("zone_id"):
                parsed_data["zone_id"] = zone_id

            # Pydantic validation
            event = InteractionEvent.model_validate(parsed_data)
            logger.info(
                "Gemini Video Analysis [%s | Zone: %s]: Type=%s | Outcome=%s | Product='%s'\n"
                ">> AI Behavioral Summary: %s",
                event.event_id,
                event.zone_id,
                event.interaction_type.value.upper(),
                event.conversion_outcome.value.upper(),
                event.product_category_engaged,
                event.behavioral_summary,
            )
            return event

        except Exception as e:
            logger.error("Error during Gemini video analysis: %s. Response text: %s", e, raw_response_text)
            # Return graceful fallback event rather than crashing entire ingestion pipeline
            return InteractionEvent(
                event_id=event_id,
                zone_id=zone_id,
                zone_dwell_time_seconds=estimated_dwell_time_seconds or 5,
                interaction_type=InteractionType.BROWSED,
                conversion_outcome=ConversionOutcome.NONE,
                product_category_engaged="general_shelf",
                shopper_group_size=1,
                estimated_demographic="adult",
                behavioral_summary=f"Automated fallback event due to analysis exception: {str(e)}",
                video_uri=video_uri,
                confidence_score=0.5,
            )

    def _call_genai_client(self, video_uri: str, prompt: str) -> str:
        """Invokes google.genai Client with video part and system instruction."""
        from google.genai import types

        if video_uri.startswith("gs://"):
            video_part = types.Part.from_uri(file_uri=video_uri, mime_type="video/mp4")
        else:
            video_bytes = self.storage.resolve_video_bytes(video_uri)
            video_part = types.Part.from_bytes(data=video_bytes, mime_type="video/mp4")

        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.2,
            response_mime_type="application/json",
        )
        response = self._genai_client.models.generate_content(
            model=self.settings.GEMINI_MODEL,
            contents=[video_part, prompt],
            config=config,
        )
        return response.text

    def _clean_and_parse_json(self, response_text: str) -> Dict[str, Any]:
        """Strips markdown delimiters and parses JSON."""
        cleaned = response_text.strip()
        if "```" in cleaned:
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.MULTILINE)
            cleaned = re.sub(r"```$", "", cleaned, flags=re.MULTILINE)
            cleaned = cleaned.strip()

        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1:
            cleaned = cleaned[start : end + 1]

        return json.loads(cleaned)

    def _generate_mock_analysis(
        self, event_id: str, zone_id: str, dwell_time: int, timestamp: Optional[str]
    ) -> str:
        """Provides realistic synthetic behavioral extraction for offline dev testing."""
        from datetime import datetime, timezone
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        return json.dumps(
            {
                "event_id": event_id,
                "timestamp": ts,
                "zone_id": zone_id,
                "zone_dwell_time_seconds": dwell_time,
                "interaction_type": "examined",
                "conversion_outcome": "returned",
                "product_category_engaged": "eye_level_organic_cereals",
                "shopper_group_size": 1,
                "estimated_demographic": "adult",
                "behavioral_summary": (
                    "Shopper approached eye-level shelf, dwelled for "
                    f"{dwell_time}s, picked up an organic cereal box to examine the nutritional panel, "
                    "hesitated, and returned it back to the shelf before exiting."
                ),
                "behavior_tags": ["label_inspection", "hesitated"],
            }
        )
