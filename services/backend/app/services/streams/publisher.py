"""
StreamPublisher — writes FSM events to the per-call Redis Stream.

Wire format: one Redis Stream entry per event.
    XADD voice:calls:{session_id} MAXLEN ~ 10000 * event_type <str> data <json>

We store `event_type` as a flat field for easy consumer filtering via XREAD,
and `data` as the full serialized event JSON for typed deserialization.

All producers import this module. No ad-hoc xadd calls elsewhere.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from redis.asyncio import Redis

from app.core.config import get_settings
from app.services.streams.event_schemas import FSMEventBase

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class StreamPublisher:
    """
    Publishes FSMEvent objects to the per-call Redis Stream.

    One instance is created per call session and held by the StreamIngester.
    Consumers that need to emit events back (ASR result, TTS done, LLM result)
    receive a reference to this publisher.
    """

    def __init__(self, *, redis: Redis, session_id: str, call_id: str) -> None:
        self._redis = redis
        self._session_id = session_id
        self._call_id = call_id
        self._settings = get_settings()
        self._stream_key = self._settings.per_call_stream_key(session_id)
        self._maxlen = self._settings.redis_stream_maxlen

    @property
    def stream_key(self) -> str:
        return self._stream_key

    async def publish(self, event: FSMEventBase) -> str | None:
        """
        Serialize and XADD the event to the per-call stream.
        Returns the Redis stream entry ID, or None on failure (logged, not raised).
        """
        try:
            entry_id = await self._redis.xadd(
                self._stream_key,
                {
                    'event_type': event.event_type,
                    'data': event.model_dump_json(),
                },
                maxlen=self._maxlen,
                approximate=True,
            )
            return entry_id
        except Exception as exc:
            logger.warning(
                'stream.publish.failed',
                extra={
                    'correlation_id': '',
                    'tenant_id': '',
                    'call_id': self._call_id,
                    'session_id': self._session_id,
                    'event_type': event.event_type,
                    'stream_key': self._stream_key,
                    'error_type': type(exc).__name__,
                    'error': str(exc),
                },
            )
            return None

    async def publish_many(self, events: list[FSMEventBase]) -> None:
        """Fire-and-forget publish of multiple events in order."""
        for event in events:
            await self.publish(event)
