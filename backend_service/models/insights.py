from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class FindingSeverity(str, Enum):
    ACT = "act"
    WATCH = "watch"
    INFO = "info"


class Finding(BaseModel):
    """One observation a store manager can act on, backed by specific clips."""

    title: str = Field(..., description="Short statement of the finding")
    detail: str = Field(..., description="Evidence and a suggested next step, 1-3 sentences")
    zone_id: Optional[str] = Field(default=None, description="Zone the finding applies to, if any")
    severity: FindingSeverity = Field(default=FindingSeverity.WATCH)
    evidence_event_ids: List[str] = Field(
        default_factory=list, description="Event IDs whose clips support the finding"
    )


class InsightsResponse(BaseModel):
    findings: List[Finding]
    source: str = Field(..., description="'gemini' or 'rules'")
    event_count: int
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
