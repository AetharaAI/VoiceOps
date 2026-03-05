import base64
import time
from dataclasses import dataclass

import httpx

from app.core.config import get_settings


@dataclass
class ASRChunkResult:
    text: str
    is_final: bool
    confidence: float | None = None
    started_ms: int | None = None
    ended_ms: int | None = None


class ASRClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.http = httpx.AsyncClient(timeout=10.0)

    async def transcribe_chunk(
        self,
        audio_pcm: bytes,
        *,
        is_final: bool,
        started_ms: int | None = None,
        ended_ms: int | None = None,
    ) -> ASRChunkResult:
        t0 = time.perf_counter()
        payload = {
            'audio_base64': base64.b64encode(audio_pcm).decode(),
            'sample_rate': 8000,
            'is_final': is_final,
        }
        try:
            response = await self.http.post(self.settings.asr_endpoint, json=payload)
            response.raise_for_status()
            body = response.json()
            text = body.get('text', '').strip()
            confidence = body.get('confidence')
        except Exception:
            # Fallback when ASR is unavailable to keep call flow non-blocking.
            text = '' if not is_final else '(unintelligible audio)'
            confidence = None
        _ = time.perf_counter() - t0
        return ASRChunkResult(
            text=text,
            is_final=is_final,
            confidence=confidence,
            started_ms=started_ms,
            ended_ms=ended_ms,
        )


asr_client = ASRClient()
