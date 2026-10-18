import logging
import time
from typing import Any, Optional

from backend_service.models.interaction_event import (
    BehaviorTag,
    ClipAnalysis,
    ConversionOutcome,
    EstimatedDemographic,
    InteractionEvent,
    InteractionType,
)
from backend_service.services.gemini_client import GeminiClient
from backend_service.services.storage_service import StorageService

logger = logging.getLogger(__name__)

BEHAVIOR_TAG_GUIDE = """- behavior_tags (include only physical shopper behaviors clearly visible in the clip; use an empty list if none apply):
  - 'compared_alternatives': Held or looked back and forth between two or more products.
  - 'low_shelf_reach': Visibly crouched or bent at the waist to reach the bottom shelf. Reaching forward with an arm does not count.
  - 'label_inspection': Turned or held a product close to read packaging, ingredients, or nutrition labels.
  - 'carried_basket': Carried a basket or pushed a cart.
  - 'hesitated': Paused with a product in hand before deciding.
Note: Focus strictly on physical merchandise handling. Do not interpret small packages, snack bars, or items held in hands as smartphones or cameras.
"""

SYSTEM_PROMPT = (
    """You are an expert AI retail behavioral analyst for in-store physical retail analytics.
You analyze short overhead or shelf-facing video clips of customer interactions with retail store shelves and displays.

Definitions:
- interaction_type:
  - 'passed_by': Walked through zone without stopping.
  - 'browsed': Stopped and looked at shelf, no physical contact.
  - 'examined': Picked up an item to inspect (label, price, texture).
  - 'compared': Picked up multiple items or looked back and forth between alternatives.
- conversion_outcome (decided by what the shopper leaves with):
  - 'taken': Leaves with an item (cart, basket, or held to purchase).
  - 'returned': Picked up an item, put it back on the shelf, and leaves without it.
  - 'none': Never picked up an item.
- items_taken_count:
  - 0 if conversion_outcome is 'returned' or 'none'.
  - If conversion_outcome is 'taken', count the exact number of physical product units the shopper takes or puts into cart/basket (e.g. 1, 2, 3...). Pay close attention if a customer takes multiple items consecutively.
"""
    + BEHAVIOR_TAG_GUIDE
)


class GeminiAnalyzerService:
    """Reads one shelf clip with Gemini and turns it into an InteractionEvent."""

    def __init__(self, gemini: GeminiClient, storage: StorageService) -> None:
        self.gemini = gemini
        self.storage = storage

    def analyze_video_clip(
        self,
        video_uri: str,
        event_id: str,
        zone_id: str,
        estimated_dwell_time_seconds: Optional[int] = None,
        timestamp: Optional[str] = None,
    ) -> InteractionEvent:
        """Raises GeminiError when Gemini fails; no event is invented in that case."""
        start = time.time()
        if self.gemini.available:
            prompt = (
                f"Zone ID: {zone_id}\n"
                f"Estimated edge dwell time: {estimated_dwell_time_seconds or 'observe from video'} seconds.\n"
                "Analyze the shopper behavior in this clip."
            )
            analysis = self.gemini.generate(
                system=SYSTEM_PROMPT,
                contents=[self._video_part(video_uri), prompt],
                schema=ClipAnalysis,
                temperature=0.2,
            )
        else:
            analysis = _mock_analysis(estimated_dwell_time_seconds or 7)

        event = InteractionEvent(
            event_id=event_id,
            zone_id=zone_id,
            video_uri=video_uri,
            gemini_latency_ms=int((time.time() - start) * 1000),
            **({"timestamp": timestamp} if timestamp else {}),
            **analysis.model_dump(mode="json"),
        )
        logger.info(
            "Gemini video analysis [%s | Zone: %s]: Type=%s | Outcome=%s | Product='%s'\n"
            ">> AI behavioral summary: %s",
            event.event_id,
            event.zone_id,
            event.interaction_type.value.upper(),
            event.conversion_outcome.value.upper(),
            event.product_category_engaged,
            event.behavioral_summary,
        )
        return event

    def _video_part(self, video_uri: str) -> Any:
        from google.genai import types

        if video_uri.startswith("gs://"):
            return types.Part.from_uri(file_uri=video_uri, mime_type="video/mp4")
        return types.Part.from_bytes(data=self.storage.resolve_video_bytes(video_uri), mime_type="video/mp4")


def _mock_analysis(dwell_time: int) -> ClipAnalysis:
    """Synthetic analysis for offline development without Gemini credentials."""
    return ClipAnalysis(
        zone_dwell_time_seconds=dwell_time,
        interaction_type=InteractionType.EXAMINED,
        conversion_outcome=ConversionOutcome.RETURNED,
        items_taken_count=0,
        product_category_engaged="eye_level_organic_cereals",
        shopper_group_size=1,
        estimated_demographic=EstimatedDemographic.ADULT,
        behavioral_summary=(
            f"Shopper approached eye-level shelf, dwelled for {dwell_time}s, picked up an organic "
            "cereal box to examine the nutritional panel, hesitated, and returned it back to the "
            "shelf before exiting."
        ),
        behavior_tags=[BehaviorTag.LABEL_INSPECTION, BehaviorTag.HESITATED],
    )
