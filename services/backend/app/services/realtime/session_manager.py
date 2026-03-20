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
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.metrics import ASR_LATENCY, LLM_LATENCY, TTS_LATENCY
from app.models.models import Agent, Call, CallStatus, TranscriptSegment
from app.services.agent_runtime.runtime import AgentTurn, agent_runtime
from app.services.asr.client import ASRFinalTranscript, ASRStream, asr_client
from app.services.realtime.audio import (
    mulaw_to_pcm16,
    pcm16_to_mulaw,
    resample_pcm16,
    strip_control_markup,
    wav_to_pcm16,
)
from app.services.telephony.event_sink import call_event_sink
from app.services.telephony.telemetry import CallTelemetry
from app.services.tts.client import tts_client

logger = get_logger(__name__)

TWILIO_FRAME_BYTES = 160
TWILIO_SAMPLE_RATE = 8000
ASR_SAMPLE_RATE = 16000
MIN_SPEECH_FRAMES = 2
END_OF_TURN_SILENCE_FRAMES = 30
TTS_MEDIA_CHUNK_BYTES = 640
RECENT_FRAME_BUFFER = 10
RECOVERY_PROMPT = 'Sorry, I missed that. Could you repeat that?'
MAX_FIELD_RETRIES = 2
MAX_CONSECUTIVE_RECOVERY_TURNS = 4
INITIAL_DEAD_AIR_SECONDS = 6
HELLO_LOOP_THRESHOLD = 3
CARRIER_PROMPT_HINTS = (
    'verification code',
    'google voice',
    'press 1',
    'press any key',
    'pin',
    'voicemail',
    'mailbox',
    'call has been forwarded',
    'record your name',
)
GREETING_ONLY_UTTERANCES = {'hello', 'hello?', 'hi', 'hi there', 'hey'}


def _build_vad() -> webrtcvad.Vad:
    vad = webrtcvad.Vad()
    vad.set_mode(2)
    return vad


@dataclass
class VoiceSession:
    call_id: str
    tenant_id: str
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    telemetry: CallTelemetry | None = None
    stream_sid: str | None = None
    tts_task: asyncio.Task | None = None
    speaking: bool = False
    collected_fields: dict[str, str] = field(default_factory=dict)
    prompted_field: str | None = None
    field_retry_counts: dict[str, int] = field(default_factory=dict)
    notable_errors: list[str] = field(default_factory=list)
    caller_turns: int = 0
    agent_turns: int = 0
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    vad: webrtcvad.Vad = field(default_factory=_build_vad)
    twilio_audio_buffer: bytearray = field(default_factory=bytearray)
    pre_speech_frames: deque[bytes] = field(default_factory=lambda: deque(maxlen=RECENT_FRAME_BUFFER))
    asr_stream: ASRStream | None = None
    asr_resample_state: tuple | None = None
    caller_turn_active: bool = False
    consecutive_voiced_frames: int = 0
    consecutive_silence_frames: int = 0
    hello_repetitions: int = 0
    initial_dead_air_reported: bool = False
    tts_requests: int = 0
    asr_turns_started: int = 0
    llm_requests: int = 0
    last_asr_partial: str = ''
    last_asr_final: str = ''
    last_recovery_prompt: str = ''
    last_retry_reason: str = ''
    consecutive_recovery_turns: int = 0
    interrupted_turn: bool = False
    llm_mode: str = 'scripted'
    detected_intent: str = 'general'
    last_response_source: str = 'scripted_backend_flow'


