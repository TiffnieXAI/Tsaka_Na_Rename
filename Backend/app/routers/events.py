import logging

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from app.core.deps import get_current_user_ws
from app.core.messaging.event_bus import subscribe_user_events
from app.models.models import User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Real-Time Dashboard Events"])


@router.websocket("/ws/events")
async def dashboard_events(websocket: WebSocket, current_user: User = Depends(get_current_user_ws)):
    """
    "Cross-Platform Monitoring" + ("Incident Investigation & Autonomous Action"), 
    real-time half.
    Server -> client only: once connected, the client just listens. Any
    backend process publishes onto this user's stream via
    app.core.messaging.event_bus.publish_event(user_id, event_type, data) -
    a webhook handler processing platform telemetry, the behavioral trust
    engine, the autonomous response engine, a background worker, etc. This
    router doesn't know or care who published; it just relays.

    Client connects with a JWT as a query param (same pattern as
    /ws/live-verify - see get_current_user_ws):
      wss://host/ws/events?token=<jwt>

    Every frame is a PageEvent (app/schemas/events.py):
      {"type": "dashboard_event", "event_type": "...", "user_id": ..., "data": {...}, "emitted_at": "..."}

    If RabbitMQ isn't reachable, the connection stays open (so the frontend
    doesn't error out) but no events will ever arrive - check server logs.
    """
    await websocket.accept()
    await websocket.send_json({"type": "connected", "user_id": current_user.id})

    try:
        async for raw_event_json in subscribe_user_events(current_user.id):
            await websocket.send_text(raw_event_json)
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("Dashboard events stream failed for user %s", current_user.id)
