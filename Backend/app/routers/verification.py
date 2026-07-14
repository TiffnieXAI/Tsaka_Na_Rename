import logging

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.deps import get_current_user, get_current_user_ws
from app.models.models import User, VerificationStatus
from app.schemas.verification import (
    VerificationSessionResponse, VerificationSessionDetailResponse,
    LiveVerifyMergePayload, LiveVerifySessionInitPayload, LiveVerifyErrorPayload,
    VoiceBiometricsResult, SemanticIntentResult,
)
from app.services import verification_service, risk_engine_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Live Voice Verification"])


@router.websocket("/ws/live-verify")
async def live_verify(websocket: WebSocket,
                       current_user: User = Depends(get_current_user_ws),
                       db: Session = Depends(get_db)):
    """
    "Live Deepfake Audio Detection (Live Verify)".

    Client connects with a JWT as a query param (see get_current_user_ws),
    e.g.:  wss://host/ws/live-verify?token=<jwt>

    Protocol:
      - Client sends raw binary audio chunks (frontend decides chunk size/
        cadence - confirm with Lorenz's part what encoding is streamed:
        raw PCM16, WebM/Opus, etc.)
      - After each chunk, server runs the parallel dual-model analysis and
        pushes back a JSON text frame shaped like LiveVerifyMergePayload.
      - Client sends the text message "END" (or just closes the socket) to
        stop; server always sends one final JSON frame confirming session end.
    """
    await websocket.accept()

    session = verification_service.start_session(db, current_user)
    await websocket.send_json(
        LiveVerifySessionInitPayload(session_id=session.id, started_at=session.started_at).model_dump(mode="json")
    )

    try:
        while True:
            message = await websocket.receive()

            if message["type"] == "websocket.disconnect":
                break

            if "text" in message and message["text"] == "END":
                break

            audio_chunk = message.get("bytes")
            if not audio_chunk:
                continue

            try:
                assessment = await verification_service.analyze_audio_window(db, session, audio_chunk)
            except Exception:
                logger.exception("Live-verify analysis failed for session %s", session.id)
                await websocket.send_json(
                    LiveVerifyErrorPayload(detail="Analysis failed for this audio window - continuing.").model_dump()
                )
                continue

            recommend_block = assessment.aggregated_risk_score >= risk_engine_service.AUTONOMOUS_BLOCK_THRESHOLD
            payload = LiveVerifyMergePayload(
                session_id=session.id,
                sequence_number=assessment.sequence_number,
                voice_biometrics=VoiceBiometricsResult(
                    authenticity_score=assessment.voice_authenticity_score,
                    confidence=assessment.voice_model_confidence,
                    model_version="voice-biometrics-stub-v0",
                ),
                semantic_intent=SemanticIntentResult(
                    scam_score=assessment.semantic_scam_score,
                    detected_markers=assessment.detected_scam_markers or [],
                    transcript_snippet=assessment.transcript_snippet,
                    model_version="semantic-intent-stub-v0",
                ),
                aggregated_risk_score=assessment.aggregated_risk_score,
                aggregated_risk_level=assessment.aggregated_risk_level,
                recommend_autonomous_block=recommend_block,
            )
            await websocket.send_json(payload.model_dump(mode="json"))

    except WebSocketDisconnect:
        pass
    finally:
        verification_service.end_session(db, session, status_=VerificationStatus.COMPLETED)


@router.get("/api/v1/verification/sessions", response_model=list[VerificationSessionResponse])
def list_verification_sessions(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Call history for section 3/4 - dashboard list of past Live Verify sessions."""
    return verification_service.list_sessions(db, current_user.id)


@router.get("/api/v1/verification/sessions/{session_id}", response_model=VerificationSessionDetailResponse)
def get_verification_session(session_id: int,
                              current_user: User = Depends(get_current_user),
                              db: Session = Depends(get_db)):
    """Full detail for one call, including every analyzed audio window (RiskAssessment)."""
    return verification_service.get_session(db, current_user.id, session_id)
