import io
import struct
import wave

from app.services.realtime.audio import (
    mulaw_to_pcm16,
    pcm16_to_mulaw,
    resample_pcm16,
    strip_control_markup,
    wav_to_pcm16,
)


def _make_wav(sample_rate: int = 24000, duration_ms: int = 100) -> bytes:
    frame_count = sample_rate * duration_ms // 1000
    pcm_audio = b''.join(struct.pack('<h', 0) for _ in range(frame_count))
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_audio)
    return buffer.getvalue()


def test_strip_control_markup_removes_reasoning_tags() -> None:
    text = 'Hello <think>internal</think> there <tool_call>{"x":1}</tool_call> <|reserved|> world'
    assert strip_control_markup(text) == 'Hello there world'


def test_wav_to_mulaw_transcode_path() -> None:
    wav_audio = _make_wav()
    pcm_audio, sample_rate = wav_to_pcm16(wav_audio)
    assert sample_rate == 24000
    assert len(pcm_audio) > 0

    pcm_8k, _ = resample_pcm16(pcm_audio, from_rate=sample_rate, to_rate=8000)
    mulaw_audio = pcm16_to_mulaw(pcm_8k)
    restored_pcm = mulaw_to_pcm16(mulaw_audio)

    assert len(mulaw_audio) == len(pcm_8k) // 2
    assert len(restored_pcm) == len(mulaw_audio) * 2
