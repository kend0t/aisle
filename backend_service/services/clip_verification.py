"""Combines several Gemini reads of one clip and checks each read against itself.

One read is a sample, not a measurement: the same clip can come back "taken" once and
"returned" the next time. The stored record is the majority of several reads, and a
clip is flagged for a person when the reads disagree or a read contradicts itself.
"""

from collections import Counter
from dataclasses import dataclass, field
from statistics import median
from typing import List

from backend_service.models.interaction_event import ClipAnalysis, ConversionOutcome


@dataclass
class Consensus:
    analysis: ClipAnalysis
    reading_count: int
    outcome_agreement: float
    review_reasons: List[str] = field(default_factory=list)

    @property
    def needs_review(self) -> bool:
        return bool(self.review_reasons)


def expected_outcome(picked_up_item: bool, left_with_item: bool) -> ConversionOutcome:
    """The outcome the two observations imply."""
    if not picked_up_item:
        return ConversionOutcome.NONE
    return ConversionOutcome.TAKEN if left_with_item else ConversionOutcome.RETURNED


def consistency_issues(analysis: ClipAnalysis) -> List[str]:
    """Contradictions between the outcome and what the same read observed."""
    implied = expected_outcome(analysis.picked_up_item, analysis.left_with_item)
    if implied == analysis.conversion_outcome:
        return []
    observed = {
        ConversionOutcome.NONE: "no item left the shelf",
        ConversionOutcome.TAKEN: "the shopper left with an item",
        ConversionOutcome.RETURNED: "the item was picked up and not kept",
    }[implied]
    return [f"Outcome says {_outcome_words(analysis.conversion_outcome)}, but {observed}"]


def combine(reads: List[ClipAnalysis]) -> Consensus:
    """Majority outcome; tags seen in most reads; median dwell; reasons to review."""
    if not reads:
        raise ValueError("combine() needs at least one read")

    votes = Counter(r.conversion_outcome for r in reads)
    outcome, majority = votes.most_common(1)[0]
    representative = next(r for r in reads if r.conversion_outcome == outcome)

    tag_votes = Counter(tag for r in reads for tag in set(r.behavior_tags))
    tags = [tag for tag in representative.behavior_tags if tag_votes[tag] * 2 > len(reads)]
    tags += [tag for tag, n in tag_votes.items() if n * 2 > len(reads) and tag not in tags]

    analysis = representative.model_copy(
        update={
            "behavior_tags": tags,
            "zone_dwell_time_seconds": int(median(r.zone_dwell_time_seconds for r in reads)),
            "items_taken_count": int(median(r.items_taken_count for r in reads if r.conversion_outcome == outcome)),
        }
    )

    reasons: List[str] = []
    if majority < len(reads):
        reasons.append(f"Readings disagreed ({majority} of {len(reads)} agree)")
    reasons += consistency_issues(analysis)

    return Consensus(
        analysis=analysis,
        reading_count=len(reads),
        outcome_agreement=round(majority / len(reads), 2),
        review_reasons=reasons,
    )


def _outcome_words(outcome: ConversionOutcome) -> str:
    return {"taken": "taken", "returned": "put back", "none": "no pick-up"}[outcome.value]
