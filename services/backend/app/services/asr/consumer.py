"""
VoiceOps FSM — ASR Consumer
============================

Consumer group: voice:asr

Waits for asr.start_listen events on the per-call Redis stream.
When received: opens an ASR stream to Aether Voice, drains PCM16@16kHz audio
from the IngesterSession.asr_audio_queue, and publishes asr.transcript when
the caller's turn ends.

Audio flow:
    Twilio → Ingester (VAD) → asr_audio_queue → ASR Consumer → Aether Voice ASR
                                    (PCM16@16kHz)

Coordination:
    asr.start_listen (from State Controller) → start a listen window
    None sentinel in asr_audio_queue         → caller turn ended, finalize
    asr.transcript (published here)          → State Controller picks up

Timeout:
    If no speech arrives within timeout_seconds + DRAIN_TIMEOUT_BUFFER seconds,
    the listen window is abandoned. The State Controller already detects the
    silence and emits recovery TTS / next asr.start_listen independently.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from typing import TYPE_CHECKING

from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.asr.client import ASRClient, asr_client
from app.services.streams.event_schemas import (
    ASRTranscriptEvent,
    ASRTranscriptPayload,
    FSMEventBase,
    make_event,
)
from app.services.streams.publisher import StreamPublisher

if TYPE_CHECKING:
    from app.services.realtime.stream_ingester import IngesterSession

logger = get_logger(__name__)

# Extra time beyond the State Controller's silence timeout before we abandon
# a listen window. The State Controller fires independently; we just need
# not to block forever.
DRAIN_TIMEOUT_BUFFER = 3.0
STREAM_POLL_BLOCK_MS = 500


class ASRConsumer:
    """
    Runs as an asyncio task for one call.
    Subscribes to asr.start_listen on the per-call stream; manages one ASR
    stream session per caller turn.
    """

    def __init__(self, client: ASRClient | None = None) -> None:
        self._settings = get_settings()
        self._client = client or asr_client

    async def run(
        self,
        *,
        session_id: str,
        call_id: str,
        tenant_id: str,
        ingester_session: IngesterSession,
        redis: Redis,
        publisher: StreamPublisher,
    ) -> None:
        """
        Consumer loop for one call. Returns when call.ended is seen or task
        is cancelled (always happens from handle_ws cleanup).
        """
        stream_key = self._settings.per_call_stream_key(session_id)
        group_name = self._settings.redis_cg_asr
        consumer_name = f'asr_{session_id[:8]}'

        try:
            await redis.xgroup_create(stream_key, group_name, id='0', mkstream=True)
        except Exception:
            pass  # BUSYGROUP — already exists

        logger.info('asr_consumer.started', extra={
            'correlation_id': '', 'tenant_id': tenant_id,
            'call_id': call_id, 'session_id': session_id,
        })

        try:
            while True:
                entries = await redis.xreadgroup(
                    group_name, consumer_name,
                    {stream_key: '>'},
                    count=5,
                    block=STREAM_POLL_BLOCK_MS,
                )
                if not entries:
                    continue

                for _stream, messages in entries:
                    for entry_id, raw_fields in messages:
                        et = await self._dispatch(
                            ingester_session, publisher, raw_fields,
                            session_id=session_id, call_id=call_id,
                        )
                        try:
                            await redis.xack(stream_key, group_name, entry_id)
                        except Exception:
                            pass
                        if et == 'call.ended':
                            return

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error('asr_consumer.fatal', extra={
                'correlation_id': '', 'tenant_id': tenant_id,
                'call_id': call_id, 'error': str(exc),
            })
        finally:
            logger.info('asr_consumer.ended', extra={
                'correlation_id': '', 'tenant_id': tenant_id,
                'call_id': call_id,
            })

    # ------------------------------------------------------------------
    # Dispatcher
    # ------------------------------------------------------------------

    async def _dispatch(
        self,
        ingester_session: IngesterSession,
        publisher: StreamPublisher,
        raw_fields: dict,
        *,
        session_id: str,
        call_id: str,
    ) -> str:
        """Parse entry and handle asr.start_listen. Returns event_type."""
        raw = raw_fields.get('data') or raw_fields.get(b'data', b'')
        if isinstance(raw, bytes):
            raw = raw.decode('utf-8', errors='replace')
        if not raw:
            return ''

        try:
            base = FSMEventBase.model_validate_json(raw)
        except Exception:
            return ''

        et = base.event_type
        if et == 'asr.start_listen':
            payload = base.payload
            timeout = (
                payload.get('timeout_seconds', 8.0)
                if isinstance(payload, dict)
                else getattr(payload, 'timeout_seconds', 8.0)
            )
            await self._handle_listen_window(
                ingester_session, publisher, base,
                timeout_seconds=float(timeout),
            )
        return et

    # ------------------------------------------------------------------
    # Core: one listen window
    # ------------------------------------------------------------------

    async def _handle_listen_window(
        self,
        session: IngesterSession,
        publisher: StreamPublisher,
        base: FSMEventBase,
        timeout_seconds: float,
    ) -> None:
        """
        Open ASR stream, drain asr_audio_queue until None sentinel, then
        publish asr.transcript.
        """
        deadline = time.monotonic() + timeout_seconds + DRAIN_TIMEOUT_BUFFER
        asr_stream = None
        transcript_text = ''
        started_ms: int | None = None
        ended_ms: int | None = None
        error_msg: str | None = None
        got_speech = False
        saw_partial_transcript = False
        last_partial_text = ''

        try:
            async def _on_asr_event(event: dict) -> None:
                nonlocal last_partial_text
                event_type = str(event.get('type') or '')
                if event_type != 'partial_transcript':
                    return
                text = str(event.get('text') or '').strip()
                if not text or text == last_partial_text:
                    return
                last_partial_text = text
                saw_partial_transcript = True
                await publisher.publish(make_event(
                    ASRTranscriptEvent,
                    session_id=base.session_id,
                    call_id=base.call_id,
                    payload=ASRTranscriptPayload(
                        text=text,
                        is_final=False,
                        asr_session_id=getattr(asr_stream, 'session_id', '') if asr_stream else '',
                    ),
                ))
                logger.debug('asr_consumer.partial.published', extra={
                    'correlation_id': '', 'tenant_id': '',
                    'call_id': base.call_id, 'text_preview': text[:80],
                })

            asr_stream = await self._client.start_stream(
                call_id=base.call_id,
                on_event=_on_asr_event,
            )
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    # Timeout — State Controller handles silence independently
                    logger.info('asr_consumer.listen_window.timeout', extra={
                        'correlation_id': '', 'tenant_id': '',
                        'call_id': base.call_id, 'got_speech': got_speech,
                    })
                    break

                try:
                    frame = await asyncio.wait_for(
                        session.asr_audio_queue.get(),
                        timeout=min(remaining, 1.0),
                    )
                except asyncio.TimeoutError:
                    continue  # check deadline again

                if frame is None:
                    # End-of-turn sentinel from Ingester VAD
                    break

                got_speech = True
                await asr_stream.send_audio_frame(frame)

            if got_speech:
                await asr_stream.end_stream()
                final = await asr_stream.wait_for_final(timeout_seconds=5.0)
                transcript_text = final.text or ''
                started_ms = final.started_ms
                ended_ms = final.ended_ms

        except Exception as exc:
            error_msg = str(exc)
            logger.error('asr_consumer.listen_window.error', extra={
                'correlation_id': '', 'tenant_id': '',
                'call_id': base.call_id, 'error': error_msg,
            })
        finally:
            if asr_stream is not None:
                with contextlib.suppress(Exception):
                    await asr_stream.close()

        has_non_empty_final = bool(transcript_text.strip())
        has_time_bounds = started_ms is not None or ended_ms is not None
        should_publish_final = bool(
            error_msg is not None
            or has_non_empty_final
            or saw_partial_transcript
            or has_time_bounds
        )

        # Publish asr.transcript only when we have meaningful signal.
        # Noise-only false starts commonly produce empty finals with no timings;
        # dropping those avoids prompt-churn/step-on loops in the controller.
        if should_publish_final:
            await publisher.publish(make_event(
                ASRTranscriptEvent,
                session_id=base.session_id,
                call_id=base.call_id,
                payload=ASRTranscriptPayload(
                    text=transcript_text,
                    started_ms=started_ms,
                    ended_ms=ended_ms,
                    asr_session_id=getattr(asr_stream, 'session_id', '') if asr_stream else '',
                ),
            ))

            logger.info('asr_consumer.transcript.published', extra={
                'correlation_id': '', 'tenant_id': '',
                'call_id': base.call_id,
                'text_preview': transcript_text[:80],
                'started_ms': started_ms, 'ended_ms': ended_ms,
            })
        elif got_speech:
            logger.info('asr_consumer.transcript.dropped_empty_noise', extra={
                'correlation_id': '', 'tenant_id': '',
                'call_id': base.call_id,
                'saw_partial_transcript': saw_partial_transcript,
                'started_ms': started_ms,
                'ended_ms': ended_ms,
            })


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

asr_consumer = ASRConsumer()
