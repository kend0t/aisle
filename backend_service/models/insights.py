from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class FindingSeverity(str, Enum):
    ACT = "act"
    WATCH = "watch"
    INFO = "info"


class Finding(BaseModel):
    """One observation a store manager can act on, backed by specific clips."""

    # Response model: fields with defaults are always sent, so the OpenAPI schema marks them required.
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)

    title: str = Field(..., description="Short statement of the finding")
    action: str = Field(default="", description="One shelf-level change to try, 15 words or fewer")
    detail: str = Field(default="", description="One sentence of evidence")
    zone_id: Optional[str] = Field(default=None, description="Zone the finding applies to, if any")
    severity: FindingSeverity = Field(default=FindingSeverity.WATCH)
    evidence_event_ids: List[str] = Field(
        default_factory=list, description="Event IDs whose clips support the finding"
    )


class FindingDraft(BaseModel):
    """Gemini output for one finding; the same fields as Finding, all required."""

    title: str = Field(description="8 words or fewer, states what shoppers did")
    action: str = Field(description="One imperative of 15 words or fewer naming a change at the shelf")
    detail: str = Field(description="One sentence of evidence with the numbers")
    zone_id: Optional[str] = Field(description="Zone the finding applies to, or null")
    severity: FindingSeverity
    evidence_event_ids: List[str] = Field(description="evt_ IDs of the clips that support it")


class FindingList(BaseModel):
    findings: List[FindingDraft]


class InsightsResponse(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)

    findings: List[Finding]
    source: str = Field(..., description="'gemini' or 'rules'")
    event_count: int
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
