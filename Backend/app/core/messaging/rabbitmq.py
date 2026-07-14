"""
RabbitMQ connection lifecycle.

One shared connection + channel + topic exchange for the whole app process,
opened in app.main's lifespan on startup and closed on shutdown. Everything
else (publishing, subscribing) goes through app/core/messaging/event_bus.py,
which uses `get_exchange()` from here - this module only owns the
connection itself.

Kept deliberately tolerant of RabbitMQ being unavailable (see
`settings.rabbitmq_optional`): in local dev, or before the AI team's/infra
team's RabbitMQ instance exists yet, the rest of the API should still come
up and work - real-time dashboard events just won't go anywhere until the
broker is reachable.
"""

import logging

import aio_pika
from aio_pika import ExchangeType
from aio_pika.abc import AbstractExchange, AbstractRobustConnection

from app.config import settings

logger = logging.getLogger(__name__)

_connection: AbstractRobustConnection | None = None
_exchange: AbstractExchange | None = None


async def connect_rabbitmq() -> None:
    """Call once on app startup (see app/main.py's lifespan)."""
    global _connection, _exchange

    try:
        _connection = await aio_pika.connect_robust(settings.rabbitmq_url)
        channel = await _connection.channel()
        _exchange = await channel.declare_exchange(
            settings.rabbitmq_events_exchange, ExchangeType.TOPIC, durable=True
        )
        logger.info("Connected to RabbitMQ at %s", settings.rabbitmq_url)
    except Exception:
        _connection = None
        _exchange = None
        if settings.rabbitmq_optional:
            logger.warning(
                "Could not connect to RabbitMQ (%s) - real-time dashboard events "
                "(/ws/events) will be unavailable until this is fixed. Everything "
                "else in the API is unaffected.",
                settings.rabbitmq_url,
                exc_info=True,
            )
        else:
            raise


async def close_rabbitmq() -> None:
    """Call once on app shutdown (see app/main.py's lifespan)."""
    global _connection, _exchange
    if _connection is not None:
        await _connection.close()
    _connection = None
    _exchange = None


def get_exchange() -> AbstractExchange | None:
    """
    Returns the shared topic exchange, or None if RabbitMQ isn't connected
    (only possible when rabbitmq_optional=True - see connect_rabbitmq).
    Callers (event_bus.py) should handle the None case rather than crash a
    request/websocket over a broker outage.
    """
    return _exchange


def get_connection() -> AbstractRobustConnection | None:
    return _connection
