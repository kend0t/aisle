import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend_service.config import Settings
from backend_service.errors import DataSourceError
from backend_service.models.interaction_event import (
    ConversionOutcome,
    InteractionEvent,
    InteractionType,
)

logger = logging.getLogger(__name__)

SEED_FILE = Path(__file__).resolve().parent.parent / "data" / "seed_benchmark_events.json"


class EventRepository(ABC):
    """Stores and queries interaction events."""

    @abstractmethod
    def save_event(self, event: InteractionEvent) -> str: ...

    @abstractmethod
    def get_event(self, event_id: str) -> Optional[InteractionEvent]: ...

    @abstractmethod
    def list_events(
        self,
        zone_id: Optional[str] = None,
        interaction_type: Optional[InteractionType] = None,
        outcome: Optional[ConversionOutcome] = None,
        limit: int = 50,
    ) -> List[InteractionEvent]: ...

    def get_summary(self) -> Dict[str, Any]:
        """Calculates aggregated metrics across all stored events."""
        return summarize(self.list_events(limit=500))


class FirestoreEventRepository(EventRepository):
    """Cloud Firestore. Every failure raises DataSourceError; there is no fallback data."""

    def __init__(self, settings: Settings) -> None:
        self.collection_name = settings.FIRESTORE_COLLECTION
        try:
            from google.cloud import firestore

            if settings.GOOGLE_APPLICATION_CREDENTIALS:
                self._client = firestore.Client.from_service_account_json(
                    settings.GOOGLE_APPLICATION_CREDENTIALS,
                    project=settings.GCP_PROJECT_ID,
                    database=settings.FIRESTORE_DATABASE,
                )
            else:
                self._client = firestore.Client(
                    project=settings.GCP_PROJECT_ID,
                    database=settings.FIRESTORE_DATABASE,
                )
        except Exception as e:
            raise DataSourceError("Firestore", "connection", e) from e
        logger.info(
            "Using Firestore database '%s', collection '%s'",
            settings.FIRESTORE_DATABASE,
            self.collection_name,
        )

    def _collection(self):
        return self._client.collection(self.collection_name)

    def save_event(self, event: InteractionEvent) -> str:
        try:
            self._collection().document(event.event_id).set(event.model_dump(mode="json"))
        except Exception as e:
            raise DataSourceError("Firestore", "write", e) from e
        logger.info("Saved event %s to Firestore", event.event_id)
        return event.event_id

    def get_event(self, event_id: str) -> Optional[InteractionEvent]:
        try:
            snapshot = self._collection().document(event_id).get()
        except Exception as e:
            raise DataSourceError("Firestore", "read", e) from e
        return InteractionEvent.model_validate(snapshot.to_dict()) if snapshot.exists else None

    def list_events(
        self,
        zone_id: Optional[str] = None,
        interaction_type: Optional[InteractionType] = None,
        outcome: Optional[ConversionOutcome] = None,
        limit: int = 50,
    ) -> List[InteractionEvent]:
        query = self._collection()
        if zone_id:
            query = query.where("zone_id", "==", zone_id)
        if interaction_type:
            query = query.where("interaction_type", "==", interaction_type.value)
        if outcome:
            query = query.where("conversion_outcome", "==", outcome.value)

        try:
            docs = list(query.limit(limit).stream())
        except Exception as e:
            raise DataSourceError("Firestore", "query", e) from e

        events: List[InteractionEvent] = []
        for doc in docs:
            try:
                events.append(InteractionEvent.model_validate(doc.to_dict()))
            except Exception as parse_err:
                logger.warning("Skipping unreadable document %s: %s", doc.id, parse_err)
        return events


