from sqlalchemy.orm import Session

from app.core.exceptions import ResourceNotFoundException
from app.models.models import (
    ChatSession, ChatMessage, ChatRole, VerificationSession, User,
)
from app.schemas.chat import ChatSessionCreate, ChatMessageCreate
from app.services.ai_models import localized_chatbot


def create_session(db: Session, user: User, payload: ChatSessionCreate) -> ChatSession:
    verification_session = None
    if payload.verification_session_id is not None:
        verification_session = db.query(VerificationSession).filter(
            VerificationSession.id == payload.verification_session_id,
            VerificationSession.user_id == user.id,
        ).first()
        if not verification_session:
            raise ResourceNotFoundException(
                f"Verification session {payload.verification_session_id} not found"
            )

    title = "Incident explanation" if verification_session else "Centry AI Support"
    chat_session = ChatSession(
        user_id=user.id,
        verification_session_id=payload.verification_session_id,
        title=title,
        language=payload.language,
    )
    db.add(chat_session)
    db.commit()
    db.refresh(chat_session)
    return chat_session


def _get_owned_session(db: Session, user_id: int, chat_session_id: int) -> ChatSession:
    chat_session = db.query(ChatSession).filter(
        ChatSession.id == chat_session_id,
        ChatSession.user_id == user_id,
    ).first()
    if not chat_session:
        raise ResourceNotFoundException(f"Chat session {chat_session_id} not found")
    return chat_session


def _build_incident_context(chat_session: ChatSession) -> tuple[str | None, list[int]]:
    verification_session = chat_session.verification_session
    if not verification_session or not verification_session.assessments:
        return None, []

    latest = verification_session.assessments[-1]
    all_markers = sorted({
        marker
        for assessment in verification_session.assessments
        for marker in (assessment.detected_scam_markers or [])
    })
    summary = (
        f"call risk level {latest.aggregated_risk_level.value} "
        f"(score {latest.aggregated_risk_score}/100)"
        + (f", markers detected: {', '.join(all_markers)}" if all_markers else "")
    )
    source_ids = [a.id for a in verification_session.assessments]
    return summary, source_ids


async def send_message(db: Session, user: User, chat_session_id: int,
                        payload: ChatMessageCreate) -> ChatMessage:
    chat_session = _get_owned_session(db, user.id, chat_session_id)
    language = payload.language or chat_session.language

    user_message = ChatMessage(
        chat_session_id=chat_session.id,
        role=ChatRole.USER,
        content=payload.content,
        language=language,
    )
    db.add(user_message)
    db.commit()

    incident_summary, source_incident_ids = _build_incident_context(chat_session)

    reply = await localized_chatbot.generate_reply(
        payload.content,
        language=language,
        incident_summary=incident_summary,
    )

    assistant_message = ChatMessage(
        chat_session_id=chat_session.id,
        role=ChatRole.ASSISTANT,
        content=reply.content,
        language=reply.language,
        model_used=reply.model_version,
        source_incident_ids=source_incident_ids or None,
        latency_ms=reply.latency_ms,
    )
    db.add(assistant_message)
    db.commit()
    db.refresh(assistant_message)
    return assistant_message


def get_chat_log(db: Session, user_id: int, chat_session_id: int) -> ChatSession:
    """Fetch a chat session with its full message history + metadata."""
    return _get_owned_session(db, user_id, chat_session_id)


def list_sessions(db: Session, user_id: int) -> list[ChatSession]:
    return (
        db.query(ChatSession)
        .filter(ChatSession.user_id == user_id)
        .order_by(ChatSession.updated_at.desc())
        .all()
    )
