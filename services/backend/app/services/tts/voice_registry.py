from __future__ import annotations

from app.core.config import get_settings


KOKORO_TTS_VOICES = [
    {'id': 'af_bella', 'label': 'Bella', 'gender': 'female', 'style_tag': 'warm', 'family': 'kokoro_realtime'},
    {'id': 'af_heart', 'label': 'Heart', 'gender': 'female', 'style_tag': 'bright', 'family': 'kokoro_realtime'},
    {'id': 'af_nicole', 'label': 'Nicole', 'gender': 'female', 'style_tag': 'confident', 'family': 'kokoro_realtime'},
    {'id': 'af_sarah', 'label': 'Sarah', 'gender': 'female', 'style_tag': 'clear', 'family': 'kokoro_realtime'},
    {'id': 'af_sky', 'label': 'Sky', 'gender': 'female', 'style_tag': 'neutral', 'family': 'kokoro_realtime'},
    {'id': 'am_adam', 'label': 'Adam', 'gender': 'male', 'style_tag': 'steady', 'family': 'kokoro_realtime'},
    {'id': 'am_michael', 'label': 'Michael', 'gender': 'male', 'style_tag': 'clear', 'family': 'kokoro_realtime'},
    {'id': 'bf_emma', 'label': 'Emma', 'gender': 'female', 'style_tag': 'british', 'family': 'kokoro_realtime'},
    {'id': 'bf_isabella', 'label': 'Isabella', 'gender': 'female', 'style_tag': 'british', 'family': 'kokoro_realtime'},
    {'id': 'bm_george', 'label': 'George', 'gender': 'male', 'style_tag': 'british', 'family': 'kokoro_realtime'},
    {'id': 'bm_lewis', 'label': 'Lewis', 'gender': 'male', 'style_tag': 'british', 'family': 'kokoro_realtime'},
]


def list_tts_voices() -> list[dict[str, str | bool]]:
    settings = get_settings()
    default_voice = settings.aether_voice_tts_voice
    voices: list[dict[str, str | bool]] = []
    for voice in KOKORO_TTS_VOICES:
        voices.append(
            {
                **voice,
                'is_default': voice['id'] == default_voice,
            }
        )
    return voices