class VoiceSessionManager:
    def __init__(self) -> None:
        self.sessions: dict[str, VoiceSession] = {}

    async def get_or_create(self, call_id: str, tenant_id: str) -> VoiceSession:
        if call_id not in self.sessions:
            self.sessions[call_id] = VoiceSession(call_id=call_id, tenant_id=tenant_id)
        return self.sessions[call_id]

    def _record_error(self, session: VoiceSession, error_code: str) -> None:
        if error_code not in session.notable_errors:
            session.notable_errors.append(error_code)
        if session.telemetry is not None:
            session.telemetry.add_anomaly(error_code)

    def _telemetry_context(self, session: VoiceSession) -> dict[str, Any]:
        if session.telemetry is None:
            return {'correlation_id': '', 'tenant_id': session.tenant_id}
        return session.telemetry.payload()

    def _retry_reason_from_transcript(self, *, session: VoiceSession, transcript_text: str | None) -> str:
        normalized = (transcript_text or '').strip().lower()
        if session.interrupted_turn:
            return 'caller_interruption'
        if session.last_asr_partial and not normalized:
            return 'partial_unclear_speech'
        if any(hint in normalized for hint in CARRIER_PROMPT_HINTS):
            return 'line_artifact'
        if not normalized:
            return 'no_speech'
        return 'unusable_input'

    def _log_recovery_prompt(
        self,
        *,
        session: VoiceSession,
        retry_reason: str,
        retry_count: int,
        active_field: str | None,
        chosen_recovery_prompt: str,
        progress_made: bool,
    ) -> None:
        if session.telemetry is None:
            return
        session.telemetry.log(
            'call.recovery.selected',
            retry_reason=retry_reason,
            retry_count=retry_count,
            active_field=active_field or '',
            last_asr_partial=session.last_asr_partial,
            last_asr_final=session.last_asr_final,
            chosen_recovery_prompt=chosen_recovery_prompt,
            progress_made=progress_made,
            consecutive_recovery_turns=session.consecutive_recovery_turns,
        )

    def _handle_passthrough_telephony_event(
        self,
        *,
        session: VoiceSession,
        event: dict[str, Any],
    ) -> bool:
        event_type = event.get('event')
        if event_type == 'connected':
            connected_payload = event.get('connected') or {}
            if session.telemetry is not None:
                session.telemetry.log(
                    'call.telephony.stream.connected',
                    media_stream_event='connected',
                    protocol=connected_payload.get('protocol', ''),
                    version=connected_payload.get('version', ''),
                )
            return True

        if event_type == 'mark':
            mark_payload = event.get('mark') or {}
            if session.telemetry is not None:
                session.telemetry.log(
                    'call.telephony.stream.mark',
                    media_stream_event='mark',
                    mark_name=mark_payload.get('name', ''),
                )
            return True

        return False

    def _analyze_initial_transcript(self, *, session: VoiceSession, transcript_text: str) -> None:
        normalized = transcript_text.strip().lower()
        if not normalized:
            return

        if any(hint in normalized for hint in CARRIER_PROMPT_HINTS):
            self._record_error(session, 'carrier_or_ivr_prompt_detected')
        if normalized in GREETING_ONLY_UTTERANCES:
            session.hello_repetitions += 1
            if session.hello_repetitions >= HELLO_LOOP_THRESHOLD and session.telemetry is not None:
                session.telemetry.add_anomaly(
                    'repeated_hello_loop',
                    transcript_text=transcript_text,
                    hello_repetitions=session.hello_repetitions,
                )
        else:
            session.hello_repetitions = 0

    async def _handle_asr_event(self, *, session: VoiceSession, event: dict[str, Any]) -> None:
        if session.telemetry is None:
            return

        event_type = event.get('type')
        text = (event.get('text') or '').strip()
        if event_type == 'partial_transcript' and text:
            session.last_asr_partial = text
            session.telemetry.mark('asr_first_partial', transcript_text=text)
        elif event_type == 'final_transcript' and text:
            session.last_asr_final = text
            session.telemetry.mark('asr_first_final', transcript_text=text)
            if session.caller_turns == 0:
                self._analyze_initial_transcript(session=session, transcript_text=text)
        elif event_type == 'error':
            session.telemetry.add_anomaly(
                'asr_stream_error',
                asr_error=event.get('message', 'ASR stream error'),
            )

    async def _send_twilio_event(self, websocket: WebSocket, session: VoiceSession, payload: dict) -> None:
        async with session.send_lock:
            await websocket.send_json(payload)

    async def stop_tts_for_barge_in(self, websocket: WebSocket, session: VoiceSession) -> None:
        if session.tts_task and not session.tts_task.done():
            session.tts_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await session.tts_task
            session.speaking = False
            session.interrupted_turn = True
            self._record_error(session, 'barge_in')
            if session.stream_sid:
                await self._send_twilio_event(
                    websocket,
                    session,
                    {
                        'event': 'clear',
                        'streamSid': session.stream_sid,
                    },
                )
            if session.telemetry is not None:
                session.telemetry.add_anomaly('barge_in_detected')

    def _wav_chunk_to_mulaw(self, wav_chunk: bytes) -> bytes:
        try:
            pcm_audio, sample_rate = wav_to_pcm16(wav_chunk)
        except Exception:
            pcm_audio = wav_chunk
            sample_rate = 24000
        pcm_8k, _ = resample_pcm16(pcm_audio, from_rate=sample_rate, to_rate=TWILIO_SAMPLE_RATE)
        return pcm16_to_mulaw(pcm_8k)

    async def send_tts(
        self,
        websocket: WebSocket,
        session: VoiceSession,
        agent: Agent,
        text: str,
        *,
        llm_mode: str | None = None,
        response_source: str | None = None,
    ) -> None:
        if not session.stream_sid:
            return

        if session.tts_task and not session.tts_task.done():
            await self.stop_tts_for_barge_in(websocket, session)

        sanitized_text = strip_control_markup(text)
        if not sanitized_text:
            sanitized_text = RECOVERY_PROMPT
        resolved_llm_mode = llm_mode or session.llm_mode
        resolved_response_source = response_source or session.last_response_source
        if session.telemetry is not None and sanitized_text != text:
            session.telemetry.add_anomaly(
                'tts_text_sanitized',
                original_chars=len(text),
                sanitized_chars=len(sanitized_text),
            )

        async def _stream() -> None:
            session.speaking = True
            t0 = time.perf_counter()
            session.tts_requests += 1
            tts_request_index = session.tts_requests
            tts_provider = agent_runtime.tts_provider_for_agent(agent=agent)
            tts_model = agent_runtime.tts_model_for_agent(agent=agent)
            tts_voice = agent_runtime.tts_voice_for_agent(agent=agent)
            tts_metadata = agent_runtime.tts_metadata_for_agent(agent=agent)
            first_chunk_logged = False
            if session.telemetry is not None:
                session.telemetry.log(
                    'call.response.spoken',
                    llm_mode=resolved_llm_mode,
                    response_source=resolved_response_source,
                    detected_intent=session.detected_intent,
                    tts_request_index=tts_request_index,
                    tts_provider=tts_provider,
                    tts_model=tts_model,
                    tts_voice=tts_voice,
                    text_preview=sanitized_text[:160],
                )
                session.telemetry.log(
                    'call.tts.request.start',
                    tts_request_index=tts_request_index,
                    tts_provider=tts_provider,
                    tts_model=tts_model,
                    tts_voice=tts_voice,
                    llm_mode=resolved_llm_mode,
                    agent_voice=tts_voice,
                    text_preview=sanitized_text[:160],
                )
                session.telemetry.mark(
                    'tts_request_started',
                    tts_provider=tts_provider,
                    tts_model=tts_model,
                    tts_voice=tts_voice,
                    agent_voice=tts_voice,
                    text_preview=sanitized_text[:160],
                )
            try:
                async for wav_chunk in tts_client.stream_tts(
                    text=sanitized_text,
                    call_id=session.call_id,
                    agent_id=str(agent.id),
                    provider=tts_provider,
                    model=tts_model,
                    voice=tts_voice,
                    metadata=tts_metadata,
                ):
                    mulaw_audio = self._wav_chunk_to_mulaw(wav_chunk)
                    for index in range(0, len(mulaw_audio), TTS_MEDIA_CHUNK_BYTES):
                        if session.telemetry is not None and not first_chunk_logged:
                            first_chunk_logged = True
                            session.telemetry.log(
                                'call.tts.audio.first_chunk',
                                tts_request_index=tts_request_index,
                                tts_provider=tts_provider,
                                tts_model=tts_model,
                                tts_voice=tts_voice,
                                chunk_bytes=len(mulaw_audio),
                            )
                        if session.telemetry is not None and 'tts_first_audio_chunk' not in session.telemetry.timestamps:
                            session.telemetry.mark('tts_first_audio_chunk', chunk_bytes=len(mulaw_audio))
                        payload = base64.b64encode(mulaw_audio[index : index + TTS_MEDIA_CHUNK_BYTES]).decode()
                        await self._send_twilio_event(
                            websocket,
                            session,
                            {
                                'event': 'media',
                                'streamSid': session.stream_sid,
                                'media': {'payload': payload},
                            },
                        )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._record_error(session, 'tts_stream_error')
                if session.telemetry is not None:
                    session.telemetry.warning(
                        'call.tts.request.failed',
                        tts_provider=tts_provider,
                        tts_model=tts_model,
                        tts_voice=tts_voice,
                        error_type=type(exc).__name__,
                        error=str(exc),
                    )
            else:
                await self._send_twilio_event(
                    websocket,
                    session,
                    {
                        'event': 'mark',
                        'streamSid': session.stream_sid,
                        'mark': {'name': 'tts_done'},
                    },
                )
            finally:
                if session.telemetry is not None:
                    session.telemetry.log(
                        'call.tts.request.end',
                        tts_request_index=tts_request_index,
                        tts_provider=tts_provider,
                        tts_model=tts_model,
                        tts_voice=tts_voice,
                        latency_ms=round(max(0.0, (time.perf_counter() - t0) * 1000), 2),
                    )
                    session.telemetry.mark(
                        'tts_request_completed',
                        tts_provider=tts_provider,
                        tts_model=tts_model,
                        tts_voice=tts_voice,
                        latency_ms=round(max(0.0, (time.perf_counter() - t0) * 1000), 2),
                    )
                TTS_LATENCY.observe(time.perf_counter() - t0)
                session.speaking = False

        session.tts_task = asyncio.create_task(_stream())

    async def _start_asr_turn(self, *, session: VoiceSession, websocket: WebSocket) -> None:
        if session.speaking:
            await self.stop_tts_for_barge_in(websocket, session)
        session.last_asr_partial = ''
        session.last_asr_final = ''
        session.asr_turns_started += 1
        session.asr_stream = await asr_client.start_stream(
            call_id=session.call_id,
            on_event=lambda event: self._handle_asr_event(session=session, event=event),
        )
        session.asr_resample_state = None
        session.caller_turn_active = True
        session.consecutive_silence_frames = 0
        if session.telemetry is not None:
            session.telemetry.log(
                'call.asr.stream.started',
                asr_turn_index=session.asr_turns_started,
                asr_provider='aether_voice',
            )
            session.telemetry.mark('asr_started', asr_provider='aether_voice')

    async def _send_frame_to_asr(self, session: VoiceSession, pcm_frame_8k: bytes) -> None:
        if session.asr_stream is None:
            return
        pcm_frame_16k, session.asr_resample_state = resample_pcm16(
            pcm_frame_8k,
            from_rate=TWILIO_SAMPLE_RATE,
            to_rate=ASR_SAMPLE_RATE,
            state=session.asr_resample_state,
        )
        await session.asr_stream.send_audio_frame(pcm_frame_16k)

    async def _persist_caller_turn(
        self,
        *,
        session: VoiceSession,
        db: AsyncSession,
        call: Call,
        transcript: ASRFinalTranscript,
    ) -> None:
        db.add(
            TranscriptSegment(
                tenant_id=session.tenant_id,
                call_id=call.id,
                speaker='caller',
                text=transcript.text,
                is_final=True,
                started_ms=transcript.started_ms,
                ended_ms=transcript.ended_ms,
            )
        )
        session.caller_turns += 1
        await db.flush()
        if session.telemetry is not None:
            call_event_sink.record_event(
                call_event_sink.build_event(
                    event_type='transcript.caller.final',
                    level='info',
                    call_id=str(call.id),
                    call_sid=call.external_call_id or '',
                    tenant_id=session.tenant_id,
                    direction=session.telemetry.route,
                    route=session.telemetry.route,
                    agent_id=session.telemetry.resolved_agent_id,
                    agent_name=session.telemetry.resolved_agent_name,
                    correlation_id=session.telemetry.correlation_id,
                    from_number=call.from_number,
                    to_number=call.to_number,
                    asr_provider='aether_voice',
                    speaker='caller',
                    text=transcript.text,
                    is_final=True,
                    started_ms=transcript.started_ms,
                    ended_ms=transcript.ended_ms,
                )
            )

    async def _persist_agent_turn(
        self,
        *,
        session: VoiceSession,
        db: AsyncSession,
        agent: Agent,
        call: Call,
        text: str,
    ) -> None:
        sanitized_text = strip_control_markup(text) or RECOVERY_PROMPT
        db.add(
            TranscriptSegment(
                tenant_id=session.tenant_id,
                call_id=call.id,
                speaker='agent',
                text=sanitized_text,
                is_final=True,
            )
        )
        session.agent_turns += 1
        await db.flush()
        if session.telemetry is not None:
            call_event_sink.record_event(
                call_event_sink.build_event(
                    event_type='transcript.agent.final',
                    level='info',
                    call_id=str(call.id),
                    call_sid=call.external_call_id or '',
                    tenant_id=session.tenant_id,
                    direction=session.telemetry.route,
                    route=session.telemetry.route,
                    agent_id=session.telemetry.resolved_agent_id,
                    agent_name=session.telemetry.resolved_agent_name,
                    correlation_id=session.telemetry.correlation_id,
                    from_number=call.from_number,
                    to_number=call.to_number,
                    tts_provider='aether_voice',
                    tts_voice=agent_runtime.tts_voice_for_agent(agent=agent),
                    speaker='agent',
                    text=sanitized_text,
                    is_final=True,
                )
            )

    def _next_missing_field(
        self,
        *,
        agent: Agent,
        session: VoiceSession,
        skip_field: str | None = None,
    ) -> str | None:
        missing_fields = agent_runtime.missing_required_fields(agent=agent, collected_fields=session.collected_fields)
        for field_name in missing_fields:
            if field_name != skip_field:
                return field_name
        return None

    async def _recover_missing_field(
        self,
        *,
        websocket: WebSocket,
        session: VoiceSession,
        db: AsyncSession,
        agent: Agent,
        call: Call,
        current_field: str | None,
        retry_reason: str,
        progress_made: bool = False,
    ) -> None:
        session.consecutive_recovery_turns += 1
        session.last_retry_reason = retry_reason
        session.llm_mode = 'fallback'
        session.last_response_source = 'fallback_recovery_prompt'
        if session.telemetry is not None:
            session.telemetry.set_llm_mode(session.llm_mode)

        if not current_field:
            retry_count = session.consecutive_recovery_turns
            prompt = agent_runtime.build_general_recovery_prompt(
                retry_reason=retry_reason,
                retry_count=retry_count,
                previous_prompt=session.last_recovery_prompt,
            )
            if session.consecutive_recovery_turns >= MAX_CONSECUTIVE_RECOVERY_TURNS:
                prompt = agent_runtime.build_connection_check_prompt(previous_prompt=session.last_recovery_prompt)
            session.last_recovery_prompt = prompt
            self._log_recovery_prompt(
                session=session,
                retry_reason=retry_reason,
                retry_count=retry_count,
                active_field=current_field,
                chosen_recovery_prompt=prompt,
                progress_made=progress_made,
            )
            if session.telemetry is not None:
                session.telemetry.log(
                    'call.fallback.engaged',
                    llm_mode=session.llm_mode,
                    detected_intent=session.detected_intent,
                    fallback_reason=retry_reason,
                    response_source=session.last_response_source,
                )
                session.telemetry.log(
                    'call.response.generated',
                    llm_mode=session.llm_mode,
                    detected_intent=session.detected_intent,
                    response_source=session.last_response_source,
                    fallback_reason=retry_reason,
                    text_preview=prompt[:160],
                )
            await self._persist_agent_turn(session=session, db=db, agent=agent, call=call, text=prompt)
            await self.send_tts(
                websocket,
                session,
                agent,
                prompt,
                llm_mode=session.llm_mode,
                response_source=session.last_response_source,
            )
            return

        retry_count = session.field_retry_counts.get(current_field, 0) + 1
        session.field_retry_counts[current_field] = retry_count
        self._record_error(session, f'{current_field}_retry_{retry_count}')

        if session.consecutive_recovery_turns >= MAX_CONSECUTIVE_RECOVERY_TURNS:
            next_field = self._next_missing_field(agent=agent, session=session, skip_field=current_field)
            if next_field:
                prompt = agent_runtime.build_skip_ahead_prompt(
                    agent=agent,
                    field_name=current_field,
                    next_field=next_field,
                )
                session.prompted_field = next_field
            else:
                prompt = agent_runtime.build_connection_check_prompt(previous_prompt=session.last_recovery_prompt)
                session.prompted_field = None
            if session.telemetry is not None:
                session.telemetry.add_fallback(
                    'recovery_ceiling_reached',
                    active_field=current_field,
                    retry_reason=retry_reason,
                )
        elif retry_count <= MAX_FIELD_RETRIES:
            prompt = agent_runtime.build_field_retry_prompt(
                agent=agent,
                field_name=current_field,
                retry_count=retry_count,
                retry_reason=retry_reason,
                previous_prompt=session.last_recovery_prompt,
            )
            session.prompted_field = current_field
        else:
            self._record_error(session, f'{current_field}_capture_exhausted')
            next_field = self._next_missing_field(agent=agent, session=session, skip_field=current_field)
            prompt = agent_runtime.build_skip_ahead_prompt(
                agent=agent,
                field_name=current_field,
                next_field=next_field,
            )
            session.prompted_field = next_field

        session.last_recovery_prompt = prompt
        self._log_recovery_prompt(
            session=session,
            retry_reason=retry_reason,
            retry_count=retry_count,
            active_field=current_field,
            chosen_recovery_prompt=prompt,
            progress_made=progress_made,
        )
        if session.telemetry is not None:
            session.telemetry.log(
                'call.fallback.engaged',
                llm_mode=session.llm_mode,
                detected_intent=session.detected_intent,
                fallback_reason=retry_reason,
                response_source=session.last_response_source,
                active_field=current_field or '',
            )
            session.telemetry.log(
                'call.response.generated',
                llm_mode=session.llm_mode,
                detected_intent=session.detected_intent,
                response_source=session.last_response_source,
                fallback_reason=retry_reason,
                active_field=current_field or '',
                text_preview=prompt[:160],
            )
        await self._persist_agent_turn(session=session, db=db, agent=agent, call=call, text=prompt)
        await self.send_tts(
            websocket,
            session,
            agent,
            prompt,
            llm_mode=session.llm_mode,
            response_source=session.last_response_source,
        )

    def _determine_disposition(self, *, call: Call, agent: Agent, session: VoiceSession) -> str:
        if call.status == CallStatus.escalated or call.outcome == 'transfer_needed':
            return 'transfer_needed'

        missing_fields = agent_runtime.missing_required_fields(agent=agent, collected_fields=session.collected_fields)
        if not (agent.required_fields or {}):
            return call.outcome or 'success'
        if not missing_fields:
            return 'success'
        if session.collected_fields:
            return 'partial_intake'
        return 'failed_intake'

    def _inbound_builder_config(self, *, agent: Agent) -> dict[str, Any]:
        workflow = agent.workflow_dsl or {}
        if not isinstance(workflow, dict):
            return {}
        builder = workflow.get('inbound_builder') or {}
        return builder if isinstance(builder, dict) else {}

    def _build_operator_artifacts(self, *, call: Call, agent: Agent, session: VoiceSession) -> dict[str, Any]:
        builder = self._inbound_builder_config(agent=agent)
        workflow = agent.workflow_dsl or {}
        workflow_type = workflow.get('workflow_type') if isinstance(workflow, dict) else None
        required_fields = agent.required_fields if isinstance(agent.required_fields, dict) else {}
        tools_config = agent.tools_config if isinstance(agent.tools_config, dict) else {}
        context_telephony = ((call.context_payload or {}).get('telephony') or {}) if isinstance(call.context_payload, dict) else {}
        missing_fields = agent_runtime.missing_required_fields(agent=agent, collected_fields=session.collected_fields)
        disposition = self._determine_disposition(call=call, agent=agent, session=session)

        extraction_artifact = {
            'artifact_type': 'extraction',
            'workflow_type': workflow_type or ('outbound' if call.direction.value == 'outbound' else 'inbound'),
            'call_id': str(call.id),
            'call_sid': call.external_call_id or '',
            'direction': call.direction.value,
            'llm_mode': session.llm_mode,
            'detected_intent': session.detected_intent,
            'fields_captured': dict(session.collected_fields),
            'missing_fields': missing_fields,
            'required_fields': required_fields,
            'crm_mapping': builder.get('crm_mapping') or {},
            'last_caller_utterance': session.last_asr_final,
            'campaign': context_telephony.get('campaign') or {},
        }

        action_artifact = {
            'artifact_type': 'action',
            'workflow_type': workflow_type or ('outbound' if call.direction.value == 'outbound' else 'inbound'),
            'call_id': str(call.id),
            'call_sid': call.external_call_id or '',
            'direction': call.direction.value,
            'llm_mode': session.llm_mode,
            'detected_intent': session.detected_intent,
            'final_disposition': disposition,
            'call_outcome': call.outcome or disposition,
            'escalation_reason': call.escalation_reason,
            'action_config': builder.get('action_config') or tools_config,
            'follow_up_needed': bool(missing_fields) or disposition in {'partial_intake', 'transfer_needed'},
            'selected_agent': context_telephony.get('selected_agent') or {},
            'campaign': context_telephony.get('campaign') or {},
        }

        return {
            'extraction': extraction_artifact,
            'action': action_artifact,
        }

    def _build_call_summary(self, *, call: Call, agent: Agent, session: VoiceSession) -> dict:
        ended_at = call.ended_at or datetime.now(timezone.utc)
        duration_seconds = None
        if call.started_at and ended_at:
            duration_seconds = round(max(0.0, (ended_at - call.started_at).total_seconds()), 2)

        disposition = self._determine_disposition(call=call, agent=agent, session=session)
        missing_fields = agent_runtime.missing_required_fields(agent=agent, collected_fields=session.collected_fields)
        operator_artifacts = self._build_operator_artifacts(call=call, agent=agent, session=session)

        return {
            'call_id': str(call.id),
            'timestamp': ended_at.isoformat(),
            'duration_seconds': duration_seconds,
            'fields_captured': dict(session.collected_fields),
            'missing_fields': missing_fields,
            'final_disposition': disposition,
            'notable_errors': list(session.notable_errors),
            'retry_counts': dict(session.field_retry_counts),
            'caller_turns': session.caller_turns,
            'agent_turns': session.agent_turns,
            'llm_mode': session.llm_mode,
            'detected_intent': session.detected_intent,
            'last_response_source': session.last_response_source,
            'operator_artifacts': operator_artifacts,
            'telemetry': session.telemetry.snapshot() if session.telemetry is not None else {},
        }

    async def _finalize_call_summary(
        self,
        *,
        db: AsyncSession,
        call: Call,
        agent: Agent,
        session: VoiceSession,
    ) -> None:
        summary = self._build_call_summary(call=call, agent=agent, session=session)
        call.outcome = summary['final_disposition']
        call.outcome_tags = summary
        logger.info(
            'call.summary',
            extra={
                'correlation_id': session.telemetry.correlation_id if session.telemetry is not None else '',
                'tenant_id': session.tenant_id,
                'call_id': str(call.id),
                'call_sid': call.external_call_id or '',
                'call_summary': summary,
            },
        )
        if session.telemetry is not None:
            call_event_sink.record_event(
                call_event_sink.build_event(
                    event_type='call.summary.final',
                    level='info',
                    call_id=str(call.id),
                    call_sid=call.external_call_id or '',
                    tenant_id=session.tenant_id,
                    direction=session.telemetry.route,
                    route=session.telemetry.route,
                    agent_id=session.telemetry.resolved_agent_id,
                    agent_name=session.telemetry.resolved_agent_name,
                    correlation_id=session.telemetry.correlation_id,
                    from_number=call.from_number,
                    to_number=call.to_number,
                    latency_ms=(
                        round(summary.get('duration_seconds', 0) * 1000, 2)
                        if summary.get('duration_seconds') is not None
                        else None
                    ),
                    summary=summary,
                    total_call_duration_seconds=summary.get('duration_seconds'),
                    first_greeting_latency_ms=summary.get('telemetry', {})
                    .get('latency_ms', {})
                    .get('time_to_first_greeting_audio'),
                    asr_latency_summary=summary.get('telemetry', {}).get('latency_summary', {}).get('asr', {}),
                    llm_latency_summary=summary.get('telemetry', {}).get('latency_summary', {}).get('llm', {}),
                    tts_latency_summary=summary.get('telemetry', {}).get('latency_summary', {}).get('tts', {}),
                    extracted_fields=summary.get('fields_captured', {}),
                    retries=summary.get('retry_counts', {}),
                    errors=summary.get('notable_errors', []),
                    fallbacks=summary.get('telemetry', {}).get('fallbacks', []),
                    anomalies=summary.get('telemetry', {}).get('anomalies', []),
                    handoff_attempts=summary.get('telemetry', {}).get('handoff_attempts', 0),
                )
            )
            artifacts = summary.get('operator_artifacts', {})
            extraction_artifact = artifacts.get('extraction', {})
            action_artifact = artifacts.get('action', {})
            call_event_sink.record_event(
                call_event_sink.build_event(
                    event_type='call.extraction.ready',
                    level='info',
                    call_id=str(call.id),
                    call_sid=call.external_call_id or '',
                    tenant_id=session.tenant_id,
                    direction=session.telemetry.route,
                    route=session.telemetry.route,
                    agent_id=session.telemetry.resolved_agent_id,
                    agent_name=session.telemetry.resolved_agent_name,
                    correlation_id=session.telemetry.correlation_id,
                    from_number=call.from_number,
                    to_number=call.to_number,
                    llm_mode=session.llm_mode,
                    llm_model=(agent.policy_config or {}).get('runtime', {}).get('llm_model', ''),
                    extraction_artifact=extraction_artifact,
                )
            )
            call_event_sink.record_event(
                call_event_sink.build_event(
                    event_type='call.action.ready',
                    level='info',
                    call_id=str(call.id),
                    call_sid=call.external_call_id or '',
                    tenant_id=session.tenant_id,
                    direction=session.telemetry.route,
                    route=session.telemetry.route,
                    agent_id=session.telemetry.resolved_agent_id,
                    agent_name=session.telemetry.resolved_agent_name,
                    correlation_id=session.telemetry.correlation_id,
                    from_number=call.from_number,
                    to_number=call.to_number,
                    llm_mode=session.llm_mode,
                    llm_model=(agent.policy_config or {}).get('runtime', {}).get('llm_model', ''),
                    action_artifact=action_artifact,
                )
            )
        await db.commit()

    async def _handle_agent_turn(
        self,
        *,
        websocket: WebSocket,
        session: VoiceSession,
        db: AsyncSession,
        agent: Agent,
        call: Call,
        turn: AgentTurn,
    ) -> None:
        progress_made = bool(turn.captured_fields)
        for field_name in turn.captured_fields.keys():
            session.field_retry_counts[field_name] = 0
        if progress_made:
            session.consecutive_recovery_turns = 0
            session.last_recovery_prompt = ''
            session.last_retry_reason = ''
        session.llm_mode = turn.llm_mode
        session.detected_intent = turn.detected_intent
        session.last_response_source = turn.response_source
        if session.telemetry is not None:
            session.telemetry.set_llm_mode(turn.llm_mode)
            session.telemetry.set_detected_intent(turn.detected_intent)
            session.telemetry.log(
                'call.intent.detected',
                llm_mode=turn.llm_mode,
                detected_intent=turn.detected_intent,
                detection_source='heuristic',
                transcript_text=session.last_asr_final,
            )
            if turn.captured_fields:
                session.telemetry.log(
                    'call.required_fields.collected',
                    llm_mode=turn.llm_mode,
                    detected_intent=turn.detected_intent,
                    captured_fields=sorted(turn.captured_fields.keys()),
                    captured_values=turn.captured_fields,
                )
            if turn.missing_fields:
                session.telemetry.log(
                    'call.required_fields.missing',
                    llm_mode=turn.llm_mode,
                    detected_intent=turn.detected_intent,
                    missing_fields=turn.missing_fields,
                    active_field=session.prompted_field or turn.prompted_field or '',
                )
            if turn.llm_mode == 'fallback' or turn.fallback_reason:
                session.telemetry.log(
                    'call.fallback.engaged',
                    llm_mode=turn.llm_mode,
                    detected_intent=turn.detected_intent,
                    fallback_reason=turn.fallback_reason or '',
                    response_source=turn.response_source,
                )
            session.telemetry.log(
                'call.response.generated',
                llm_mode=turn.llm_mode,
                detected_intent=turn.detected_intent,
                response_source=turn.response_source,
                fallback_reason=turn.fallback_reason or '',
                captured_fields=sorted(turn.captured_fields.keys()),
                missing_fields=turn.missing_fields,
                text_preview=turn.response_text[:160],
            )
        if session.telemetry is not None:
            session.telemetry.log(
                'call.dialog.turn_evaluated',
                llm_mode=turn.llm_mode,
                active_field=session.prompted_field or '',
                progress_made=progress_made,
                captured_fields=sorted(turn.captured_fields.keys()),
                missing_fields=turn.missing_fields,
                last_asr_partial=session.last_asr_partial,
                last_asr_final=session.last_asr_final,
            )

        if turn.should_escalate:
            call.status = CallStatus.escalated
            call.escalation_reason = turn.escalation_reason
            call.outcome = 'transfer_needed'
            self._record_error(session, 'transfer_requested')
            if session.telemetry is not None:
                session.telemetry.note_handoff_attempt(turn.escalation_reason)

        session.prompted_field = turn.prompted_field
        if turn.outcome:
            call.outcome = turn.outcome

        await self._persist_agent_turn(session=session, db=db, agent=agent, call=call, text=turn.response_text)
        await self.send_tts(
            websocket,
            session,
            agent,
            turn.response_text,
            llm_mode=turn.llm_mode,
            response_source=turn.response_source,
        )

    async def finalize_caller_turn(
        self,
        *,
        websocket: WebSocket,
        session: VoiceSession,
        db: AsyncSession,
        agent: Agent,
        call: Call,
    ) -> None:
        stream = session.asr_stream
        if stream is None:
            session.caller_turn_active = False
            session.consecutive_silence_frames = 0
            session.consecutive_voiced_frames = 0
            session.pre_speech_frames.clear()
            return

        session.asr_stream = None
        session.caller_turn_active = False
        session.consecutive_silence_frames = 0
        session.consecutive_voiced_frames = 0
        session.pre_speech_frames.clear()
        session.asr_resample_state = None

        transcript: ASRFinalTranscript | None = None
        t0 = time.perf_counter()
        try:
            await stream.end_stream()
            transcript = await stream.wait_for_final()
        except Exception as exc:
            self._record_error(session, 'asr_finalization_error')
            if session.telemetry is not None:
                session.telemetry.warning(
                    'call.asr.finalization.failed',
                    asr_provider='aether_voice',
                    error_type=type(exc).__name__,
                    error=str(exc),
                )
            transcript = None
        finally:
            ASR_LATENCY.observe(time.perf_counter() - t0)
            await stream.close()

        if not transcript or not transcript.text.strip():
            self._record_error(session, 'empty_transcript')
            if session.telemetry is not None:
                session.telemetry.add_anomaly('silence_or_dead_air_turn')
            await self._recover_missing_field(
                websocket=websocket,
                session=session,
                db=db,
                agent=agent,
                call=call,
                current_field=session.prompted_field,
                retry_reason=self._retry_reason_from_transcript(session=session, transcript_text=''),
                progress_made=False,
            )
            session.interrupted_turn = False
            return

        session.last_asr_final = transcript.text
        if session.telemetry is not None and 'asr_first_final' not in session.telemetry.timestamps:
            session.telemetry.mark('asr_first_final', transcript_text=transcript.text)
        if session.caller_turns == 0:
            self._analyze_initial_transcript(session=session, transcript_text=transcript.text)
        if session.telemetry is not None:
            session.telemetry.log(
                'call.asr.final.received',
                asr_turn_index=session.asr_turns_started,
                asr_provider='aether_voice',
                latency_ms=round(max(0.0, (time.perf_counter() - t0) * 1000), 2),
                transcript_text=transcript.text,
                transcript_started_ms=transcript.started_ms,
                transcript_ended_ms=transcript.ended_ms,
            )
        session.interrupted_turn = False
        await self._persist_caller_turn(session=session, db=db, call=call, transcript=transcript)

        t1 = time.perf_counter()
        session.llm_requests += 1
        if session.telemetry is not None:
            session.telemetry.log('call.llm.turn.start', llm_request_index=session.llm_requests)
            session.telemetry.mark('llm_request_started')
        turn = await agent_runtime.generate_response(
            agent=agent,
            user_text=transcript.text,
            context=call.context_payload,
            collected_fields=session.collected_fields,
            prompted_field=session.prompted_field,
            telemetry_context={
                **self._telemetry_context(session),
                'llm_request_index': session.llm_requests,
            },
        )
        if session.telemetry is not None:
            session.telemetry.log(
                'call.llm.turn.end',
                llm_request_index=session.llm_requests,
                outcome=turn.outcome or '',
                latency_ms=round(max(0.0, (time.perf_counter() - t1) * 1000), 2),
            )
            session.telemetry.mark('llm_request_completed', outcome=turn.outcome or '')
        LLM_LATENCY.observe(time.perf_counter() - t1)

        await self._handle_agent_turn(
            websocket=websocket,
            session=session,
            db=db,
            agent=agent,
            call=call,
            turn=turn,
        )

    async def process_audio_frame(
        self,
        *,
        websocket: WebSocket,
        session: VoiceSession,
        db: AsyncSession,
        agent: Agent,
        call: Call,
        mulaw_audio: bytes,
    ) -> None:
        session.twilio_audio_buffer.extend(mulaw_audio)
        if session.telemetry is not None and not session.initial_dead_air_reported:
            elapsed_ms = session.telemetry.latency_ms_since_start('call_connected')
            if (
                elapsed_ms is not None
                and elapsed_ms >= INITIAL_DEAD_AIR_SECONDS * 1000
                and 'asr_first_partial' not in session.telemetry.timestamps
                and 'asr_first_final' not in session.telemetry.timestamps
            ):
                session.initial_dead_air_reported = True
                session.telemetry.add_anomaly('initial_dead_air')

        while len(session.twilio_audio_buffer) >= TWILIO_FRAME_BYTES:
            frame_mulaw = bytes(session.twilio_audio_buffer[:TWILIO_FRAME_BYTES])
            del session.twilio_audio_buffer[:TWILIO_FRAME_BYTES]

            pcm_frame_8k = mulaw_to_pcm16(frame_mulaw)
            is_speech = session.vad.is_speech(pcm_frame_8k, TWILIO_SAMPLE_RATE)

            if not session.caller_turn_active:
                session.pre_speech_frames.append(frame_mulaw)
                if is_speech:
                    session.consecutive_voiced_frames += 1
                    if session.consecutive_voiced_frames >= MIN_SPEECH_FRAMES:
                        await self._start_asr_turn(session=session, websocket=websocket)
                        buffered_frames = list(session.pre_speech_frames)
                        session.pre_speech_frames.clear()
                        for buffered_frame in buffered_frames:
                            buffered_pcm = mulaw_to_pcm16(buffered_frame)
                            await self._send_frame_to_asr(session, buffered_pcm)
                else:
                    session.consecutive_voiced_frames = 0
                continue

            await self._send_frame_to_asr(session, pcm_frame_8k)
            if is_speech:
                session.consecutive_silence_frames = 0
            else:
                session.consecutive_silence_frames += 1
                if session.consecutive_silence_frames >= END_OF_TURN_SILENCE_FRAMES:
                    await self.finalize_caller_turn(
                        websocket=websocket,
                        session=session,
                        db=db,
                        agent=agent,
                        call=call,
                    )

    async def _drain_active_turn(
        self,
        *,
        websocket: WebSocket,
        session: VoiceSession,
        db: AsyncSession,
        agent: Agent,
        call: Call,
    ) -> None:
        if session.caller_turn_active or session.asr_stream is not None:
            await self.finalize_caller_turn(
                websocket=websocket,
                session=session,
                db=db,
                agent=agent,
                call=call,
            )

    async def handle_ws(self, websocket: WebSocket, call_id: str, db: AsyncSession) -> None:
        await websocket.accept()
        stmt = select(Call).where(Call.id == call_id)
        call = (await db.execute(stmt)).scalar_one_or_none()
        if not call:
            await websocket.close(code=4404)
            return

        agent_stmt = select(Agent).where(Agent.id == call.agent_id, Agent.tenant_id == call.tenant_id)
        agent = (await db.execute(agent_stmt)).scalar_one_or_none()
        if not agent:
            await websocket.close(code=4404)
            return

        session = await self.get_or_create(call_id, str(call.tenant_id))
        telephony_context = (call.context_payload or {}).get('telephony', {})
        session.telemetry = CallTelemetry(
            call_id=str(call.id),
            tenant_id=str(call.tenant_id),
            route=telephony_context.get('route', call.direction.value),
            call_sid=call.external_call_id or '',
            from_number=call.from_number,
            to_number=call.to_number,
            correlation_id=(telephony_context.get('webhook') or {}).get('correlation_id', ''),
        )
        session.telemetry.bind_agent(agent_id=str(agent.id), agent_name=agent.name)
        session.telemetry.set_llm_mode(session.llm_mode)
        session.telemetry.set_detected_intent(session.detected_intent)
        session.telemetry.mark('call_connected')
        session.telemetry.log(
            'call.started',
            llm_mode=session.llm_mode,
            detected_intent=session.detected_intent,
            call_direction=telephony_context.get('route', call.direction.value),
            agent_persona_preview=agent.persona[:160],
            agent_script_preview=agent.script[:160],
        )
        resolver_context = telephony_context.get('resolver') or {}
        if resolver_context.get('fallback_reason'):
            session.telemetry.add_fallback(
                resolver_context['fallback_reason'],
                resolution_source=resolver_context.get('source', ''),
            )
        for warning in resolver_context.get('warnings') or []:
            session.telemetry.add_anomaly(warning)
        webhook_context = telephony_context.get('webhook') or {}
        for warning in webhook_context.get('warnings') or []:
            session.telemetry.add_anomaly(warning)
        if call.from_number in {'', 'unknown'}:
            session.telemetry.add_anomaly('missing_caller_metadata')
        call.session_id = session.session_id
        call.status = CallStatus.in_progress
        await db.commit()
        session.telemetry.log(
            'call.session.started',
            stream_route=session.telemetry.route,
            agent_persona_preview=agent.persona[:160],
            agent_script_preview=agent.script[:160],
        )

        try:
            while True:
                try:
                    event = await websocket.receive_json()
                except Exception as exc:
                    self._record_error(session, 'telephony_event_parse_failure')
                    if session.telemetry is not None:
                        session.telemetry.warning(
                            'call.telephony.event_parse_failed',
                            error_type=type(exc).__name__,
                            error=str(exc),
                        )
                    raise
                event_type = event.get('event')
                if self._handle_passthrough_telephony_event(session=session, event=event):
                    continue

                if event_type == 'start':
                    session.stream_sid = event.get('start', {}).get('streamSid')
                    if session.stream_sid:
                        session.telemetry.mark('stream_started', stream_sid=session.stream_sid)
                        opening_turn = agent_runtime.build_opening_prompt(
                            agent=agent,
                            collected_fields=session.collected_fields,
                        )
                        session.prompted_field = opening_turn.prompted_field
                        session.llm_mode = opening_turn.llm_mode
                        session.last_response_source = opening_turn.response_source
                        session.detected_intent = opening_turn.detected_intent
                        session.telemetry.set_llm_mode(session.llm_mode)
                        session.telemetry.set_detected_intent(session.detected_intent)
                        session.telemetry.log(
                            'call.opening.loaded',
                            opening_prompt=opening_turn.response_text,
                            prompted_field=opening_turn.prompted_field or '',
                            agent_persona_preview=agent.persona[:160],
                            agent_script_preview=agent.script[:160],
                        )
                        await self._persist_agent_turn(
                            session=session,
                            db=db,
                            agent=agent,
                            call=call,
                            text=opening_turn.response_text,
                        )
                        session.telemetry.log(
                            'call.greeting.sent',
                            llm_mode=opening_turn.llm_mode,
                            response_source=opening_turn.response_source,
                            greeting_text=opening_turn.response_text,
                            prompted_field=opening_turn.prompted_field or '',
                        )
                        await self.send_tts(
                            websocket,
                            session,
                            agent,
                            opening_turn.response_text,
                            llm_mode=opening_turn.llm_mode,
                            response_source=opening_turn.response_source,
                        )
                        await db.commit()
                elif event_type == 'media':
                    payload = event.get('media', {}).get('payload', '')
                    if payload:
                        await self.process_audio_frame(
                            websocket=websocket,
                            session=session,
                            db=db,
                            agent=agent,
                            call=call,
                            mulaw_audio=base64.b64decode(payload),
                        )
                        await db.commit()
                elif event_type == 'dtmf':
                    digit = event.get('dtmf', {}).get('digit')
                    if session.telemetry is not None:
                        session.telemetry.add_anomaly('dtmf_received', digit=digit or '')
                        call_event_sink.record_event(
                            call_event_sink.build_event(
                                event_type='transcript.dtmf.final',
                                level='info',
                                call_id=str(call.id),
                                call_sid=call.external_call_id or '',
                                tenant_id=session.tenant_id,
                                direction=session.telemetry.route,
                                route=session.telemetry.route,
                                agent_id=session.telemetry.resolved_agent_id,
                                agent_name=session.telemetry.resolved_agent_name,
                                correlation_id=session.telemetry.correlation_id,
                                from_number=call.from_number,
                                to_number=call.to_number,
                                speaker='dtmf',
                                text=f'DTMF:{digit}',
                                is_final=True,
                            )
                        )
                    db.add(
                        TranscriptSegment(
                            tenant_id=session.tenant_id,
                            call_id=call.id,
                            speaker='dtmf',
                            text=f'DTMF:{digit}',
                            is_final=True,
                        )
                    )
                    await db.commit()
                elif event_type == 'stop':
                    await self._drain_active_turn(
                        websocket=websocket,
                        session=session,
                        db=db,
                        agent=agent,
                        call=call,
                    )
                    if call.status != CallStatus.escalated:
                        call.status = CallStatus.completed
                    call.ended_at = datetime.now(timezone.utc)
                    if session.telemetry is not None:
                        session.telemetry.mark('call_ended', terminal_status=call.status.value)
                    await db.commit()
                    break
                else:
                    if session.telemetry is not None:
                        session.telemetry.add_anomaly('unknown_telephony_event', event_type=event_type or '')
                    continue
        except Exception:
            self._record_error(session, 'call_loop_exception')
            call.status = CallStatus.failed
            call.ended_at = datetime.now(timezone.utc)
            if session.telemetry is not None:
                session.telemetry.mark('call_ended', terminal_status=call.status.value)
            await db.commit()
        finally:
            if call.ended_at is None:
                call.ended_at = datetime.now(timezone.utc)
            if session.telemetry is not None and 'call_ended' not in session.telemetry.timestamps:
                session.telemetry.mark('call_ended', terminal_status=call.status.value)
            await self._finalize_call_summary(db=db, call=call, agent=agent, session=session)
            if session.tts_task and not session.tts_task.done():
                session.tts_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await session.tts_task
            if session.asr_stream is not None:
                with contextlib.suppress(Exception):
                    await session.asr_stream.close()
            call_event_sink.close_call(str(call.id), call.external_call_id or '')
            self.sessions.pop(call_id, None)
            with contextlib.suppress(Exception):
                await websocket.close()


session_manager = VoiceSessionManager()
