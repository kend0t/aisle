"""Counting tools Copilot calls instead of doing arithmetic in the prompt.

Every number in a Copilot answer comes from one of these functions, so it matches the
dashboard: percentages are of shoppers who picked an item up, as in the shelf funnel.
"""

from typing import Any, Callable, Dict, List, Optional

from backend_service.db import EventRepository
from backend_service.models.interaction_event import BehaviorTag, InteractionEvent

ZONE_IDS = ("left_bay_cereal", "right_bay_snacks")
OUTCOMES = ("taken", "returned", "none")
MAX_EVENTS = 500


def _percent(part: int, whole: int) -> Optional[float]:
    return round(100 * part / whole, 1) if whole else None


def _filter(
    events: List[InteractionEvent],
    zone_id: Optional[str] = None,
    behavior: Optional[str] = None,
    outcome: Optional[str] = None,
) -> List[InteractionEvent]:
    return [
        e
        for e in events
        if (not zone_id or e.zone_id == zone_id)
        and (not behavior or behavior in {t.value for t in e.behavior_tags})
        and (not outcome or e.conversion_outcome.value == outcome)
    ]


def outcome_counts(events: List[InteractionEvent]) -> Dict[str, Any]:
    taken = sum(e.conversion_outcome.value == "taken" for e in events)
    put_back = sum(e.conversion_outcome.value == "returned" for e in events)
    picked_up = taken + put_back
    units = sum(max(1, e.items_taken_count) for e in events if e.conversion_outcome.value == "taken")
    return {
        "stopped": len(events),
        "picked_up": picked_up,
        "taken": taken,
        "units_taken": units,
        "put_back": put_back,
        "no_pickup": len(events) - picked_up,
        "taken_pct_of_picked_up": _percent(taken, picked_up),
        "put_back_pct_of_picked_up": _percent(put_back, picked_up),
    }


class CopilotTools:
    """Read-only queries over the stored clips, exposed to Gemini as function calls."""

    def __init__(self, repo: EventRepository) -> None:
        self.repo = repo

    def _events(self) -> List[InteractionEvent]:
        return self.repo.list_events(limit=MAX_EVENTS)

    def count_outcomes(
        self, zone_id: Optional[str] = None, behavior: Optional[str] = None, outcome: Optional[str] = None
    ) -> Dict[str, Any]:
        """Counts shoppers who stopped, picked up, took, put back, or did not pick up an item.

        Args:
            zone_id: Optional zone: left_bay_cereal or right_bay_snacks.
            behavior: Optional behavior tag the clips must show, for example label_inspection.
            outcome: Optional outcome the clips must have: taken, returned, or none.
        """
        return outcome_counts(_filter(self._events(), zone_id, behavior, outcome))

    def count_behaviors(self, zone_id: Optional[str] = None, outcome: Optional[str] = None) -> Dict[str, Any]:
        """Counts each behavior tag and splits it by outcome. A clip can show several behaviors.

        Args:
            zone_id: Optional zone: left_bay_cereal or right_bay_snacks.
            outcome: Optional outcome the clips must have: taken, returned, or none.
        """
        events = _filter(self._events(), zone_id, None, outcome)
        result = {}
        for tag in BehaviorTag:
            tagged = [e for e in events if tag in e.behavior_tags]
            if tagged:
                result[tag.value] = outcome_counts(tagged)
        return {"clips": len(events), "behaviors": result}

    def list_clips(
        self,
        zone_id: Optional[str] = None,
        behavior: Optional[str] = None,
        outcome: Optional[str] = None,
        limit: int = 8,
    ) -> Dict[str, Any]:
        """Lists matching clips with their ID, zone, outcome, behaviors, dwell and a short summary.

        Args:
            zone_id: Optional zone: left_bay_cereal or right_bay_snacks.
            behavior: Optional behavior tag the clips must show.
            outcome: Optional outcome: taken, returned, or none.
            limit: Maximum number of clips to return, up to 20.
        """
        matches = _filter(self._events(), zone_id, behavior, outcome)
        return {
            "total_matches": len(matches),
            "clips": [
                {
                    "event_id": e.event_id,
                    "zone_id": e.zone_id,
                    "outcome": e.conversion_outcome.value,
                    "behaviors": [t.value for t in e.behavior_tags],
                    "dwell_seconds": e.zone_dwell_time_seconds,
                    "summary": e.behavioral_summary[:160],
                }
                for e in matches[: max(1, min(int(limit), 20))]
            ],
        }

    def get_clip(self, event_id: str) -> Dict[str, Any]:
        """Returns the full stored record for one clip.

        Args:
            event_id: The clip ID, for example evt_1f559628d0.
        """
        event = self.repo.get_event(event_id)
        if event is None:
            return {"error": f"No clip {event_id}"}
        return event.model_dump(
            mode="json",
            exclude={"video_uri", "created_at", "confidence_score", "estimated_demographic"},
        )

    def as_functions(self) -> Dict[str, Callable[..., Dict[str, Any]]]:
        return {
            "count_outcomes": self.count_outcomes,
            "count_behaviors": self.count_behaviors,
            "list_clips": self.list_clips,
            "get_clip": self.get_clip,
        }
