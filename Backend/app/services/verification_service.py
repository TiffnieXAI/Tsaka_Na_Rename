import asyncio

from sqlalchemy.orm import Session

from app.core.exceptions import ResourceNotFoundException
from app.models.models import (
    VerificationSession, RiskAssessment, VerificationStatus, User,
)
from app.services.ai_models import voice_biometrics, semantic_intent
from app.services import risk_engine_service


def start_session(db: Session, user: User, caller_label: str | None = None) -> VerificationSession:
    session = VerificationSession(
        user_id=user.id,
        status=VerificationStatus.ACTIVE,
        caller_label=caller_label,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


async def analyze_audio_window(db: Session, session: VerificationSession, audio_chunk: bytes) -> RiskAssessment:
    voice_result, semantic_result = await asyncio.gather(
        voice_biometrics.analyze(audio_chunk),
        semantic_intent.analyze(audio_chunk),
    )

    aggregated_score, aggregated_level, _recommend_block = risk_engine_service.aggregate(
        voice_result, semantic_result
    )

    next_sequence = len(session.assessments)
    assessment = RiskAssessment(
        session_id=session.id,
        sequence_number=next_sequence,
        voice_authenticity_score=voice_result.authenticity_score,
        voice_model_confidence=voice_result.confidence,
        semantic_scam_score=semantic_result.scam_score,
        detected_scam_markers=semantic_result.detected_markers,
        transcript_snippet=semantic_result.transcript_snippet,
        aggregated_risk_score=aggregated_score,
        aggregated_risk_level=aggregated_level,
    )
    db.add(assessment)

    # Keep the session's denormalized "latest" snapshot in sync for
    # dashboard list views (avoids a join+aggregate on every page load).
    session.latest_risk_score = aggregated_score
    session.latest_risk_level = aggregated_level

    db.commit()
    db.refresh(assessment)
    return assessment


def end_session(db: Session, session: VerificationSession, *,
                 status_: VerificationStatus = VerificationStatus.COMPLETED) -> VerificationSession:
    from datetime import datetime, timezone

    session.status = status_
    session.ended_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(session)
    return session


def get_session(db: Session, user_id: int, session_id: int) -> VerificationSession:
    session = db.query(VerificationSession).filter(
        VerificationSession.id == session_id,
        VerificationSession.user_id == user_id,
    ).first()
    if not session:
        raise ResourceNotFoundException(f"Verification session {session_id} not found")
    return session


def list_sessions(db: Session, user_id: int) -> list[VerificationSession]:
    return (
        db.query(VerificationSession)
        .filter(VerificationSession.user_id == user_id)
        .order_by(VerificationSession.started_at.desc())
        .all()
    )
