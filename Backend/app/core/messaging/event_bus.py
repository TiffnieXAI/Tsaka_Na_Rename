"""
Real-time dashboard event bus, built on top of the shared RabbitMQ topic
exchange from app/core/messaging/rabbitmq.py.

This is the piece any producer plugs into: a webhook handler receiving
platform telemetry (flowchart step 01), the behavioral trust engine
(steps 02-04), the autonomous response engine (section 3), etc. None of
them need to know who's currently connected to /ws/events - they just
publish_event() with the affected user_id, and RabbitMQ fans it out to
whichever uvicorn worker (if any) is holding that user's dashboard socket.

  Producer                                  Consumer
  --------                                  --------
  publish_event(user_id=7, ...)   --->  RabbitMQ topic exchange   --->  per-connection
                                         "centry.dashboard_events"       queue bound to
                                         routing key                    "user.7.#"
                                         "user.7.trust_score_updated"    (app/routers/events.py)

Routing key shape: "user.<user_id>.<event_type>". A dashboard connection
binds an exclusive, auto-delete queue to "user.<user_id>.#" so it receives
every event type for that user without the publisher needing to know which
event types any given consumer cares about.
"""

import json
import logging
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

import aio_pika

from app.core.messaging.rabbitmq import get_exchange, get_connection
from app.schemas.events import EventType, PageEvent

logger = logging.getLogger(__name__)


def _routing_key(user_id: int, event_type: EventType) -> str:
    return f"user.{user_id}.{event_type.value}"


async def publish_event(user_id: int, event_type: EventType, data: dict) -> None:
    """
    Publish one dashboard event for a given user. Fire-and-forget from the
    caller's perspective - if RabbitMQ is down this logs and returns rather
    than raising, so a flaky broker never breaks the webhook/AI pipeline
    that's calling this (those should keep working and persisting to MySQL
    regardless of whether anyone's dashboard is open live to see it).
    """
    exchange = get_exchange()
    if exchange is None:
        logger.warning(
            "publish_event(%s, %s) dropped - RabbitMQ not connected", user_id, event_type.value
        )
        return

    event = PageEvent(
        event_type=event_type,
        user_id=user_id,
        data=data,
        emitted_at=datetime.now(timezone.utc),
    )

    message = aio_pika.Message(
        body=event.model_dump_json().encode("utf-8"),
        content_type="application/json",
        delivery_mode=aio_pika.DeliveryMode.NOT_PERSISTENT,  # live UI push, not an audit log
    )
    await exchange.publish(message, routing_key=_routing_key(user_id, event_type))


async def subscribe_user_events(user_id: int) -> AsyncGenerator[str, None]:
    """
    Async generator yielding raw JSON strings (PageEvent payloads) for one
    user, as they're published. Used by app/routers/events.py to bridge
    RabbitMQ messages onto a single WebSocket connection.

    Creates a fresh exclusive, auto-delete queue per call (i.e. per
    WebSocket connection) bound to "user.<user_id>.#", so multiple browser
    tabs / devices for the same user each get their own independent copy of
    every event, and the queue cleans itself up when the connection drops.
    """
    connection = get_connection()
    exchange = get_exchange()
    if connection is None or exchange is None:
        logger.warning("subscribe_user_events(%s) - RabbitMQ not connected, nothing to stream", user_id)
        return

    channel = await connection.channel()
    try:
        queue = await channel.declare_queue(
            name=f"dashboard.{user_id}.{uuid.uuid4().hex}",
            exclusive=True,
            auto_delete=True,
        )
        await queue.bind(exchange, routing_key=f"user.{user_id}.#")

        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    yield message.body.decode("utf-8")
    finally:
        await channel.close()
