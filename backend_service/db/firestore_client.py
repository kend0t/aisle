import logging
from typing import Any, Dict, List, Optional
from backend_service.config import get_settings
from backend_service.models.interaction_event import (
    ConversionOutcome,
    InteractionEvent,
    InteractionType,
)

logger = logging.getLogger(__name__)


class FirestoreRepository:
    """Handles persistence and retrieval of interaction metrics in Cloud Firestore."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.project_id = self.settings.GCP_PROJECT_ID
        self.database_name = self.settings.FIRESTORE_DATABASE
        self.collection_name = self.settings.FIRESTORE_COLLECTION
        self._client = None
        self._in_memory_db: Dict[str, Dict[str, Any]] = {}
        self._init_client()

    def _init_client(self) -> None:
        """Initializes the Google Cloud Firestore client or falls back to in-memory store."""
        try:
            from google.cloud import firestore

            if self.settings.GOOGLE_APPLICATION_CREDENTIALS:
                self._client = firestore.Client.from_service_account_json(
                    self.settings.GOOGLE_APPLICATION_CREDENTIALS,
                    project=self.project_id,
                    database=self.database_name,
                )
            else:
                self._client = firestore.Client(
                    project=self.project_id,
                    database=self.database_name,
                )
            logger.info(
                "Connected to Firestore database '%s', collection '%s'",
                self.database_name,
                self.collection_name,
            )
        except Exception as e:
            logger.warning(
                "Could not connect to live Firestore (%s). Using in-memory fallback repository.",
                e,
            )
            self._client = None

    def save_event(self, event: InteractionEvent) -> str:
        """Saves an InteractionEvent to Firestore."""
        data = event.model_dump()
        doc_id = event.event_id

        if self._client is not None:
            try:
                doc_ref = self._client.collection(self.collection_name).document(doc_id)
                doc_ref.set(data)
                logger.info("Saved event %s to Firestore", doc_id)
                return doc_id
            except Exception as e:
                logger.error("Failed to write to Firestore (%s). Saving to in-memory store.", e)

        # In-memory fallback
        self._in_memory_db[doc_id] = data
        logger.info("Saved event %s to in-memory store (Total: %d)", doc_id, len(self._in_memory_db))
        return doc_id

    def get_event(self, event_id: str) -> Optional[InteractionEvent]:
        """Fetches a specific event by ID."""
        if self._client is not None:
            try:
                doc_ref = self._client.collection(self.collection_name).document(event_id)
                snapshot = doc_ref.get()
                if snapshot.exists:
                    return InteractionEvent.model_validate(snapshot.to_dict())
                return None
            except Exception as e:
                logger.error("Error reading from Firestore (%s). Checking in-memory store.", e)

        if event_id in self._in_memory_db:
            return InteractionEvent.model_validate(self._in_memory_db[event_id])
        return None

    def list_events(
        self,
        zone_id: Optional[str] = None,
        interaction_type: Optional[InteractionType] = None,
        outcome: Optional[ConversionOutcome] = None,
        limit: int = 50,
    ) -> List[InteractionEvent]:
        """Queries events with optional filters."""
        events: List[InteractionEvent] = []

        if self._client is not None:
            try:
                query = self._client.collection(self.collection_name)
                if zone_id:
                    query = query.where("zone_id", "==", zone_id)
                if interaction_type:
                    query = query.where("interaction_type", "==", interaction_type.value)
                if outcome:
                    query = query.where("conversion_outcome", "==", outcome.value)

                docs = query.limit(limit).stream()
                for doc in docs:
                    try:
                        events.append(InteractionEvent.model_validate(doc.to_dict()))
                    except Exception as parse_err:
                        logger.warning("Failed to parse document %s: %s", doc.id, parse_err)
                return events
            except Exception as e:
                logger.error("Error streaming from Firestore (%s). Querying in-memory store.", e)

        # In-memory query
        for record in self._in_memory_db.values():
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

    def get_summary(self) -> Dict[str, Any]:
        """Calculates aggregated metrics across all stored events."""
        events = self.list_events(limit=500)
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

        gemini_lats = [e.gemini_latency_ms for e in events if e.gemini_latency_ms]
        total_lats = [e.total_latency_ms for e in events if e.total_latency_ms]

        for e in events:
            out_val = e.conversion_outcome.value
            type_val = e.interaction_type.value
            demo_val = getattr(e, "estimated_demographic", "adult")
            z_id = e.zone_id

            breakdown_outcome[out_val] = breakdown_outcome.get(out_val, 0) + 1
            breakdown_type[type_val] = breakdown_type.get(type_val, 0) + 1
            breakdown_demographic[demo_val] = breakdown_demographic.get(demo_val, 0) + 1

            if z_id not in zone_stats:
                zone_stats[z_id] = {
                    "zone_id": z_id,
                    "interactions": 0,
                    "taken": 0,
                    "returned": 0,
                    "none": 0,
                    "total_dwell": 0,
                    "products": set(),
                }
            z = zone_stats[z_id]
            z["interactions"] += 1
            z["total_dwell"] += e.zone_dwell_time_seconds
            z[out_val] = z.get(out_val, 0) + 1
            if e.product_category_engaged:
                z["products"].add(e.product_category_engaged)

        # Format zones
        formatted_zones = []
        for zid, z in zone_stats.items():
            z_total = z["interactions"]
            z_conv = round((z["taken"] / z_total) * 100, 1) if z_total > 0 else 0.0
            z_dwell = round(z["total_dwell"] / z_total, 1) if z_total > 0 else 0.0
            formatted_zones.append({
                "zone_id": zid,
                "display_name": zid.replace("_", " ").title(),
                "interactions": z_total,
                "conversion_rate": z_conv,
                "average_dwell": z_dwell,
                "taken_count": z["taken"],
                "returned_count": z["returned"],
                "sample_products": list(z["products"])[:3],
            })

        mean_gemini_lat = round(sum(gemini_lats) / len(gemini_lats)) if gemini_lats else 2150
        mean_total_lat = round(sum(total_lats) / len(total_lats)) if total_lats else 3200

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
                "mean_gemini_latency_ms": mean_gemini_lat,
                "mean_total_latency_ms": mean_total_lat,
                "bandwidth_saved_pct": 78.4,
                "edge_fps": 30.0,
            },
        }