class InMemoryEventRepository(EventRepository):
    """The bundled benchmark events, held in memory. Used when AISLE_DATA_SOURCE=seed."""

    def __init__(self) -> None:
        with open(SEED_FILE, "r") as f:
            records = json.load(f)
        self._events: Dict[str, Dict[str, Any]] = {item["event_id"]: item for item in records}
        logger.info("Using %d seed events from %s (in memory)", len(records), SEED_FILE.name)

    def save_event(self, event: InteractionEvent) -> str:
        self._events[event.event_id] = event.model_dump(mode="json")
        return event.event_id

    def get_event(self, event_id: str) -> Optional[InteractionEvent]:
        record = self._events.get(event_id)
        return InteractionEvent.model_validate(record) if record else None

    def list_events(
        self,
        zone_id: Optional[str] = None,
        interaction_type: Optional[InteractionType] = None,
        outcome: Optional[ConversionOutcome] = None,
        limit: int = 50,
    ) -> List[InteractionEvent]:
        events: List[InteractionEvent] = []
        for record in self._events.values():
            if zone_id and record.get("zone_id") != zone_id:
                continue
            if interaction_type and record.get("interaction_type") != interaction_type.value:
                continue
            if outcome and record.get("conversion_outcome") != outcome.value:
                continue
            events.append(InteractionEvent.model_validate(record))
            if len(events) >= limit:
                break
        return events


def build_repository(settings: Settings) -> EventRepository:
    if settings.AISLE_DATA_SOURCE == "seed":
        return InMemoryEventRepository()
    return FirestoreEventRepository(settings)


def _mean(values: List[int]) -> Optional[int]:
    return round(sum(values) / len(values)) if values else None


def summarize(events: List[InteractionEvent]) -> Dict[str, Any]:
    """Aggregated metrics. Telemetry holds only measured values; unmeasured ones are None."""
    total = len(events)
    if total == 0:
        return {
            "total_interactions": 0,
            "conversion_rate": 0.0,
            "abandonment_rate": 0.0,
            "average_dwell_time_seconds": 0.0,
            "breakdown_by_outcome": {},
            "breakdown_by_type": {},
        }

    taken_count = sum(1 for e in events if e.conversion_outcome == ConversionOutcome.TAKEN)
    returned_count = sum(1 for e in events if e.conversion_outcome == ConversionOutcome.RETURNED)
    total_dwell = sum(e.zone_dwell_time_seconds for e in events)

    # Abandonment = returned / (taken + returned)
    physical_touches = taken_count + returned_count
    abandonment_rate = round((returned_count / physical_touches) * 100, 1) if physical_touches > 0 else 0.0
    conversion_rate = round((taken_count / total) * 100, 1)
    avg_dwell = round(total_dwell / total, 1)

    breakdown_outcome: Dict[str, int] = {}
    breakdown_type: Dict[str, int] = {}
    breakdown_demographic: Dict[str, int] = {}
    zone_stats: Dict[str, Dict[str, Any]] = {}

    for e in events:
        out_val = e.conversion_outcome.value
        type_val = e.interaction_type.value
        demo_val = e.estimated_demographic
        breakdown_outcome[out_val] = breakdown_outcome.get(out_val, 0) + 1
        breakdown_type[type_val] = breakdown_type.get(type_val, 0) + 1
        breakdown_demographic[demo_val] = breakdown_demographic.get(demo_val, 0) + 1

        z = zone_stats.setdefault(
            e.zone_id,
            {"interactions": 0, "taken": 0, "returned": 0, "none": 0, "total_dwell": 0, "products": set()},
        )
        z["interactions"] += 1
        z["total_dwell"] += e.zone_dwell_time_seconds
        z[out_val] += 1
        if e.product_category_engaged:
            z["products"].add(e.product_category_engaged)

    formatted_zones = []
    for zid, z in zone_stats.items():
        z_total = z["interactions"]
        formatted_zones.append({
            "zone_id": zid,
            "display_name": zid.replace("_", " ").title(),
            "interactions": z_total,
            "conversion_rate": round((z["taken"] / z_total) * 100, 1),
            "average_dwell": round(z["total_dwell"] / z_total, 1),
            "taken_count": z["taken"],
            "returned_count": z["returned"],
            "sample_products": list(z["products"])[:3],
        })

    return {
        "total_interactions": total,
        "conversion_rate": conversion_rate,
        "abandonment_rate": abandonment_rate,
        "average_dwell_time_seconds": avg_dwell,
        "breakdown_by_outcome": breakdown_outcome,
        "breakdown_by_type": breakdown_type,
        "breakdown_by_demographic": breakdown_demographic,
        "zones": formatted_zones,
        "telemetry": {
            "mean_gemini_latency_ms": _mean([e.gemini_latency_ms for e in events if e.gemini_latency_ms]),
            "mean_total_latency_ms": _mean([e.total_latency_ms for e in events if e.total_latency_ms]),
        },
    }
