import asyncio
import base64
import contextlib
import inspect
import json
from dataclasses import dataclass, field
from typing import Awaitable, Callable
from typing import Any
from urllib.parse import urljoin

import httpx
import websockets

from app.core.config import get_settings


class ASRStreamError(RuntimeError):
    pass


@dataclass
class ASRFinalTranscript:
    text: str
    segments: list[dict[str, Any]] = field(default_factory=list)
    started_ms: int | None = None
    ended_ms: int | None = None


class ASRStream:
    def __init__(
        self,
        *,
        websocket: websockets.WebSocketClientProtocol,
        session_id: str,
        on_event: Callable[[dict[str, Any]], Awaitable[None] | None] | None = None,
    ) -> None:
        self.websocket = websocket
        self.session_id = session_id
        self.on_event = on_event
        self.listener_task: asyncio.Task | None = None
        self.final_transcript: asyncio.Future[ASRFinalTranscript] = asyncio.get_running_loop().create_future()
        self.seq = 0
        self.timestamp_ms = 0

    async def send_audio_frame(self, pcm_audio: bytes) -> None:
        if not pcm_audio:
            return

        self.seq += 1
        await self.websocket.send(
            json.dumps(
                {
                    'type': 'audio_frame',
                    'seq': self.seq,
                    'timestamp_ms': self.timestamp_ms,
                    'sample_rate': 16000,
                    'encoding': 'pcm_s16le',
                    'channels': 1,
                    'payload_b64': base64.b64encode(pcm_audio).decode(),
                }
            )
        )
        sample_count = len(pcm_audio) // 2
        self.timestamp_ms += int(sample_count * 1000 / 16000)

    async def end_stream(self) -> None:
        await self.websocket.send(json.dumps({'type': 'end_stream'}))

    async def wait_for_final(self, timeout_seconds: float = 5.0) -> ASRFinalTranscript:
        return await asyncio.wait_for(self.final_transcript, timeout=timeout_seconds)

    async def close(self) -> None:
        if self.listener_task is not None and not self.listener_task.done():
            self.listener_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.listener_task
        if not self.websocket.closed:
            await self.websocket.close()


class ASRClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.http = httpx.AsyncClient(timeout=10.0)

    def _auth_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.settings.aether_voice_api_key:
            headers['X-API-Key'] = self.settings.aether_voice_api_key
        elif self.settings.aether_voice_bearer_token:
            headers['Authorization'] = f'Bearer {self.settings.aether_voice_bearer_token}'
        return headers

    def _resolve_ws_url(self, ws_url: str) -> str:
        if ws_url.startswith('ws://') or ws_url.startswith('wss://'):
            return ws_url
        return urljoin(self.settings.aether_voice_ws_base.rstrip('/') + '/', ws_url.lstrip('/'))

    async def start_stream(
        self,
        *,
        call_id: str,
        on_event: Callable[[dict[str, Any]], Awaitable[None] | None] | None = None,
    ) -> ASRStream:
        payload = {
            'model': self.settings.aether_voice_asr_model,
            'language': self.settings.aether_voice_asr_language,
            'sample_rate': 16000,
            'encoding': 'pcm_s16le',
            'channels': 1,
            'triage_enabled': False,
            'metadata': {
                'source': 'voiceops_call_ingest',
                'extra': {
                    'surface': 'voiceops',
                    'mode': 'live_call',
                    'call_id': call_id,
                },
            },
        }
        response = await self.http.post(
            f"{self.settings.aether_voice_http_base.rstrip('/')}/v1/asr/stream/start",
            json=payload,
            headers=self._auth_headers(),
        )
        response.raise_for_status()
        body = response.json()
        websocket = await websockets.connect(
            self._resolve_ws_url(body['ws_url']),
            extra_headers=self._auth_headers(),
            max_size=None,
        )
        stream = ASRStream(websocket=websocket, session_id=body['session_id'], on_event=on_event)
        stream.listener_task = asyncio.create_task(self._listen(stream=stream, websocket=websocket))
        return stream

    async def _listen(
        self,
        *,
        stream: ASRStream | None,
        websocket: websockets.WebSocketClientProtocol,
    ) -> None:
        try:
            async for message in websocket:
                event = json.loads(message)
                if stream is None:
                    continue
                if stream.on_event is not None:
                    maybe_awaitable = stream.on_event(event)
                    if inspect.isawaitable(maybe_awaitable):
                        await maybe_awaitable
                event_type = event.get('type')
                if event_type == 'final_transcript' and not stream.final_transcript.done():
                    segments = event.get('segments') or []
                    started_ms = segments[0].get('start_ms') if segments else None
                    ended_ms = segments[-1].get('end_ms') if segments else None
                    stream.final_transcript.set_result(
                        ASRFinalTranscript(
                            text=(event.get('text') or '').strip(),
                            segments=segments,
                            started_ms=started_ms,
                            ended_ms=ended_ms,
                        )
                    )
                elif event_type == 'error' and not stream.final_transcript.done():
                    stream.final_transcript.set_exception(
                        ASRStreamError(event.get('message', 'ASR stream error'))
                    )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if stream is not None and not stream.final_transcript.done():
                stream.final_transcript.set_exception(exc)


asr_client = ASRClient()
