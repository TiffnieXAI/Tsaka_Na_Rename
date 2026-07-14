import enum

from sqlalchemy import (
    Column, String, Integer, Float, Text, DateTime, Boolean, ForeignKey, Enum as SAEnum,
    UniqueConstraint, JSON, func
)
from sqlalchemy.orm import relationship

from app.database import Base


class PlatformType(str, enum.Enum):
    SHOPEE = "SHOPEE"
    LAZADA = "LAZADA"
    TIKTOK_SHOP = "TIKTOK_SHOP"
    META = "META"


class ConnectionStatus(str, enum.Enum):
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
    EXPIRED = "EXPIRED"
    ERROR = "ERROR"


class User(Base):
    """Login identity for Centry."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(150), nullable=False, unique=True, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(150))
    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    platform_connections = relationship(
        "PlatformConnection", back_populates="user", cascade="all, delete-orphan"
    )


class PlatformConnection(Base):
    """A third-party shop account (Shopee/Lazada/TikTok Shop) linked to a User via OAuth."""
    __tablename__ = "platform_connections"
    __table_args__ = (
        UniqueConstraint("user_id", "platform_type", "external_account_id", name="uq_user_platform"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    platform_type = Column(SAEnum(PlatformType), nullable=False)
    external_account_id = Column(String(150), nullable=False)  # shop_id / seller_id on that platform
    external_display_name = Column(String(150))

    # NOTE: plain text for now, per current project phase - encrypt before this touches real tokens
    access_token = Column(String(500), nullable=False)
    refresh_token = Column(String(500))
    token_expires_at = Column(DateTime)

    status = Column(SAEnum(ConnectionStatus), nullable=False, default=ConnectionStatus.CONNECTED)
    connected_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="platform_connections")


# ---------------------------------------------------------------------------
# Live Deepfake / Scam-Call Voice Verification ("Live Verify")
# ---------------------------------------------------------------------------

class VerificationStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"          # WebSocket connected, audio streaming in progress
    COMPLETED = "COMPLETED"    # call ended normally (frontend disconnected)
    TERMINATED = "TERMINATED"  # ended abnormally (socket error, server restart, etc.)


class RiskLevel(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class VerificationSession(Base):
    """
    One "Live Verify" call, from the moment the MSME owner taps the button
    in the app to the moment the call ends / socket disconnects. Holds the 
    running/aggregated risk state; each individual chunk analyzed during 
    the call is a RiskAssessment row.
    """
    __tablename__ = "verification_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    status = Column(SAEnum(VerificationStatus), nullable=False, default=VerificationStatus.ACTIVE)
    caller_label = Column(String(150))  # optional user-supplied note, e.g. "Unknown Number"

    # Denormalized "latest" snapshot so a dashboard list view doesn't need to
    # join + aggregate RiskAssessment rows just to show a status chip.
    latest_risk_score = Column(Float)          # 0-100, higher = more likely a scam/deepfake
    latest_risk_level = Column(SAEnum(RiskLevel))

    autonomous_action_taken = Column(Boolean, nullable=False, default=False)  # section 3 hook

    started_at = Column(DateTime, server_default=func.now())
    ended_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User")
    assessments = relationship(
        "RiskAssessment", back_populates="session",
        cascade="all, delete-orphan", order_by="RiskAssessment.sequence_number",
    )
    chat_sessions = relationship("ChatSession", back_populates="verification_session")


class RiskAssessment(Base):
    """
    One "Merge JSON" result: the combined output of the
    parallel Voice Biometrics model + Semantic Intent model for a single
    rolling window of streamed audio during a live-verify call.
    """
    __tablename__ = "risk_assessments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("verification_sessions.id"), nullable=False)
    sequence_number = Column(Integer, nullable=False, default=0)  # ordering within the call

    # --- Voice Biometrics Model output (how they speak") ---
    voice_authenticity_score = Column(Float)     # 0-100, higher = more likely a genuine human voice
    voice_model_confidence = Column(Float)       # 0-1, model's confidence in its own output

    # --- Semantic Intent Model output ("what they say") ---
    semantic_scam_score = Column(Float)          # 0-100, higher = more scam-like language
    detected_scam_markers = Column(JSON)         # e.g. ["urgency", "requests OTP", "impersonates bank"]
    transcript_snippet = Column(Text)            # ASR transcript for this window, if available

    # --- Aggregated result ---
    aggregated_risk_score = Column(Float, nullable=False)
    aggregated_risk_level = Column(SAEnum(RiskLevel), nullable=False)

    created_at = Column(DateTime, server_default=func.now())

    session = relationship("VerificationSession", back_populates="assessments")


# ---------------------------------------------------------------------------
# Centry AI Chatbot (Post-Incident Review & Localized AI Support)
# ---------------------------------------------------------------------------

class ChatRole(str, enum.Enum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"
    SYSTEM = "SYSTEM"


class ChatSession(Base):
    """
    A conversation thread with the Centry AI Chatbot (localized LLM), usually
    opened by the MSME owner from an incident's "explain this" button, 
    but also usable as general standalone support.
    """
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Optional: which Live Verify incident this chat is explaining context for.
    verification_session_id = Column(Integer, ForeignKey("verification_sessions.id"), nullable=True)

    title = Column(String(200))                 # short auto-generated summary, e.g. "Call risk explained"
    language = Column(String(10), nullable=False, default="en")  # "en" | "fil" | "tgl" (Taglish)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User")
    verification_session = relationship("VerificationSession", back_populates="chat_sessions")
    messages = relationship(
        "ChatMessage", back_populates="chat_session",
        cascade="all, delete-orphan", order_by="ChatMessage.created_at",
    )


class ChatMessage(Base):
    """A single turn in a ChatSession, with the metadata needed to audit/debug the AI's answers."""
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_session_id = Column(Integer, ForeignKey("chat_sessions.id"), nullable=False)

    role = Column(SAEnum(ChatRole), nullable=False)
    content = Column(Text, nullable=False)

    # --- Metadata (query context, localize, respond) ---
    language = Column(String(10))                # localized language actually used for this message
    model_used = Column(String(100))              # e.g. "centry-chatbot-localized-llm-v1"
    source_incident_ids = Column(JSON)             # RiskAssessment ids used as grounding context, if any
    latency_ms = Column(Integer)                    # end-to-end model response time

    created_at = Column(DateTime, server_default=func.now())

    chat_session = relationship("ChatSession", back_populates="messages")
