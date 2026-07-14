from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.deps import get_current_user
from app.models.models import User
from app.schemas.chat import (
    ChatSessionCreate, ChatSessionResponse, ChatMessageCreate,
    ChatMessageResponse, ChatLogResponse,
)
from app.services import chat_service

router = APIRouter(prefix="/api/v1/chat", tags=["Centry AI Chatbot"])


@router.post("/sessions", response_model=ChatSessionResponse, status_code=status.HTTP_201_CREATED)
def create_chat_session(payload: ChatSessionCreate,
                         current_user: User = Depends(get_current_user),
                         db: Session = Depends(get_db)):
    """
    "Open Centry AI Chat for incident details". Pass
    `verification_session_id` to scope this chat to a specific Live Verify
    incident, or omit it for general support.
    """
    return chat_service.create_session(db, current_user, payload)


@router.get("/sessions", response_model=list[ChatSessionResponse])
def list_chat_sessions(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return chat_service.list_sessions(db, current_user.id)


@router.post("/sessions/{session_id}/messages", response_model=ChatMessageResponse,
             status_code=status.HTTP_201_CREATED)
async def send_chat_message(session_id: int,
                             payload: ChatMessageCreate,
                             current_user: User = Depends(get_current_user),
                             db: Session = Depends(get_db)):
    """
    Send a message to the Centry AI Chatbot. The backend pulls incident context 
    for the linked Live Verify session (if any), gets a localized explanation 
    from the chatbot model, and returns the assistant's reply message 
    (the user's own message is also persisted).
    """
    return await chat_service.send_message(db, current_user, session_id, payload)


@router.get("/sessions/{session_id}/logs", response_model=ChatLogResponse)
def fetch_chat_logs(session_id: int,
                     current_user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    """
    Fetch the full chat log for a session, with metadata (language used per
    message, which model answered, latency, and which incident/risk-
    assessment records were used as grounding context). Powers the
    "Post-Incident Review" screen.
    """
    chat_session = chat_service.get_chat_log(db, current_user.id, session_id)
    return ChatLogResponse(session=chat_session, messages=chat_session.messages)
