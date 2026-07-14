from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.models import VerificationStatus, RiskLevel


# --- REST: session history / detail --------------------------------------

class VerificationSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: VerificationStatus
    caller_label: Optional[str]
    latest_risk_score: Optional[float]
    latest_risk_level: Optional[RiskLevel]
    autonomous_action_taken: bool
    started_at: datetime
    ended_at: Optional[datetime]


class RiskAssessmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sequence_number: int
    voice_authenticity_score: Optional[float]
    voice_model_confidence: Optional[float]
    semantic_scam_score: Optional[float]
    detected_scam_markers: Optional[list[str]]
    transcript_snippet: Optional[str]
    aggregated_risk_score: float
    aggregated_risk_level: RiskLevel
    created_at: datetime


class VerificationSessionDetailResponse(VerificationSessionResponse):
    assessments: list[RiskAssessmentResponse] = []


# --- WebSocket payload shapes ----------------------------------------------
# These aren't enforced by FastAPI (WS messages are hand-serialized in the
# router) but are documented here as the source of truth for the frontend.

class VoiceBiometricsResult(BaseModel):
    """Output of the Voice Biometrics Model (acoustic profile) - 'how they speak'."""
    model_config = ConfigDict(protected_namespaces=())

    authenticity_score: float = Field(..., ge=0, le=100)
    confidence: float = Field(..., ge=0, le=1)
    model_version: str


class SemanticIntentResult(BaseModel):
    """Output of the Semantic Intent Model (scam markers) - 'what they say'."""
    model_config = ConfigDict(protected_namespaces=())

    scam_score: float = Field(..., ge=0, le=100)
    detected_markers: list[str]
    transcript_snippet: Optional[str]
    model_version: str


class LiveVerifyMergePayload(BaseModel):
    """
    The "Merge JSON" pushed to the frontend after each analyzed audio window. 
    This is the message shape sent over /ws/live-verify for type="risk_update" frames.
    """
    
    type: str = "risk_update"
    session_id: int
    sequence_number: int
    voice_biometrics: VoiceBiometricsResult
    semantic_intent: SemanticIntentResult
    aggregated_risk_score: float = Field(..., ge=0, le=100)
    aggregated_risk_level: RiskLevel
    recommend_autonomous_block: bool


class LiveVerifySessionInitPayload(BaseModel):
    """Sent once, right after the WebSocket connection is accepted."""
    type: str = "session_initialized"
    session_id: int
    started_at: datetime


class LiveVerifyErrorPayload(BaseModel):
    type: str = "error"
    detail: str
