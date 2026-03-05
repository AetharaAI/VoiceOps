import asyncio
import base64
from collections.abc import AsyncGenerator

import httpx

from app.core.config import get_settings


class TTSClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.http = httpx.AsyncClient(timeout=30.0)

    async def stream_tts(self, text: str, voice: str = 'alloy') -> AsyncGenerator[bytes, None]:
        payload = {'text': text, 'voice': voice, 'format': 'pcm_mulaw'}
        try:
            async with self.http.stream('POST', self.settings.tts_endpoint, json=payload) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes():
                    if chunk:
                        yield chunk
        except Exception:
            # Fallback: emit synthetic silence packet to keep protocol valid.
            silence = base64.b64decode('/////////////////////w==')
            for _ in range(max(1, min(20, len(text) // 8))):
                yield silence
                await asyncio.sleep(0.02)


tts_client = TTSClient()
