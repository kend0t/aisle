"""
Backfill behavior_tags on stored interaction events.

Asks Gemini to re-watch each event's clip and return only the behavior tags.
Dry run by default: prints the tags. Pass --write to store them with a Firestore
update() that changes only the behavior_tags field.

Usage (from the repo root):
    uv run python -m scripts.backfill_behavior_tags            # dry run
    uv run python -m scripts.backfill_behavior_tags --write    # write tags
    uv run python -m scripts.backfill_behavior_tags --only evt_1f559628d0
"""

import argparse
import logging
import sys
from typing import List, Optional

from pydantic import BaseModel

from backend_service.config import get_settings
from backend_service.errors import GeminiError
from backend_service.models.interaction_event import BehaviorTag
from backend_service.services.gemini_analyzer import BEHAVIOR_TAG_GUIDE
from backend_service.services.gemini_client import GeminiClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("aisle.backfill")

TAGS_PROMPT = (
    "You watch a short overhead clip of a shopper at a retail shelf.\n"
    "Return the behavior tags, using these definitions:\n"
    + BEHAVIOR_TAG_GUIDE
)


class TagsOnly(BaseModel):
    behavior_tags: List[BehaviorTag]


def tag_clip(gemini: GeminiClient, video_uri: str, summary: str) -> List[str]:
    from google.genai import types

    result = gemini.generate(
        system=TAGS_PROMPT,
        contents=[
            types.Part.from_uri(file_uri=video_uri, mime_type="video/mp4"),
            f"An earlier analysis of this clip said: \"{summary}\"\nReturn the behavior tags.",
        ],
        schema=TagsOnly,
        temperature=0.1,
    )
    return list(dict.fromkeys(tag.value for tag in result.behavior_tags))


def main(write: bool, only: Optional[List[str]]) -> None:
    settings = get_settings()
    gemini = GeminiClient(settings)  # also exports GOOGLE_APPLICATION_CREDENTIALS for Firestore
    if not gemini.available:
        sys.exit("Gemini is not configured: set GCP_PROJECT_ID or GEMINI_API_KEY.")

    from google.cloud import firestore

    db = firestore.Client(project=settings.GCP_PROJECT_ID, database=settings.FIRESTORE_DATABASE)
    collection = db.collection(settings.FIRESTORE_COLLECTION)

    logger.info(
        "Project %s, collection %s, mode %s",
        settings.GCP_PROJECT_ID,
        settings.FIRESTORE_COLLECTION,
        "WRITE" if write else "dry run",
    )

    failures = 0
    for doc in collection.stream():
        data = doc.to_dict()
        if only and doc.id not in only:
            continue
        video_uri = data.get("video_uri") or ""
        if not video_uri.startswith("gs://"):
            logger.warning("%s: skipped, no gs:// clip (%s)", doc.id, video_uri)
            continue
        try:
            tags = tag_clip(gemini, video_uri, data.get("behavioral_summary", ""))
        except GeminiError as e:
            failures += 1
            logger.error("%s: Gemini call failed: %s", doc.id, e)
            continue

        print(f"{doc.id}  {data.get('conversion_outcome', ''):8}  {tags}")
        print(f"    {data.get('behavioral_summary', '')[:160]}")
        if write:
            collection.document(doc.id).update({"behavior_tags": tags})

    if failures:
        logger.error("%d events failed. Re-run with --only to retry them.", failures)
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill behavior_tags on stored events")
    parser.add_argument("--write", action="store_true", help="Store the tags (default: dry run)")
    parser.add_argument("--only", nargs="*", help="Limit to these event IDs")
    args = parser.parse_args()
    main(write=args.write, only=args.only)
