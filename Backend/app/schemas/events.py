import enum
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class EventType(str, enum.Enum):
    """
    Dashboard event types - "Cross-Platform Monitoring"
    and "Incident Investigation & Autonomous Action". Extend this
    as new real-time event kinds are needed; add a matching producer call
    (app.core.messaging.event_bus.publish_event) wherever that event
    actually originates.
    """

    PLATFORM_ACTIVITY_RECEIVED = "platform_activity_received"  # step 01: raw webhook landed
    TRUST_SCORE_UPDATED = "trust_score_updated"                # steps 03-04: behavioral engine output
    DASHBOARD_SYNC = "dashboard_sync"                          # step 05: baseline security snapshot

    INCIDENT_DETECTED = "incident_detected"                    # high-risk scam/breach flagged
    AUTONOMOUS_ACTION_TAKEN = "autonomous_action_taken"         # steps 23-25: threat auto-mitigated


class PageEvent(BaseModel):
    """
    The envelope every message on /ws/events is wrapped in. `data`'s shape
    depends on `event_type` - see the producer that emits each one
    (app/services/ai_models/behavioral_engine.py for TRUST_SCORE_UPDATED,
    etc.) for what to expect.
    """

    type: str = "dashboard_event"
    event_type: EventType
    user_id: int
    data: dict[str, Any]
    emitted_at: datetime
