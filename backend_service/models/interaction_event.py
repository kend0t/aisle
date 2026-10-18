from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class InteractionType(str, Enum):
    PASSED_BY = "passed_by"
    BROWSED = "browsed"
    EXAMINED = "examined"
    COMPARED = "compared"


class ConversionOutcome(str, Enum):
    TAKEN = "taken"
    RETURNED = "returned"
    NONE = "none"


class EstimatedDemographic(str, Enum):
    YOUNG_ADULT = "young_adult"
    ADULT = "adult"
    SENIOR = "senior"
    UNKNOWN = "unknown"


class BehaviorTag(str, Enum):
    COMPARED_ALTERNATIVES = "compared_alternatives"
    LOW_SHELF_REACH = "low_shelf_reach"
    LABEL_INSPECTION = "label_inspection"
    CARRIED_BASKET = "carried_basket"
    HESITATED = "hesitated"


BEHAVIOR_TAG_VALUES = {tag.value for tag in BehaviorTag}


def filter_behavior_tags(tags: object) -> List[str]:
    """Keeps known behavior tags in first-seen order and drops anything else."""
    if not isinstance(tags, list):
        return []
    cleaned = [str(t).strip().lower() for t in tags]
    return list(dict.fromkeys(t for t in cleaned if t in BEHAVIOR_TAG_VALUES))


class ClipAnalysis(BaseModel):
    """What Gemini reads from one clip. Gemini output is shaped to this schema;
    event_id, zone_id, timestamp and provenance are added in code.

    Field order matters: Gemini writes fields in schema order, so it describes the clip
    before it classifies it.
    """

    behavioral_summary: str = Field(
        description="1-2 sentences on movement, hesitation, every item picked up, and what happened to it"
    )
    behavior_tags: List[BehaviorTag] = Field(
        description="Behaviors clearly visible in the clip; empty when none apply"
    )
    picked_up_item: bool = Field(description="True if the shopper lifted any item off the shelf")
    left_with_item: bool = Field(
        description="True if, at the end of the clip, the shopper holds an item or it is in their basket or cart"
    )
    interaction_type: InteractionType = Field(
        description=(
            "passed_by: walked through without stopping. browsed: stopped and looked, no contact. "
            "examined: picked up an item to inspect it. compared: picked up several items or "
            "looked back and forth between alternatives."
        )
    )
    conversion_outcome: ConversionOutcome = Field(
        description=(
            "taken: the shopper leaves with an item (cart, basket or hand). returned: the shopper "
            "picked up an item and put it back, and leaves without it. none: the shopper never "
            "picked up an item."
        )
    )
    items_taken_count: int = Field(
        default=0,
        ge=0,
        description="Exact count of physical product items taken/purchased (0 if returned or none, 1 or more if taken)",
    )
    zone_dwell_time_seconds: int = Field(description="Total seconds the shopper stayed in the zone")
    product_category_engaged: str = Field(description="Shelf section or product the shopper engaged with")
    shopper_group_size: int = Field(description="Number of shoppers interacting together")
    estimated_demographic: EstimatedDemographic


class InteractionEvent(BaseModel):
    """Structured interaction metric extracted from video clips via Gemini 1.5."""

    # Response model: fields with defaults are always sent, so the OpenAPI schema marks them required.
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)

    event_id: str = Field(..., description="Unique event identifier or clip ID")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 timestamp of the observed interaction",
    )
    zone_id: str = Field(..., description="Shelf or promotional zone ID (e.g. aisle_3_shelf_top)")
    zone_dwell_time_seconds: int = Field(
        ..., ge=0, description="Observed dwell duration in seconds"
    )
    interaction_type: InteractionType = Field(
        ..., description="Highest level of observed customer physical/visual engagement"
    )
    conversion_outcome: ConversionOutcome = Field(
        ..., description="Outcome of product engagement (taken, returned, none)"
    )
    items_taken_count: int = Field(
        default=0,
        ge=0,
        description="Exact count of physical product items taken/purchased (0 if returned or none, 1 or more if taken)",
    )
    product_category_engaged: str = Field(
        ..., description="Shelf section or product description engaged with"
    )
    shopper_group_size: int = Field(
        default=1, ge=1, description="Estimated number of shoppers interacting together"
    )
    estimated_demographic: str = Field(
        default="adult", description="High-level demographic estimate"
    )
    behavioral_summary: str = Field(
        ..., description="Concise qualitative narrative describing customer actions"
    )
    behavior_tags: List[BehaviorTag] = Field(
        default_factory=list,
        description="Observed shopper behaviors from the fixed BehaviorTag vocabulary",
    )
    picked_up_item: Optional[bool] = Field(
        default=None, description="Whether the shopper lifted an item off the shelf"
    )
    left_with_item: Optional[bool] = Field(
        default=None, description="Whether the shopper ends the clip holding an item"
    )

    # Verification: several independent reads of the clip, combined by majority
    reading_count: Optional[int] = Field(
        default=None, description="Number of Gemini reads combined into this record"
    )
    outcome_agreement: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Share of reads that agree with the stored outcome"
    )
    needs_review: bool = Field(
        default=False, description="True when the reads disagree or contradict themselves"
    )
    review_reasons: List[str] = Field(
        default_factory=list, description="Why a person should check this clip"
    )

    # Optional cloud provenance fields
    video_uri: Optional[str] = Field(
        default=None, description="Google Cloud Storage URI or source video path"
    )
    confidence_score: Optional[float] = Field(
        default=1.0, ge=0.0, le=1.0, description="Model confidence score"
    )
    gemini_latency_ms: Optional[int] = Field(
        default=None, description="Time spent in Gemini multimodal inference (milliseconds)"
    )
    total_latency_ms: Optional[int] = Field(
        default=None, description="Total backend processing latency (milliseconds)"
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Timestamp when record was committed to Firestore",
    )

    @field_validator("behavior_tags", mode="before")
    @classmethod
    def _keep_known_tags(cls, value: object) -> List[str]:
        return filter_behavior_tags(value)

    @model_validator(mode="after")
    def _validate_items_taken_count(self) -> "InteractionEvent":
        if self.conversion_outcome == ConversionOutcome.TAKEN and self.items_taken_count <= 0:
            self.items_taken_count = 1
        elif self.conversion_outcome != ConversionOutcome.TAKEN:
            self.items_taken_count = 0
        return self


class ProcessClipRequest(BaseModel):
    """Payload to trigger multimodal analysis on a staged video clip."""

    video_uri: str = Field(..., description="GCS URI (gs://...) or local video path")
    zone_id: str = Field(default="zone_unknown", description="Identifier of the monitored retail zone")
    estimated_dwell_time_seconds: Optional[int] = Field(
        default=None, description="Pre-computed dwell time from edge tracking"
    )
    timestamp: Optional[str] = Field(
        default=None, description="Timestamp recorded by edge node"
    )


class ProcessClipResponse(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)

    status: str
    event: InteractionEvent
    firestore_id: Optional[str] = None
    message: Optional[str] = None
