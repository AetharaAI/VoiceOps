import asyncio
import base64
import contextlib
import time
import uuid
from collections import deque
from dataclasses import dataclass, field

import webrtcvad
from fastapi import WebSocket
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.metrics import ASR_LATENCY, LLM_LATENCY, TTS_LATENCY
from app.models.models import Agent, Call, CallStatus, TranscriptSegment
from app.services.agent_runtime.runtime import agent_runtime
from app.services.asr.client import ASRFinalTranscript, ASRStream, asr_client
from app.services.realtime.audio import mulaw_to_pcm16, pcm16_to_mulaw, resample_pcm16, wav_to_pcm16
from app.services.tts.client import tts_client

TWILIO_FRAME_BYTES = 160
TWILIO_SAMPLE_RATE = 8000
ASR_SAMPLE_RATE = 16000
MIN_SPEECH_FRAMES = 2
END_OF_TURN_SILENCE_FRAMES = 40
TTS_MEDIA_CHUNK_BYTES = 640
RECENT_FRAME_BUFFER = 10
RECOVERY_PROMPT = 'I did not catch that clearly. Please say that once more.'


def _build_vad() -> webrtcvad.Vad:
    vad = webrtcvad.Vad()
    vad.set_mode(2)
    return vad


@dataclass
class VoiceSession:
    call_id: str
    tenant_id: str
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    stream_sid: str | None = None
    tts_task: asyncio.Task | None = None
    speaking: bool = False
    collected_fields: dict = field(default_factory=dict)
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    vad: webrtcvad.Vad = field(default_factory=_build_vad)
    twilio_audio_buffer: bytearray = field(default_factory=bytearray)
    pre_speech_frames: deque[bytes] = field(default_factory=lambda: deque(maxlen=RECENT_FRAME_BUFFER))
    asr_stream: ASRStream | None = None
    asr_resample_state: tuple | None = None
    caller_turn_active: bool = False
    consecutive_voiced_frames: int = 0
    consecutive_silence_frames: int = 0


class VoiceSessionManager:
    def __init__(self) -> None:
        self.sessions: dict[str, VoiceSession] = {}

    async def get_or_create(self, call_id: str, tenant_id: str) -> VoiceSession:
        if call_id not in self.sessions:
            self.sessions[call_id] = VoiceSession(call_id=call_id, tenant_id=tenant_id)
        return self.sessions[call_id]

    async def _send_twilio_event(self, websocket: WebSocket, session: VoiceSession, payload: dict) -> None:
        async with session.send_lock:
            await websocket.send_json(payload)

    async def stop_tts_for_barge_in(self, websocket: WebSocket, session: VoiceSession) -> None:
        if session.tts_task and not session.tts_task.done():
            session.tts_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await session.tts_task
            session.speaking = False
            if session.stream_sid:
                await self._send_twilio_event(
                    websocket,
                    session,
                    {
                        'event': 'clear',
                        'streamSid': session.stream_sid,
                    },
                )

    def _wav_chunk_to_mulaw(self, wav_chunk: bytes) -> bytes:
        try:
            pcm_audio, sample_rate = wav_to_pcm16(wav_chunk)
        except Exception:
            pcm_audio = wav_chunk
            sample_rate = 24000
        pcm_8k, _ = resample_pcm16(pcm_audio, from_rate=sample_rate, to_rate=TWILIO_SAMPLE_RATE)
        return pcm16_to_mulaw(pcm_8k)

    async def send_tts(self, websocket: WebSocket, session: VoiceSession, agent: Agent, text: str) -> None:
        if not session.stream_sid:
            return

        if session.tts_task and not session.tts_task.done():
            await self.stop_tts_for_barge_in(websocket, session)

        async def _stream() -> None:
            session.speaking = True
            t0 = time.perf_counter()
            try:
                async for wav_chunk in tts_client.stream_tts(
                    text=text,
                    call_id=session.call_id,
                    agent_id=str(agent.id),
                ):
                    mulaw_audio = self._wav_chunk_to_mulaw(wav_chunk)
                    for index in range(0, len(mulaw_audio), TTS_MEDIA_CHUNK_BYTES):
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
            except Exception:
                pass
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
                TTS_LATENCY.observe(time.perf_counter() - t0)
                session.speaking = False

        session.tts_task = asyncio.create_task(_stream())

    async def _start_asr_turn(self, *, session: VoiceSession, websocket: WebSocket) -> None:
        if session.speaking:
            await self.stop_tts_for_barge_in(websocket, session)
        session.asr_stream = await asr_client.start_stream(call_id=session.call_id)
        session.asr_resample_state = None
        session.caller_turn_active = True
        session.consecutive_silence_frames = 0

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
        await db.flush()

    async def _persist_agent_turn(
        self,
        *,
        session: VoiceSession,
        db: AsyncSession,
        call: Call,
        text: str,
    ) -> None:
        db.add(
            TranscriptSegment(
                tenant_id=session.tenant_id,
                call_id=call.id,
                speaker='agent',
                text=text,
                is_final=True,
            )
        )
        await db.flush()

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
        except Exception:
            transcript = None
        finally:
            ASR_LATENCY.observe(time.perf_counter() - t0)
            await stream.close()

        if not transcript or not transcript.text:
            await self.send_tts(websocket, session, agent, RECOVERY_PROMPT)
            return

        await self._persist_caller_turn(session=session, db=db, call=call, transcript=transcript)

        t1 = time.perf_counter()
        turn = await agent_runtime.generate_response(
            agent=agent,
            user_text=transcript.text,
            context=call.context_payload,
            collected_fields=session.collected_fields,
        )
        LLM_LATENCY.observe(time.perf_counter() - t1)

        if turn.should_escalate:
            call.status = CallStatus.escalated
            call.escalation_reason = turn.escalation_reason
        if turn.outcome:
            call.outcome = turn.outcome

        await self._persist_agent_turn(session=session, db=db, call=call, text=turn.response_text)
        await self.send_tts(websocket, session, agent, turn.response_text)

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

        agent_stmt = select(Agent).where(
            Agent.id == call.agent_id,
            Agent.tenant_id == call.tenant_id,
        )
        agent = (await db.execute(agent_stmt)).scalar_one_or_none()
        if not agent:
            await websocket.close(code=4404)
            return

        session = await self.get_or_create(call_id, str(call.tenant_id))
        call.session_id = session.session_id
        call.status = CallStatus.in_progress
        await db.commit()

        try:
            while True:
                event = await websocket.receive_json()
                event_type = event.get('event')

                if event_type == 'start':
                    session.stream_sid = event.get('start', {}).get('streamSid')
                    if session.stream_sid:
                        await self.send_tts(
                            websocket,
                            session,
                            agent,
                            f'Hello, this is {agent.name}. How can I help today?',
                        )
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
                    call.status = CallStatus.completed
                    await db.commit()
                    break
        except Exception:
            call.status = CallStatus.failed
            await db.commit()
        finally:
            if session.tts_task and not session.tts_task.done():
                session.tts_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await session.tts_task
            if session.asr_stream is not None:
                with contextlib.suppress(Exception):
                    await session.asr_stream.close()
            self.sessions.pop(call_id, None)
            with contextlib.suppress(Exception):
                await websocket.close()


session_manager = VoiceSessionManager()
