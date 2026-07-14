from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.models import ChatRole


class ChatSessionCreate(BaseModel):
    # Link this chat to a specific Live Verify incident so the AI chatbot can
    # pull that incident's RiskAssessment history as grounding context
    # (flowchart step 29). Omit for general/standalone support chat.
    verification_session_id: Optional[int] = None
    language: str = Field(default="en", description='"en", "fil", or "tgl" (Taglish)')


class ChatSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    verification_session_id: Optional[int]
    title: Optional[str]
    language: str
    created_at: datetime
    updated_at: datetime


class ChatMessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=4000)
    # Lets the frontend override the session's default language per-message,
    # e.g. the user suddenly switches from English to Filipino mid-conversation.
    language: Optional[str] = None


class ChatMessageResponse(BaseModel):
    """A single chat turn, including the metadata needed to audit/debug AI answers."""
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int
    chat_session_id: int
    role: ChatRole
    content: str
    language: Optional[str]
    model_used: Optional[str]
    source_incident_ids: Optional[list[int]]
    latency_ms: Optional[int]
    created_at: datetime


class ChatLogResponse(BaseModel):
    """
    Full chat log for a session plus its metadata - what 'fetch chat logs
    with metadata' returns. Wraps the session envelope around its messages
    so the frontend doesn't need a second round trip to show language/title/etc.
    """
    session: ChatSessionResponse
    messages: list[ChatMessageResponse]
