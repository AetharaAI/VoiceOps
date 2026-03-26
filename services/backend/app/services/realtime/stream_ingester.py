"""
StreamIngester — thin Twilio WebSocket handler for the FSM pipeline.

Responsibilities:
- Own the Twilio WebSocket for the duration of the call
- Decode and VAD-process incoming audio frames
- Emit FSM events to the per-call Redis Stream via StreamPublisher
- Hold the two audio queues that connect to ASR/TTS consumers:
    asr_audio_queue  — PCM16@16kHz frames → ASR Consumer reads these
    tts_audio_queue  — μ-law@8kHz chunks  → TTS Consumer puts these, we drain to Twilio
- Drain TTS audio from tts_audio_queue and forward it to Twilio as media events

NOT responsible for:
- Deciding when to speak or listen (State Controller owns that)
- Calling generate_response() or any LLM
- Calling tts_client or asr_client directly
- Field extraction or recovery prompts

The existing VoiceSessionManager (session_manager.py) is UNTOUCHED.
The webhook routes to StreamIngester only when FSM_PIPELINE_ENABLED is True.
Old and new paths run in parallel during migration phases A-D.

Audio queues
------------
asr_audio_queue: asyncio.Queue[bytes | None]
    - Ingester pushes PCM16@16kHz frames when asr_active is True
    - None sentinel = end of caller turn (ASR should finalize)
    - ASR Consumer pops; discards when inactive

tts_audio_queue: asyncio.Queue[bytes | None]
    - TTS Consumer pushes μ-law@8kHz audio chunks
    - None sentinel = TTS done for this request
    - Ingester drains and sends to Twilio as media events

State flags (set by consumers, read by Ingester)
-----------
session.asr_active   — True while ASR Consumer has an open ASR stream
session.tts_active   — True while TTS Consumer is streaming audio
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import webrtcvad
from fastapi import WebSocket
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.models import Agent, Call, CallDirection, CallStatus
from app.services.realtime.audio import mulaw_to_pcm16, pcm16_to_mulaw, resample_pcm16
from app.services.streams.event_schemas import (
    AuditLogPayload,
    AuditLogEvent,
    CallEndedPayload,
    CallEndedEvent,
    CallIncomingPayload,
    CallIncomingEvent,
    GreetingCompletePayload,
    GreetingCompleteEvent,
    make_event,
)
from app.services.asr.consumer import asr_consumer
from app.services.audit.consumer import audit_consumer
from app.services.state_controller.controller import state_controller
from app.services.streams.publisher import StreamPublisher
from app.services.tts.consumer import tts_consumer
from app.services.telephony.event_sink import call_event_sink

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Audio constants — match session_manager.py exactly
# ---------------------------------------------------------------------------
TWILIO_FRAME_BYTES = 160
TWILIO_SAMPLE_RATE = 8000
ASR_SAMPLE_RATE = 16000
MIN_SPEECH_FRAMES = 2
END_OF_TURN_SILENCE_FRAMES = 40
MIN_BARGE_IN_FRAMES = 4   # consecutive voiced frames required to trigger barge-in
BARGE_IN_GRACE_SECONDS = 1.5  # ignore barge-in for this long after TTS starts (PSTN echo guard)
TTS_MEDIA_CHUNK_BYTES = 640
RECENT_FRAME_BUFFER = 10

# Silence timeout: if caller doesn't speak within this many seconds of
# asr.start_listen, the State Controller should emit timeout.silence.
# This is advisory — the State Controller owns the decision.
VAD_DEAD_AIR_REPORT_SECONDS = 6


def _build_vad() -> webrtcvad.Vad:
    vad = webrtcvad.Vad()
    vad.set_mode(2)
    return vad


# ---------------------------------------------------------------------------
# Session dataclass — slim, no AI state
# ---------------------------------------------------------------------------

@dataclass
class IngesterSession:
    call_id: str
    session_id: str
    tenant_id: str

    # Twilio stream
    stream_sid: str | None = None

    # Audio queues — shared with consumers
    asr_audio_queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    tts_audio_queue: asyncio.Queue = field(default_factory=asyncio.Queue)

    # WebSocket send lock (prevents interleaved sends)
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    # VAD state
    vad: webrtcvad.Vad = field(default_factory=_build_vad)
    twilio_audio_buffer: bytearray = field(default_factory=bytearray)
    pre_speech_frames: deque = field(default_factory=lambda: deque(maxlen=RECENT_FRAME_BUFFER))
    consecutive_voiced_frames: int = 0
    consecutive_silence_frames: int = 0
    asr_resample_state: tuple | None = None

    # State flags — written by consumers, read by Ingester
    asr_active: bool = False   # True = ASR Consumer has an open stream → send audio
    tts_active: bool = False   # True = TTS Consumer is playing audio
    tts_audio_started: bool = False  # True after first outbound TTS media frame is sent

    # Barge-in: set by Ingester when caller speaks during TTS
    barge_in_requested: bool = False
    barge_in_voiced_frames: int = 0   # debounce counter
    barge_in_grace_until: float = 0.0  # monotonic timestamp; barge-in blocked until this passes

    # Stash for call.incoming payload — published when stream_sid is set, not before
    _call_incoming_payload: Any = field(default=None)

    # Telemetry
    call_started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    frames_received: int = 0
    vad_speech_events: int = 0
    vad_silence_events: int = 0
    dead_air_reported: bool = False


# ---------------------------------------------------------------------------
# StreamIngester
# ---------------------------------------------------------------------------

class StreamIngester:
    """
    Thin Twilio WebSocket handler for the FSM pipeline.
    See module docstring for full contract.
    """

    def __init__(self) -> None:
        self._settings = get_settings()

    async def _get_redis(self) -> Redis | None:
        if not self._settings.redis_streams_enabled:
            return None
        try:
            redis = Redis.from_url(self._settings.redis_url, decode_responses=True)
            return redis
        except Exception as exc:
            logger.warning(
                'ingester.redis.connect_failed',
                extra={'correlation_id': '', 'tenant_id': '', 'call_id': '', 'error': str(exc)},
            )
            return None

    async def _send_to_twilio(
        self,
        websocket: WebSocket,
        session: IngesterSession,
        payload: dict,
    ) -> None:
        async with session.send_lock:
            try:
                await websocket.send_json(payload)
            except Exception as exc:
                logger.debug(
                    'ingester.ws.send_failed',
                    extra={
                        'correlation_id': '', 'tenant_id': '',
                        'call_id': session.call_id, 'error': str(exc),
                    },
                )

    async def _drain_tts_audio(
        self,
        websocket: WebSocket,
        session: IngesterSession,
    ) -> None:
        """
        Background task: reads μ-law audio from tts_audio_queue,
        forwards it to Twilio as media events.
        None sentinel = this TTS request is done.
        """
        while True:
            chunk = await session.tts_audio_queue.get()
            if chunk is None:
                # TTS complete for this request — stay alive for next
                session.tts_active = False
                session.tts_audio_started = False
                session.barge_in_requested = False
                session.barge_in_voiced_frames = 0
                session.barge_in_grace_until = 0.0  # reset for next TTS utterance
                continue
            if not session.stream_sid:
                continue
            if not session.tts_audio_started:
                session.tts_audio_started = True
                # Start grace window from first outbound audio, not from tts_active flip.
                session.barge_in_grace_until = time.monotonic() + BARGE_IN_GRACE_SECONDS
                logger.info('ingester.tts.first_audio_sent', extra={
                    'correlation_id': '', 'tenant_id': session.tenant_id,
                    'call_id': session.call_id, 'stream_sid': session.stream_sid or '',
                })
            for offset in range(0, len(chunk), TTS_MEDIA_CHUNK_BYTES):
                sub = chunk[offset: offset + TTS_MEDIA_CHUNK_BYTES]
                await self._send_to_twilio(
                    websocket,
                    session,
                    {
                        'event': 'media',
                        'streamSid': session.stream_sid,
                        'media': {'payload': base64.b64encode(sub).decode()},
                    },
                )

    async def _process_audio_frame(
        self,
        session: IngesterSession,
        websocket: WebSocket,
        mulaw_audio: bytes,
    ) -> dict[str, Any] | None:
        """
        VAD-process one Twilio audio frame.
        Returns a dict describing the VAD event, or None if no event.
        Callers use the dict to emit events to the stream.
        """
        session.twilio_audio_buffer.extend(mulaw_audio)
        session.frames_received += 1

        vad_event: dict[str, Any] | None = None

        while len(session.twilio_audio_buffer) >= TWILIO_FRAME_BYTES:
            frame_mulaw = bytes(session.twilio_audio_buffer[:TWILIO_FRAME_BYTES])
            del session.twilio_audio_buffer[:TWILIO_FRAME_BYTES]

            pcm_frame_8k = mulaw_to_pcm16(frame_mulaw)
            is_speech = session.vad.is_speech(pcm_frame_8k, TWILIO_SAMPLE_RATE)

            # Barge-in: caller speaks while TTS is active (debounced).
            # While TTS is active we skip normal speech/ASR detection entirely —
            # only count toward barge-in threshold.
            if session.tts_active and session.tts_audio_started and not session.barge_in_requested:
                now = time.monotonic()
                if now >= session.barge_in_grace_until:
                    if is_speech:
                        session.barge_in_voiced_frames += 1
                    else:
                        session.barge_in_voiced_frames = 0
                    if session.barge_in_voiced_frames >= MIN_BARGE_IN_FRAMES:
                        session.barge_in_requested = True
                        session.barge_in_voiced_frames = 0
                        if session.stream_sid:
                            await self._send_to_twilio(
                                websocket, session,
                                {'event': 'clear', 'streamSid': session.stream_sid},
                            )
                        session.vad_speech_events += 1
                        vad_event = {'type': 'barge_in', 'timestamp_ms': int(time.time() * 1000)}
                continue  # always skip ASR detection while TTS is playing

            if not session.asr_active:
                # Accumulate pre-speech buffer for look-back
                session.pre_speech_frames.append(frame_mulaw)
                if is_speech:
                    session.consecutive_voiced_frames += 1
                    if session.consecutive_voiced_frames >= MIN_SPEECH_FRAMES:
                        # Speech onset — flush pre-speech buffer to ASR queue
                        session.asr_active = True
                        session.vad_speech_events += 1
                        for buffered_frame in list(session.pre_speech_frames):
                            buffered_pcm = mulaw_to_pcm16(buffered_frame)
                            pcm_16k, session.asr_resample_state = resample_pcm16(
                                buffered_pcm, from_rate=TWILIO_SAMPLE_RATE, to_rate=ASR_SAMPLE_RATE,
                                state=session.asr_resample_state,
                            )
                            await session.asr_audio_queue.put(pcm_16k)
                        session.pre_speech_frames.clear()
                        session.consecutive_silence_frames = 0
                        vad_event = {'type': 'speech_started', 'timestamp_ms': int(time.time() * 1000)}
                else:
                    session.consecutive_voiced_frames = 0
                continue

            # ASR is active — forward every frame
            pcm_16k, session.asr_resample_state = resample_pcm16(
                pcm_frame_8k, from_rate=TWILIO_SAMPLE_RATE, to_rate=ASR_SAMPLE_RATE,
                state=session.asr_resample_state,
            )
            await session.asr_audio_queue.put(pcm_16k)

            if is_speech:
                session.consecutive_silence_frames = 0
            else:
                session.consecutive_silence_frames += 1
                if session.consecutive_silence_frames >= END_OF_TURN_SILENCE_FRAMES:
                    # End of caller turn — signal ASR Consumer to finalize
                    session.asr_active = False
                    session.consecutive_silence_frames = 0
                    session.consecutive_voiced_frames = 0
                    session.pre_speech_frames.clear()
                    session.asr_resample_state = None
                    await session.asr_audio_queue.put(None)  # end-of-turn sentinel
                    session.vad_silence_events += 1
                    vad_event = {'type': 'silence_end_of_turn', 'timestamp_ms': int(time.time() * 1000)}

        return vad_event

    async def handle_ws(
        self,
        websocket: WebSocket,
        call_id: str,
        db: AsyncSession,
    ) -> None:
        """
        Main WebSocket handler — same signature as VoiceSessionManager.handle_ws().
        The webhook routes here when FSM pipeline is active.
        """
        await websocket.accept()

        # Load call record
        call = (await db.execute(select(Call).where(Call.id == call_id))).scalar_one_or_none()
        if not call:
            logger.warning('ingester.ws.call_not_found', extra={
                'correlation_id': '', 'tenant_id': '', 'call_id': call_id,
            })
            await websocket.close(code=4404)
            return

        # Load agent record
        agent = (await db.execute(
            select(Agent).where(Agent.id == call.agent_id, Agent.tenant_id == call.tenant_id)
        )).scalar_one_or_none()
        if not agent:
            logger.warning('ingester.ws.agent_not_found', extra={
                'correlation_id': '', 'tenant_id': str(call.tenant_id), 'call_id': call_id,
            })
            await websocket.close(code=4404)
            return

        # Session identity — reuse existing session_id if the call has one
        session_id = call.session_id or str(uuid.uuid4())
        session = IngesterSession(
            call_id=call_id,
            session_id=session_id,
            tenant_id=str(call.tenant_id),
        )

        # Update call record
        call.session_id = session_id
        call.status = CallStatus.in_progress
        await db.commit()

        # Connect to Redis and create publisher
        redis = await self._get_redis()
        publisher: StreamPublisher | None = None
        if redis is not None:
            publisher = StreamPublisher(
                redis=redis,
                session_id=session_id,
                call_id=call_id,
            )

        telephony_context = (call.context_payload or {}).get('telephony', {})
        agent_config_snapshot = (agent.policy_config or {}).get('runtime', {})

        # call.incoming is published inside _event_loop() when Twilio sends the 'start'
        # event (i.e. stream_sid is set).  Publishing it here (before stream_sid is known)
        # caused the State Controller to emit tts.speak before stream_sid was available,
        # so every audio chunk was silently dropped by _drain_tts_audio.
        # We stash the payload on the session so _event_loop can use it.
        session._call_incoming_payload = CallIncomingPayload(
            from_number=call.from_number,
            to_number=call.to_number,
            call_sid=call.external_call_id or '',
            agent_id=str(agent.id),
            tenant_id=str(call.tenant_id),
            resolution_source=(telephony_context.get('resolver') or {}).get('source', 'unknown'),
            agent_config_snapshot=agent_config_snapshot,
            correlation_id=(telephony_context.get('webhook') or {}).get('correlation_id', ''),
        )

        logger.info('ingester.session.started', extra={
            'correlation_id': '',
            'tenant_id': str(call.tenant_id),
            'call_id': call_id,
            'session_id': session_id,
            'stream_key': publisher.stream_key if publisher else '(redis disabled)',
        })

        # Start TTS audio drainer task
        tts_drain_task = asyncio.create_task(
            self._drain_tts_audio(websocket, session),
            name=f'tts_drain:{session_id}',
        )

        # Each consumer needs its own Redis connection for blocking XREADGROUP.
        redis_asr = await self._get_redis()
        redis_tts = await self._get_redis()
        redis_audit = await self._get_redis()

        # Start State Controller task (FSM driver — emits tts.speak / asr.start_listen)
        ctrl_task = None
        asr_task = None
        tts_task = None
        audit_task = None
        if publisher is not None and redis is not None:
            ctrl_task = asyncio.create_task(
                state_controller.run(
                    session_id=session_id,
                    call_id=call_id,
                    agent=agent,
                    tenant_id=str(call.tenant_id),
                    redis=redis,
                    publisher=publisher,
                ),
                name=f'state_ctrl:{session_id}',
            )
            if redis_asr is not None:
                asr_task = asyncio.create_task(
                    asr_consumer.run(
                        session_id=session_id,
                        call_id=call_id,
                        tenant_id=str(call.tenant_id),
                        ingester_session=session,
                        redis=redis_asr,
                        publisher=publisher,
                    ),
                    name=f'asr_consumer:{session_id}',
                )
            if redis_tts is not None:
                tts_task = asyncio.create_task(
                    tts_consumer.run(
                        session_id=session_id,
                        call_id=call_id,
                        tenant_id=str(call.tenant_id),
                        ingester_session=session,
                        redis=redis_tts,
                        publisher=publisher,
                    ),
                    name=f'tts_consumer:{session_id}',
                )
            if redis_audit is not None:
                audit_task = asyncio.create_task(
                    audit_consumer.run(
                        session_id=session_id,
                        call_id=call_id,
                        tenant_id=str(call.tenant_id),
                        redis=redis_audit,
                        publisher=publisher,
                    ),
                    name=f'audit_consumer:{session_id}',
                )

        try:
            await self._event_loop(
                websocket=websocket,
                session=session,
                db=db,
                call=call,
                agent=agent,
                publisher=publisher,
            )
        except Exception:
            call.status = CallStatus.failed
            call.ended_at = datetime.now(timezone.utc)
            await db.commit()
        finally:
            tts_drain_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await tts_drain_task
            if ctrl_task is not None:
                ctrl_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await ctrl_task
            if asr_task is not None:
                asr_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await asr_task
            if tts_task is not None:
                tts_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await tts_task
            if redis_asr is not None:
                with contextlib.suppress(Exception):
                    await redis_asr.aclose()
            if audit_task is not None:
                audit_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await audit_task
            if redis_tts is not None:
                with contextlib.suppress(Exception):
                    await redis_tts.aclose()
            if redis_audit is not None:
                with contextlib.suppress(Exception):
                    await redis_audit.aclose()

            # Finalize call
            if call.ended_at is None:
                call.ended_at = datetime.now(timezone.utc)
            await db.commit()

            # Publish call.ended
            if publisher is not None:
                duration = None
                if call.started_at and call.ended_at:
                    duration = round((call.ended_at - call.started_at).total_seconds(), 2)
                await publisher.publish(make_event(
                    CallEndedEvent,
                    session_id=session_id,
                    call_id=call_id,
                    payload=CallEndedPayload(
                        final_state='unknown',   # State Controller knows the actual state
                        outcome=call.outcome or call.status.value,
                        duration_seconds=duration,
                        escalation_reason=call.escalation_reason,
                    ),
                ))

            call_event_sink.close_call(call_id, call.external_call_id or '')

            if redis is not None:
                with contextlib.suppress(Exception):
                    await redis.aclose()

            with contextlib.suppress(Exception):
                await websocket.close()

            logger.info('ingester.session.ended', extra={
                'correlation_id': '',
                'tenant_id': str(call.tenant_id),
                'call_id': call_id,
                'session_id': session_id,
                'frames_received': session.frames_received,
                'vad_speech_events': session.vad_speech_events,
                'vad_silence_events': session.vad_silence_events,
            })

    async def _event_loop(
        self,
        *,
        websocket: WebSocket,
        session: IngesterSession,
        db: AsyncSession,
        call: Call,
        agent: Agent,
        publisher: StreamPublisher | None,
    ) -> None:
        """
        Main Twilio event loop. Handles all WebSocket events from Twilio.
        The State Controller (spawned separately) handles all AI decisions.
        """
        while True:
            try:
                event = await websocket.receive_json()
            except Exception:
                break

            event_type = event.get('event')

            if event_type == 'connected':
                proto = (event.get('connected') or {}).get('protocol', '')
                logger.debug('ingester.twilio.connected', extra={
                    'correlation_id': '', 'tenant_id': session.tenant_id,
                    'call_id': session.call_id, 'protocol': proto,
                })
                continue

            if event_type == 'mark':
                # Twilio ACK for a mark event we sent — passthrough
                continue

            if event_type == 'start':
                start_payload = event.get('start') or {}
                session.stream_sid = start_payload.get('streamSid')
                logger.info('ingester.twilio.stream_started', extra={
                    'correlation_id': '', 'tenant_id': session.tenant_id,
                    'call_id': session.call_id, 'stream_sid': session.stream_sid or '',
                })
                # NOW publish call.incoming — stream_sid is set so TTS audio will not
                # be dropped by the drain task.  State Controller reads this event and
                # transitions S0→S1, which triggers the greeting tts.speak.
                if publisher is not None and hasattr(session, '_call_incoming_payload'):
                    await publisher.publish(make_event(
                        CallIncomingEvent,
                        session_id=session.session_id,
                        call_id=session.call_id,
                        payload=session._call_incoming_payload,
                    ))
                continue

            if event_type == 'media':
                raw_payload = (event.get('media') or {}).get('payload', '')
                if not raw_payload:
                    continue
                mulaw_audio = base64.b64decode(raw_payload)
                vad_event = await self._process_audio_frame(session, websocket, mulaw_audio)

                # Emit VAD events to the stream so State Controller can track
                # silence timeout and barge-in for FSM logic
                if vad_event is not None and publisher is not None:
                    vad_type = vad_event.get('type', '')
                    # We use call_event_sink for lightweight vad telemetry (not a full FSM event type)
                    # The State Controller monitors asr.transcript / timeout.silence, not raw VAD.
                    # For now, log the VAD event for observability.
                    call_event_sink.record_event(
                        call_event_sink.build_event(
                            event_type=f'vad.{vad_type}',
                            level='info',
                            call_id=session.call_id,
                            call_sid=call.external_call_id or '',
                            tenant_id=session.tenant_id,
                            direction=call.direction.value,
                            route=call.direction.value,
                            session_id=session.session_id,
                            vad_event=vad_event,
                        )
                    )
                continue

            if event_type == 'dtmf':
                digit = (event.get('dtmf') or {}).get('digit')
                call_event_sink.record_event(
                    call_event_sink.build_event(
                        event_type='transcript.dtmf.final',
                        level='info',
                        call_id=session.call_id,
                        call_sid=call.external_call_id or '',
                        tenant_id=session.tenant_id,
                        direction=call.direction.value,
                        route=call.direction.value,
                        speaker='dtmf',
                        text=f'DTMF:{digit}',
                        is_final=True,
                    )
                )
                continue

            if event_type == 'stop':
                logger.info('ingester.twilio.stream_stopped', extra={
                    'correlation_id': '', 'tenant_id': session.tenant_id,
                    'call_id': session.call_id,
                })
                if call.status != CallStatus.escalated:
                    call.status = CallStatus.completed
                call.ended_at = datetime.now(timezone.utc)
                await db.commit()
                break

            # Unknown event — log and continue (never break the loop on unknown events)
            logger.debug('ingester.twilio.unknown_event', extra={
                'correlation_id': '', 'tenant_id': session.tenant_id,
                'call_id': session.call_id, 'event_type': event_type or '',
            })


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

stream_ingester = StreamIngester()
