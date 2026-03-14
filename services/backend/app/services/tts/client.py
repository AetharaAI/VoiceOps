import base64
import json
from collections.abc import AsyncGenerator
from urllib.parse import urljoin

import httpx
import websockets

from app.core.config import get_settings
from app.services.realtime.audio import strip_control_markup


class TTSStreamError(RuntimeError):
    pass


class TTSClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.http = httpx.AsyncClient(timeout=15.0)

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

    async def stream_tts(
        self,
        *,
        text: str,
        call_id: str,
        agent_id: str,
        voice: str | None = None,
    ) -> AsyncGenerator[bytes, None]:
        cleaned_text = strip_control_markup(text)
        payload = {
            'model': self.settings.aether_voice_tts_model,
            'voice': voice or self.settings.aether_voice_tts_voice,
            'sample_rate': self.settings.aether_voice_tts_sample_rate,
            'format': self.settings.aether_voice_tts_format,
            'context_mode': 'conversation',
            'metadata': {
                'source': 'voiceops_live_reply',
                'extra': {
                    'surface': 'voiceops',
                    'call_id': call_id,
                    'agent_id': agent_id,
                },
            },
        }
        response = await self.http.post(
            f"{self.settings.aether_voice_http_base.rstrip('/')}/v1/tts/stream/start",
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

        sent_realtime_audio = False
        try:
            await websocket.send(json.dumps({'type': 'text_chunk', 'text': cleaned_text}))
            await websocket.send(json.dumps({'type': 'text_complete'}))
            await websocket.send(json.dumps({'type': 'end_stream'}))

            async for message in websocket:
                event = json.loads(message)
                event_type = event.get('type')
                if event_type == 'audio_chunk':
                    audio_b64 = event.get('audio_b64')
                    if audio_b64:
                        sent_realtime_audio = True
                        yield base64.b64decode(audio_b64)
                elif event_type == 'final_audio':
                    audio_b64 = event.get('audio_b64')
                    if audio_b64 and not sent_realtime_audio:
                        yield base64.b64decode(audio_b64)
                    break
                elif event_type == 'error':
                    raise TTSStreamError(event.get('message', 'TTS stream error'))
        finally:
            if not websocket.closed:
                await websocket.close()


tts_client = TTSClient()
