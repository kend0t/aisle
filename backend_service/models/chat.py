from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str = Field(..., description="'user' or 'assistant'")
    content: str = Field(..., description="Message text content")
    timestamp: Optional[str] = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="Shopper or manager question to ask the store copilot")
    history: List[ChatMessage] = Field(default_factory=list, description="Recent conversation turns for multi-turn context")


class ChatResponse(BaseModel):
    response: str = Field(..., description="Markdown-formatted conversational response from Gemini")
    suggested_followups: List[str] = Field(
        default_factory=list,
        description="Suggested quick follow-up questions relevant to the answer",
    )
    referenced_events: List[str] = Field(
        default_factory=list,
        description="Event IDs explicitly cited or referenced in the response",
    )
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class QuickPrompt(BaseModel):
    id: str
    title: str
    prompt: str
    icon: str
    category: str
