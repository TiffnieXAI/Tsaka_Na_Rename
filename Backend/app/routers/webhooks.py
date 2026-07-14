import logging

from fastapi import APIRouter, Depends

from app.core.deps import get_current_user
from app.core.messaging.event_bus import publish_event
from app.models.models import User
from app.schemas.events import EventType
from app.schemas.webhooks import PlatformActivityIn
from app.services.ai_models import behavioral_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/webhooks", tags=["Cross-Platform Monitoring"])


@router.post("/platform-event")
async def ingest_platform_event(body: PlatformActivityIn, current_user: User = Depends(get_current_user)):
    """

    This is a stand-in for real platform webhooks, authenticated with a
    normal user Bearer token so it's easy to call from /docs or curl while
    the AI team's model and the real per-platform webhook receivers (with
    signature verification, e.g. Shopee's push-notification HMAC, Meta's
    X-Hub-Signature) aren't built yet. Before this goes live against real
    platforms:
      - Add one receiver per platform (unauthenticated, signature-verified,
        shaped like each platform's actual webhook payload) that translates
        into this same PlatformActivityIn contract.
      - Resolve `external_account_id` -> the owning `User` via
        `PlatformConnection` instead of trusting the caller's own JWT (a
        real webhook has no user JWT - the platform is calling us).
      - Persist a running per-user/per-platform trust score (new model)
        instead of scoring every event from a blank baseline, so
        `previous_trust_score` below is meaningful.

    Pipeline:
      1. Raw activity telemetry arrives.
      2-3. `behavioral_engine.process_event()` - AI team's plug-in point,
           currently a stub (app/services/ai_models/behavioral_engine.py).
      4-5. Publish the result onto the user's RabbitMQ event stream so any
           open dashboard (/ws/events) updates live.
    """
    result = await behavioral_engine.process_event(
        platform=body.platform.value,
        event_type=body.event_type,
        payload=body.payload,
        previous_trust_score=None,  # TODO: look up the user's last known score once persisted
    )

    await publish_event(
        user_id=current_user.id,
        event_type=EventType.TRUST_SCORE_UPDATED,
        data={
            "platform": body.platform.value,
            "event_type": body.event_type,
            "trust_score": result.trust_score,
            "risk_delta": result.risk_delta,
            "flagged_reasons": result.flagged_reasons,
            "model_version": result.model_version,
        },
    )
    await publish_event(
        user_id=current_user.id,
        event_type=EventType.DASHBOARD_SYNC,
        data={"latest_trust_score": result.trust_score},
    )

    return {
        "status": "processed",
        "trust_score": result.trust_score,
        "risk_delta": result.risk_delta,
        "flagged_reasons": result.flagged_reasons,
    }
