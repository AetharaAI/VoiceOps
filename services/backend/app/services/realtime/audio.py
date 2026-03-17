import audioop
import io
import re
import wave


CONTROL_TAG_PATTERN = re.compile(r'<(think|tool_call)\b[^>]*>.*?</\1>', re.IGNORECASE | re.DOTALL)
CONTROL_TOKEN_PATTERN = re.compile(r'<\|[^>]+?\|>')
RESERVED_TOKEN_PATTERN = re.compile(r'<reserved_\d+>', re.IGNORECASE)
CODE_FENCE_PATTERN = re.compile(r'```[\s\S]*?(?:```|$)')
INLINE_CODE_PATTERN = re.compile(r'`[^`]*`')


def strip_control_markup(text: str) -> str:
    cleaned = text or ''
    cleaned = CONTROL_TAG_PATTERN.sub(' ', cleaned)
    cleaned = CONTROL_TOKEN_PATTERN.sub(' ', cleaned)
    cleaned = CODE_FENCE_PATTERN.sub(' ', cleaned)
    cleaned = INLINE_CODE_PATTERN.sub(' ', cleaned)
    if RESERVED_TOKEN_PATTERN.search(cleaned):
        cleaned = RESERVED_TOKEN_PATTERN.split(cleaned)[-1]
    cleaned = RESERVED_TOKEN_PATTERN.sub(' ', cleaned)
    return ' '.join(cleaned.split())


def mulaw_to_pcm16(mulaw_audio: bytes) -> bytes:
    return audioop.ulaw2lin(mulaw_audio, 2)


def pcm16_to_mulaw(pcm_audio: bytes) -> bytes:
    return audioop.lin2ulaw(pcm_audio, 2)


def resample_pcm16(
    pcm_audio: bytes,
    *,
    from_rate: int,
    to_rate: int,
    channels: int = 1,
    state: tuple | None = None,
) -> tuple[bytes, tuple | None]:
    if from_rate == to_rate:
        return pcm_audio, state
    converted, next_state = audioop.ratecv(pcm_audio, 2, channels, from_rate, to_rate, state)
    return converted, next_state


def wav_to_pcm16(wav_audio: bytes) -> tuple[bytes, int]:
    with wave.open(io.BytesIO(wav_audio), 'rb') as wav_file:
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        sample_rate = wav_file.getframerate()
        frames = wav_file.readframes(wav_file.getnframes())

    if channels > 1:
        frames = audioop.tomono(frames, sample_width, 0.5, 0.5)
    if sample_width != 2:
        frames = audioop.lin2lin(frames, sample_width, 2)
    return frames, sample_rate
