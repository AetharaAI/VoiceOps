"""
VoiceOps FSM — TTS Consumer
=============================

Consumer group: voice:tts

Waits for tts.speak events on the per-call Redis stream.
When received: calls Aether Voice TTS, converts audio to μ-law@8kHz, and
writes chunks to IngesterSession.tts_audio_queue for the drain task to forward
to Twilio. Publishes tts.complete when done.

Audio flow:
    State Controller → tts.speak → TTS Consumer → Aether Voice TTS
        ↓ (WAV chunks)
    wav_to_pcm16 → resample 24kHz→8kHz → pcm16_to_mulaw
        ↓ (μ-law@8kHz chunks)
    tts_audio_queue → Ingester drain task → Twilio media events

Barge-in:
    If session.barge_in_requested is True when a chunk is about to be
    queued, the Consumer abandons the remainder of the TTS stream.
    The barge_in flag is cleared by the Ingester's drain task when it sees
    the None sentinel.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from typing import TYPE_CHECKING

from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.realtime.audio import pcm16_to_mulaw, resample_pcm16, wav_to_pcm16
from app.services.streams.event_schemas import (
    FSMEventBase,
    TTSCompleteEvent,
    TTSCompletePayload,
    make_event,
)
from app.services.streams.publisher import StreamPublisher
from app.services.tts.client import TTSClient, tts_client

if TYPE_CHECKING:
    from app.services.realtime.stream_ingester import IngesterSession

logger = get_logger(__name__)

TWILIO_SAMPLE_RATE = 8000
STREAM_POLL_BLOCK_MS = 500


class TTSConsumer:
    """
    Runs as an asyncio task for one call.
    Subscribes to tts.speak on the per-call stream; manages one TTS stream
    per agent turn.
    """

    def __init__(self, client: TTSClient | None = None) -> None:
        self._settings = get_settings()
        self._client = client or tts_client

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
        is cancelled (always from handle_ws cleanup).
        """
        stream_key = self._settings.per_call_stream_key(session_id)
        group_name = self._settings.redis_cg_tts
        consumer_name = f'tts_{session_id[:8]}'

        try:
            await redis.xgroup_create(stream_key, group_name, id='0', mkstream=True)
        except Exception:
            pass  # BUSYGROUP

        logger.info('tts_consumer.started', extra={
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
                            tenant_id=tenant_id,
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
            logger.error('tts_consumer.fatal', extra={
                'correlation_id': '', 'tenant_id': tenant_id,
                'call_id': call_id, 'error': str(exc),
            })
        finally:
            logger.info('tts_consumer.ended', extra={
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
        tenant_id: str,
    ) -> str:
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
        if et == 'tts.speak':
            payload = base.payload
            text = (
                payload.get('text', '')
                if isinstance(payload, dict)
                else getattr(payload, 'text', '')
            )
            voice = (
                payload.get('voice', self._settings.aether_voice_tts_voice)
                if isinstance(payload, dict)
                else getattr(payload, 'voice', self._settings.aether_voice_tts_voice)
            )
            model = (
                payload.get('model', self._settings.aether_voice_tts_model)
                if isinstance(payload, dict)
                else getattr(payload, 'model', self._settings.aether_voice_tts_model)
            )
            tts_request_id = (
                payload.get('tts_request_id', '')
                if isinstance(payload, dict)
                else getattr(payload, 'tts_request_id', '')
            )

            if text:
                await self._handle_speak(
                    ingester_session, publisher, base,
                    text=text, voice=voice, model=model,
                    tts_request_id=tts_request_id,
                    call_id=call_id, tenant_id=tenant_id,
                )
        return et

    # ------------------------------------------------------------------
    # Core: one TTS turn
    # ------------------------------------------------------------------

    async def _handle_speak(
        self,
        session: IngesterSession,
        publisher: StreamPublisher,
        base: FSMEventBase,
        *,
        text: str,
        voice: str,
        model: str,
        tts_request_id: str,
        call_id: str,
        tenant_id: str,
    ) -> None:
        """
        Stream TTS audio to the tts_audio_queue.
        Converts WAV chunks from Aether Voice → μ-law@8kHz for Twilio.
        Puts None sentinel when done; publishes tts.complete.
        """
        session.tts_active = True
        interrupted = False
        duration_start = time.monotonic()
        error_msg: str | None = None
        resample_state = None

        logger.info('tts_consumer.speak.start', extra={
            'correlation_id': '', 'tenant_id': tenant_id,
            'call_id': call_id, 'tts_request_id': tts_request_id,
            'text_preview': text[:80],
        })

        try:
            async for wav_chunk in self._client.stream_tts(
                text=text,
                call_id=call_id,
                agent_id='',  # not required by Aether Voice
                model=model,
                voice=voice,
            ):
                # Check for barge-in before queuing each chunk
                if session.barge_in_requested:
                    interrupted = True
                    break

                mulaw_chunk, resample_state = self._wav_chunk_to_mulaw(
                    wav_chunk, resample_state=resample_state
                )
                if mulaw_chunk:
                    await session.tts_audio_queue.put(mulaw_chunk)

        except Exception as exc:
            error_msg = str(exc)
            logger.error('tts_consumer.speak.error', extra={
                'correlation_id': '', 'tenant_id': tenant_id,
                'call_id': call_id, 'tts_request_id': tts_request_id,
                'error': error_msg,
            })
        finally:
            # None sentinel: tells Ingester drain task this TTS request is done
            await session.tts_audio_queue.put(None)
            session.tts_active = False

        duration_ms = round((time.monotonic() - duration_start) * 1000)

        # Publish tts.complete so State Controller can emit asr.start_listen
        await publisher.publish(make_event(
            TTSCompleteEvent,
            session_id=base.session_id,
            call_id=base.call_id,
            payload=TTSCompletePayload(
                tts_request_id=tts_request_id,
                duration_ms=duration_ms,
                interrupted=interrupted,
                error=error_msg,
            ),
        ))

        logger.info('tts_consumer.speak.complete', extra={
            'correlation_id': '', 'tenant_id': tenant_id,
            'call_id': call_id, 'tts_request_id': tts_request_id,
            'duration_ms': duration_ms, 'interrupted': interrupted,
        })

    # ------------------------------------------------------------------
    # Audio conversion helper (mirrors session_manager._wav_chunk_to_mulaw)
    # ------------------------------------------------------------------

    def _wav_chunk_to_mulaw(
        self, wav_chunk: bytes, resample_state: tuple | None = None
    ) -> tuple[bytes, tuple | None]:
        """Convert one TTS audio chunk (WAV or raw PCM) to μ-law@8kHz."""
        try:
            pcm_audio, sample_rate = wav_to_pcm16(wav_chunk)
        except Exception:
            # Not a WAV file — treat as raw PCM at TTS sample rate
            pcm_audio = wav_chunk
            sample_rate = self._settings.aether_voice_tts_sample_rate

        pcm_8k, next_state = resample_pcm16(
            pcm_audio, from_rate=sample_rate, to_rate=TWILIO_SAMPLE_RATE,
            state=resample_state,
        )
        return pcm16_to_mulaw(pcm_8k), next_state


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

tts_consumer = TTSConsumer()
