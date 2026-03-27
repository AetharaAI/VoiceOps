from __future__ import annotations

from typing import Any

from app.core.config import get_settings


DEFAULT_TTS_PROVIDER = 'aether_voice'
QWEN_TTS_MODELS = ['qwen_customvoice', 'qwen_customvoice_streaming', 'qwen_voice_design', 'voxtream2_realtime']

KOKORO_TTS_VOICES = [
    {
        'id': 'af_bella',
        'label': 'Bella',
        'gender': 'female',
        'style_tag': 'warm',
        'family': 'kokoro_realtime',
        'provider': DEFAULT_TTS_PROVIDER,
        'models': ['kokoro_realtime'],
    },
    {
        'id': 'af_heart',
        'label': 'Heart',
        'gender': 'female',
        'style_tag': 'bright',
        'family': 'kokoro_realtime',
        'provider': DEFAULT_TTS_PROVIDER,
        'models': ['kokoro_realtime'],
    },
    {
        'id': 'af_nicole',
        'label': 'Nicole',
        'gender': 'female',
        'style_tag': 'confident',
        'family': 'kokoro_realtime',
        'provider': DEFAULT_TTS_PROVIDER,
        'models': ['kokoro_realtime'],
    },
    {
        'id': 'af_sarah',
        'label': 'Sarah',
        'gender': 'female',
        'style_tag': 'clear',
        'family': 'kokoro_realtime',
        'provider': DEFAULT_TTS_PROVIDER,
        'models': ['kokoro_realtime'],
    },
    {
        'id': 'af_sky',
        'label': 'Sky',
        'gender': 'female',
        'style_tag': 'neutral',
        'family': 'kokoro_realtime',
        'provider': DEFAULT_TTS_PROVIDER,
        'models': ['kokoro_realtime'],
    },
    {
        'id': 'am_adam',
        'label': 'Adam',
        'gender': 'male',
        'style_tag': 'steady',
        'family': 'kokoro_realtime',
        'provider': DEFAULT_TTS_PROVIDER,
        'models': ['kokoro_realtime'],
    },
    {
        'id': 'am_michael',
        'label': 'Michael',
        'gender': 'male',
        'style_tag': 'clear',
        'family': 'kokoro_realtime',
        'provider': DEFAULT_TTS_PROVIDER,
        'models': ['kokoro_realtime'],
    },
    {
        'id': 'bf_emma',
        'label': 'Emma',
        'gender': 'female',
        'style_tag': 'british',
        'family': 'kokoro_realtime',
        'provider': DEFAULT_TTS_PROVIDER,
        'models': ['kokoro_realtime'],
    },
    {
        'id': 'bf_isabella',
        'label': 'Isabella',
        'gender': 'female',
        'style_tag': 'british',
        'family': 'kokoro_realtime',
        'provider': DEFAULT_TTS_PROVIDER,
        'models': ['kokoro_realtime'],
    },
    {
        'id': 'bm_george',
        'label': 'George',
        'gender': 'male',
        'style_tag': 'british',
        'family': 'kokoro_realtime',
        'provider': DEFAULT_TTS_PROVIDER,
        'models': ['kokoro_realtime'],
    },
    {
        'id': 'bm_lewis',
        'label': 'Lewis',
        'gender': 'male',
        'style_tag': 'british',
        'family': 'kokoro_realtime',
        'provider': DEFAULT_TTS_PROVIDER,
        'models': ['kokoro_realtime'],
    },
]

QWEN_TTS_VOICES = [
    {
        'id': 'qwen_ryan',
        'label': 'Ryan',
        'gender': 'male',
        'style_tag': 'clear',
        'family': 'qwen_customvoice',
        'provider': DEFAULT_TTS_PROVIDER,
        'models': QWEN_TTS_MODELS,
    },
    {
        'id': 'qwen_aiden',
        'label': 'Aiden',
        'gender': 'male',
        'style_tag': 'steady',
        'family': 'qwen_customvoice',
        'provider': DEFAULT_TTS_PROVIDER,
        'models': QWEN_TTS_MODELS,
    },
    {
        'id': 'qwen_serena',
        'label': 'Serena',
        'gender': 'female',
        'style_tag': 'calm',
        'family': 'qwen_customvoice',
        'provider': DEFAULT_TTS_PROVIDER,
        'models': QWEN_TTS_MODELS,
    },
    {
        'id': 'qwen_vivian',
        'label': 'Vivian',
        'gender': 'female',
        'style_tag': 'polished',
        'family': 'qwen_customvoice',
        'provider': DEFAULT_TTS_PROVIDER,
        'models': QWEN_TTS_MODELS,
    },
    {
        'id': 'qwen_uncle_fu',
        'label': 'Uncle Fu',
        'gender': 'male',
        'style_tag': 'warm',
        'family': 'qwen_customvoice',
        'provider': DEFAULT_TTS_PROVIDER,
        'models': QWEN_TTS_MODELS,
    },
    {
        'id': 'qwen_sohee',
        'label': 'Sohee',
        'gender': 'female',
        'style_tag': 'bright',
        'family': 'qwen_customvoice',
        'provider': DEFAULT_TTS_PROVIDER,
        'models': QWEN_TTS_MODELS,
    },
    {
        'id': 'qwen_dylan',
        'label': 'Dylan',
        'gender': 'male',
        'style_tag': 'neutral',
        'family': 'qwen_customvoice',
        'provider': DEFAULT_TTS_PROVIDER,
        'models': QWEN_TTS_MODELS,
    },
    {
        'id': 'qwen_eric',
        'label': 'Eric',
        'gender': 'male',
        'style_tag': 'confident',
        'family': 'qwen_customvoice',
        'provider': DEFAULT_TTS_PROVIDER,
        'models': QWEN_TTS_MODELS,
    },
    {
        'id': 'qwen_ono_anna',
        'label': 'Ono Anna',
        'gender': 'female',
        'style_tag': 'soft',
        'family': 'qwen_customvoice',
        'provider': DEFAULT_TTS_PROVIDER,
        'models': QWEN_TTS_MODELS,
    },
]


def list_tts_voices() -> list[dict[str, Any]]:
    settings = get_settings()
    default_voice = settings.aether_voice_tts_voice
    default_model = settings.aether_voice_tts_model
    voices: list[dict[str, Any]] = []
    for voice in [*KOKORO_TTS_VOICES, *QWEN_TTS_VOICES]:
        voices.append(
            {
                **voice,
                'is_default': voice['id'] == default_voice and default_model in voice['models'],
            }
        )
    return voices
