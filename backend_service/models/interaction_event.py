from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


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


class InteractionEvent(BaseModel):
    """Structured interaction metric extracted from video clips via Gemini 1.5."""

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
    status: str
    event: InteractionEvent
    firestore_id: Optional[str] = None
    message: Optional[str] = None
