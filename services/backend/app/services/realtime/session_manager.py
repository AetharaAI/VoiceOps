import asyncio
import base64
import time
import uuid
from dataclasses import dataclass, field

from fastapi import WebSocket
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.metrics import ASR_LATENCY, LLM_LATENCY, TTS_LATENCY
from app.models.models import Agent, Call, CallStatus, TranscriptSegment
from app.services.agent_runtime.runtime import agent_runtime
from app.services.asr.client import asr_client
from app.services.tts.client import tts_client


@dataclass
class VoiceSession:
    call_id: str
    tenant_id: str
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    state: str = 'greet'
    audio_buffer: bytearray = field(default_factory=bytearray)
    tts_task: asyncio.Task | None = None
    speaking: bool = False
    collected_fields: dict = field(default_factory=dict)


class VoiceSessionManager:
    def __init__(self) -> None:
        self.sessions: dict[str, VoiceSession] = {}

    async def get_or_create(self, call_id: str, tenant_id: str) -> VoiceSession:
        if call_id not in self.sessions:
            self.sessions[call_id] = VoiceSession(call_id=call_id, tenant_id=tenant_id)
        return self.sessions[call_id]

    async def stop_tts_for_barge_in(self, websocket: WebSocket, session: VoiceSession) -> None:
        if session.tts_task and not session.tts_task.done():
            session.tts_task.cancel()
            session.speaking = False
            await websocket.send_json({'event': 'clear'})

    async def send_tts(self, websocket: WebSocket, session: VoiceSession, text: str) -> None:
        async def _stream() -> None:
            session.speaking = True
            t0 = time.perf_counter()
            try:
                async for chunk in tts_client.stream_tts(text):
                    payload = base64.b64encode(chunk).decode()
                    await websocket.send_json({'event': 'media', 'media': {'payload': payload}})
                await websocket.send_json({'event': 'mark', 'mark': {'name': 'tts_done'}})
            finally:
                TTS_LATENCY.observe(time.perf_counter() - t0)
                session.speaking = False

        session.tts_task = asyncio.create_task(_stream())
        await session.tts_task

    async def process_audio_frame(
        self,
        *,
        websocket: WebSocket,
        session: VoiceSession,
        db: AsyncSession,
        agent: Agent,
        call: Call,
        pcm_audio: bytes,
    ) -> None:
        speech_detected = bool(pcm_audio and max(pcm_audio) > 8)

        if speech_detected and session.speaking:
            await self.stop_tts_for_barge_in(websocket, session)

        session.audio_buffer.extend(pcm_audio)

        # Micro-batch ASR every ~320ms @8k mu-law bytes.
        if len(session.audio_buffer) < 2560:
            return

        chunk = bytes(session.audio_buffer)
        session.audio_buffer.clear()

        t0 = time.perf_counter()
        asr = await asr_client.transcribe_chunk(chunk, is_final=True)
        ASR_LATENCY.observe(time.perf_counter() - t0)
        if not asr.text:
            return

        db.add(
            TranscriptSegment(
                tenant_id=session.tenant_id,
                call_id=call.id,
                speaker='caller',
                text=asr.text,
                is_final=True,
                confidence=asr.confidence,
                started_ms=asr.started_ms,
                ended_ms=asr.ended_ms,
            )
        )
        await db.flush()

        t1 = time.perf_counter()
        turn = await agent_runtime.generate_response(
            agent=agent,
            user_text=asr.text,
            context=call.context_payload,
            collected_fields=session.collected_fields,
        )
        LLM_LATENCY.observe(time.perf_counter() - t1)

        if turn.should_escalate:
            call.status = CallStatus.escalated
            call.escalation_reason = turn.escalation_reason

        db.add(
            TranscriptSegment(
                tenant_id=session.tenant_id,
                call_id=call.id,
                speaker='agent',
                text=turn.response_text,
                is_final=True,
            )
        )
        await db.flush()

        await self.send_tts(websocket, session, turn.response_text)

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

        await self.send_tts(websocket, session, f'Hello, this is {agent.name}. How can I help today?')

        try:
            while True:
                event = await websocket.receive_json()
                event_type = event.get('event')

                if event_type == 'media':
                    payload = event.get('media', {}).get('payload', '')
                    if payload:
                        pcm = base64.b64decode(payload)
                        await self.process_audio_frame(
                            websocket=websocket,
                            session=session,
                            db=db,
                            agent=agent,
                            call=call,
                            pcm_audio=pcm,
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
                    call.status = CallStatus.completed
                    await db.commit()
                    break
        except Exception:
            call.status = CallStatus.failed
            await db.commit()
        finally:
            self.sessions.pop(call_id, None)
            await websocket.close()


session_manager = VoiceSessionManager()
