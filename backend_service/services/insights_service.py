import json
import logging
import re
from typing import Dict, List, Optional, Tuple

from backend_service.db.firestore_client import FirestoreRepository
from backend_service.models.insights import Finding, FindingSeverity, InsightsResponse
from backend_service.models.interaction_event import ConversionOutcome, InteractionEvent
from backend_service.services.chat_service import StoreChatService

logger = logging.getLogger(__name__)

INSIGHTS_SYSTEM_PROMPT = """You are AIsle, a retail analyst writing for a store manager.
From the store data provided, pick the 2 or 3 findings the manager should look at first.
Rank by how much a change at the shelf could raise the share of items taken.

Rules:
- Each finding must cite the event IDs (evt_...) of the clips that support it. Use only IDs present in the data.
- State numbers exactly as given in the data. Do not invent figures.
- title: 8 words or fewer, states what shoppers did.
- action: one imperative sentence, 15 words or fewer, naming a change at the shelf.
- detail: one sentence of evidence with the numbers. Plain language, no hype.
- severity: 'act' when a fix is clear and the evidence covers several clips, 'watch' when the pattern is weaker, 'info' for context.

Return ONLY a JSON object:
{
  "findings": [
    {
      "title": "<8 words or fewer>",
      "action": "<15 words or fewer>",
      "detail": "<1 sentence>",
      "zone_id": "<zone id or null>",
      "severity": "<act | watch | info>",
      "evidence_event_ids": ["evt_..."]
    }
  ]
}
"""

PHONE_PATTERN = re.compile(r"\bphone\b|photograph|picture", re.IGNORECASE)
LOW_SHELF_PATTERN = re.compile(r"bend|crouch|lower shelf|bottom shelf", re.IGNORECASE)


class InsightsService:
    """Produces ranked findings from stored events, cached until the events change."""

    def __init__(self, firestore_repo: FirestoreRepository, chat_service: StoreChatService) -> None:
        self.firestore = firestore_repo
        self.chat = chat_service
        self._cache_key: Optional[Tuple] = None
        self._cached: Optional[InsightsResponse] = None

    def get_insights(self) -> InsightsResponse:
        events = self.firestore.list_events(limit=500)
        key = tuple(sorted((e.event_id, e.created_at, tuple(e.behavior_tags)) for e in events))
        if self._cached is not None and key == self._cache_key:
            return self._cached

        response = self._generate(events)
        self._cache_key = key
        self._cached = response
        return response

    def _generate(self, events: List[InteractionEvent]) -> InsightsResponse:
        known_ids = {e.event_id for e in events}
        if events and self.chat.gemini_available:
            try:
                raw = self.chat.generate_json(INSIGHTS_SYSTEM_PROMPT, self.chat.build_grounding_context())
                findings = self._parse(raw, known_ids)
                if findings:
                    return InsightsResponse(findings=findings, source="gemini", event_count=len(events))
                logger.warning("Gemini returned no usable findings. Using rule-based findings.")
            except Exception as e:
                logger.error("Failed to generate Gemini findings (%s). Using rule-based findings.", e)

        return InsightsResponse(
            findings=self._rule_based_findings(events), source="rules", event_count=len(events)
        )

    def _parse(self, raw: str, known_ids: set) -> List[Finding]:
        data = json.loads(raw)
        findings: List[Finding] = []
        for item in data.get("findings", [])[:3]:
            finding = Finding.model_validate(item)
            finding.evidence_event_ids = [i for i in finding.evidence_event_ids if i in known_ids]
            findings.append(finding)
        return findings

    def _rule_based_findings(self, events: List[InteractionEvent]) -> List[Finding]:
        """Deterministic findings for offline mode or when Gemini fails."""
        findings: List[Finding] = []

        by_zone: Dict[str, List[InteractionEvent]] = {}
        for e in events:
            by_zone.setdefault(e.zone_id, []).append(e)

        worst: Optional[Tuple[float, str, List[InteractionEvent]]] = None
        for zone_id, zone_events in by_zone.items():
            returned = [e for e in zone_events if e.conversion_outcome == ConversionOutcome.RETURNED]
            touched = [
                e for e in zone_events
                if e.conversion_outcome in (ConversionOutcome.TAKEN, ConversionOutcome.RETURNED)
            ]
            if not touched or not returned:
                continue
            rate = len(returned) / len(touched)
            if worst is None or rate > worst[0]:
                worst = (rate, zone_id, returned)

        if worst is not None:
            rate, zone_id, returned = worst
            name = zone_id.replace("_", " ")
            findings.append(
                Finding(
                    title=f"{name.capitalize()}: {round(rate * 100)}% of picked-up items put back",
                    action="Check price labels and facings on this bay.",
                    detail=f"{len(returned)} shoppers picked up an item here and put it back.",
                    zone_id=zone_id,
                    severity=FindingSeverity.ACT if len(returned) >= 3 else FindingSeverity.WATCH,
                    evidence_event_ids=[e.event_id for e in returned],
                )
            )

        phone = [
            e for e in events
            if "phone_check" in e.behavior_tags or PHONE_PATTERN.search(e.behavioral_summary)
        ]
        if phone:
            put_back = sum(1 for e in phone if e.conversion_outcome != ConversionOutcome.TAKEN)
            findings.append(
                Finding(
                    title=f"{len(phone)} shoppers checked a phone at the shelf",
                    action="Check that shelf prices are visible and current.",
                    detail=f"{put_back} of them left without the item.",
                    severity=FindingSeverity.WATCH,
                    evidence_event_ids=[e.event_id for e in phone],
                )
            )

        low = [
            e for e in events
            if "low_shelf_reach" in e.behavior_tags or LOW_SHELF_PATTERN.search(e.behavioral_summary)
        ]
        if low:
            taken = sum(1 for e in low if e.conversion_outcome == ConversionOutcome.TAKEN)
            findings.append(
                Finding(
                    title=f"{len(low)} shoppers reached for lower shelves",
                    action="Review which products sit on the lower shelves.",
                    detail=f"{taken} of {len(low)} took an item.",
                    severity=FindingSeverity.INFO,
                    evidence_event_ids=[e.event_id for e in low],
                )
            )

        return findings[:3]
