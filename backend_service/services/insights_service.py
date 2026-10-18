import logging
import threading
from typing import Dict, List, Optional, Tuple

from backend_service.db.firestore_client import EventRepository
from backend_service.errors import GeminiError
from backend_service.models.insights import Finding, FindingList, FindingSeverity, InsightsResponse
from backend_service.models.interaction_event import BehaviorTag, ConversionOutcome, InteractionEvent
from backend_service.services.chat_service import StoreChatService
from backend_service.services.gemini_client import GeminiClient

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
- zone_id: the zone the finding applies to, or null when it spans zones.
"""


class InsightsService:
    """Produces ranked findings from stored events, cached until the events change."""

    def __init__(self, repo: EventRepository, chat: StoreChatService, gemini: GeminiClient) -> None:
        self.repo = repo
        self.chat = chat
        self.gemini = gemini
        self._cache_key: Optional[Tuple] = None
        self._cached: Optional[InsightsResponse] = None
        # A Gemini run takes about 30 s; concurrent requests wait for it instead of starting their own.
        self._lock = threading.Lock()

    def get_insights(self) -> InsightsResponse:
        events = self.repo.list_events(limit=500)
        key = tuple(sorted((e.event_id, e.created_at, tuple(e.behavior_tags)) for e in events))
        with self._lock:
            if self._cached is None or key != self._cache_key:
                self._cached = self._generate(events)
                self._cache_key = key
            return self._cached

    def _generate(self, events: List[InteractionEvent]) -> InsightsResponse:
        known_ids = {e.event_id for e in events}
        if events and self.gemini.available:
            try:
                result = self.gemini.generate(
                    system=INSIGHTS_SYSTEM_PROMPT,
                    contents=[self.chat.build_grounding_context(events)],
                    schema=FindingList,
                    temperature=0.3,
                )
                findings = [
                    Finding(
                        **draft.model_dump(exclude={"evidence_event_ids"}),
                        evidence_event_ids=[i for i in draft.evidence_event_ids if i in known_ids],
                    )
                    for draft in result.findings[:3]
                ]
                if findings:
                    return InsightsResponse(findings=findings, source="gemini", event_count=len(events))
                logger.warning("Gemini returned no findings. Using rule-based findings.")
            except GeminiError as e:
                # Rule-based findings are labelled as such in the UI, so this fallback is visible.
                logger.error("Gemini findings failed (%s). Using rule-based findings.", e)

        return InsightsResponse(
            findings=self._rule_based_findings(events), source="rules", event_count=len(events)
        )

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
            if BehaviorTag.PHONE_CHECK in e.behavior_tags
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
            if BehaviorTag.LOW_SHELF_REACH in e.behavior_tags
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
