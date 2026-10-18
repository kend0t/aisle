"""Re-reads every stored clip with the verified reader and updates the records in place.

Dry run by default: prints the old and new outcome for each clip and changes nothing.

    uv run python -m scripts.reread_clips                      # dry run against AISLE_DATA_SOURCE
    uv run python -m scripts.reread_clips --write              # save the new records
    uv run python -m scripts.reread_clips --seed-out backend_service/data/seed_benchmark_events.json

Each record keeps its event_id, timestamp, zone, video_uri, created_at and total_latency_ms;
the analysis fields, behavior tags and verification fields are replaced.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List

from backend_service.config import get_settings
from backend_service.db.firestore_client import build_repository
from backend_service.errors import ServiceError
from backend_service.models.interaction_event import InteractionEvent
from backend_service.services.gemini_analyzer import GeminiAnalyzerService
from backend_service.services.gemini_client import GeminiClient
from backend_service.services.storage_service import StorageService

KEEP = {"event_id", "timestamp", "zone_id", "video_uri", "created_at", "total_latency_ms"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--write", action="store_true", help="Save the new records to the data source")
    parser.add_argument("--seed-out", help="Also write the new records to this seed JSON file")
    parser.add_argument("--only", nargs="*", help="Limit to these event IDs")
    args = parser.parse_args()

    settings = get_settings()
    gemini = GeminiClient(settings)
    if not gemini.available:
        print("Gemini is not configured; nothing to re-read.", file=sys.stderr)
        return 1
    repo = build_repository(settings)
    analyzer = GeminiAnalyzerService(
        gemini, StorageService(settings, use_gcs=settings.AISLE_DATA_SOURCE == "firestore"), settings.READS_PER_CLIP
    )

    updated: List[InteractionEvent] = []
    failures = 0
    print(f"{'event':16} {'before':9} {'after':9} agree  review")
    for old in repo.list_events(limit=500):
        if args.only and old.event_id not in args.only:
            continue
        if not old.video_uri:
            continue
        try:
            fresh = analyzer.analyze_video_clip(
                video_uri=old.video_uri,
                event_id=old.event_id,
                zone_id=old.zone_id,
                estimated_dwell_time_seconds=old.zone_dwell_time_seconds,
                timestamp=old.timestamp,
            )
        except ServiceError as e:
            failures += 1
            print(f"{old.event_id:16} failed: {e}")
            continue
        event = fresh.model_copy(update={k: getattr(old, k) for k in KEEP})
        updated.append(event)
        print(
            f"{event.event_id:16} {old.conversion_outcome.value:9} {event.conversion_outcome.value:9} "
            f"{event.outcome_agreement:<6} {'; '.join(event.review_reasons)}"
        )
        if args.write:
            repo.save_event(event)

    changed = sum(
        1 for e in updated if e.conversion_outcome != repo.get_event(e.event_id).conversion_outcome
    ) if not args.write else None
    print(f"\n{len(updated)} re-read, {failures} failed" + (f", {changed} outcomes would change" if changed is not None else ", saved"))

    if args.seed_out:
        records = sorted((e.model_dump(mode="json") for e in updated), key=lambda r: r["event_id"])
        Path(args.seed_out).write_text(json.dumps(records, indent=2) + "\n")
        print(f"Wrote {len(records)} records to {args.seed_out}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
