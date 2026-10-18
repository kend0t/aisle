from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ChatMessage(BaseModel):
    role: str = Field(..., description="'user' or 'assistant'")
    content: str = Field(..., description="Message text content")
    timestamp: Optional[str] = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="Shopper or manager question to ask the store copilot")
    history: List[ChatMessage] = Field(default_factory=list, description="Recent conversation turns for multi-turn context")


class ChatResponse(BaseModel):
    # Response model: fields with defaults are always sent, so the OpenAPI schema marks them required.
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)

    response: str = Field(..., description="Markdown-formatted conversational response from Gemini")
    suggested_followups: List[str] = Field(
        default_factory=list,
        description="Suggested quick follow-up questions relevant to the answer",
    )
    referenced_events: List[str] = Field(
        default_factory=list,
        description="Event IDs explicitly cited or referenced in the response",
    )
    tool_calls: List[str] = Field(
        default_factory=list,
        description="Counting tools Copilot called to get its numbers, in call order",
    )
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class CopilotReply(BaseModel):
    """Gemini output for one Copilot answer."""

    response: str = Field(description="Markdown answer with bold figures and evt_ citations")
    suggested_followups: List[str] = Field(description="Up to 3 short follow-up questions")
    referenced_events: List[str] = Field(description="evt_ IDs cited in the answer")


class QuickPrompt(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)

    id: str
    title: str
    prompt: str
    icon: str
    category: str
