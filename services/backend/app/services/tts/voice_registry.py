from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

DEFAULT_TTS_PROVIDER = 'aether_voice'
QWEN_TTS_MODELS = ['qwen_customvoice', 'qwen_customvoice_streaming', 'qwen_voice_design']
VOXTREAM2_RUNTIME_TARGET = 'voxtream2_realtime'
VOXTRAL_TTS_MODEL = 'voxtral_tts'
STUDIO_TENANT_HEADER_VALUE = 'default'
KOKORO_OPERATOR_NOTE = 'Qualified live inbound telephony baseline with low startup latency and acceptable interrupt behavior.'
QWEN_OPERATOR_NOTE = 'Not yet qualified as the live inbound telephony baseline. Use for controlled tests until PSTN interrupt behavior is verified.'
VOXTREAM2_OPERATOR_NOTE = (
    'Observed degraded live inbound behavior on 2026-06-26: multi-second first-audio latency and weak turn-taking.'
)
VOXTRAL_OPERATOR_NOTE = (
    'Premium Voxtral TTS demo lane (Aether-Voice-X gateway). Not qualified as a live inbound telephony '
    'baseline; use for demos and controlled tests until PSTN interrupt/latency behavior is verified.'
)

KOKORO_TTS_VOICES = [
    {
        'id': 'af_bella',
        'label': 'Bella',
        'gender': 'female',
        'style_tag': 'warm',
        'family': 'kokoro_realtime',
        'provider': DEFAULT_TTS_PROVIDER,
        'models': ['kokoro_realtime'],
        'telephony_recommended': True,
        'barge_in_quality': 'qualified',
        'latency_profile': 'low',
        'operator_note': KOKORO_OPERATOR_NOTE,
    },
    {
        'id': 'af_heart',
        'label': 'Heart',
        'gender': 'female',
        'style_tag': 'bright',
        'family': 'kokoro_realtime',
        'provider': DEFAULT_TTS_PROVIDER,
        'models': ['kokoro_realtime'],
        'telephony_recommended': True,
        'barge_in_quality': 'qualified',
        'latency_profile': 'low',
        'operator_note': KOKORO_OPERATOR_NOTE,
    },
    {
        'id': 'af_nicole',
        'label': 'Nicole',
        'gender': 'female',
        'style_tag': 'confident',
        'family': 'kokoro_realtime',
        'provider': DEFAULT_TTS_PROVIDER,
        'models': ['kokoro_realtime'],
        'telephony_recommended': True,
        'barge_in_quality': 'qualified',
        'latency_profile': 'low',
        'operator_note': KOKORO_OPERATOR_NOTE,
    },
    {
        'id': 'af_sarah',
        'label': 'Sarah',
        'gender': 'female',
        'style_tag': 'clear',
        'family': 'kokoro_realtime',
        'provider': DEFAULT_TTS_PROVIDER,
        'models': ['kokoro_realtime'],
        'telephony_recommended': True,
        'barge_in_quality': 'qualified',
        'latency_profile': 'low',
        'operator_note': KOKORO_OPERATOR_NOTE,
    },
    {
        'id': 'af_sky',
        'label': 'Sky',
        'gender': 'female',
        'style_tag': 'neutral',
        'family': 'kokoro_realtime',
        'provider': DEFAULT_TTS_PROVIDER,
        'models': ['kokoro_realtime'],
        'telephony_recommended': True,
        'barge_in_quality': 'qualified',
        'latency_profile': 'low',
        'operator_note': KOKORO_OPERATOR_NOTE,
    },
    {
        'id': 'am_adam',
        'label': 'Adam',
        'gender': 'male',
        'style_tag': 'steady',
        'family': 'kokoro_realtime',
        'provider': DEFAULT_TTS_PROVIDER,
        'models': ['kokoro_realtime'],
        'telephony_recommended': True,
        'barge_in_quality': 'qualified',
        'latency_profile': 'low',
        'operator_note': KOKORO_OPERATOR_NOTE,
    },
    {
        'id': 'am_michael',
        'label': 'Michael',
        'gender': 'male',
        'style_tag': 'clear',
        'family': 'kokoro_realtime',
        'provider': DEFAULT_TTS_PROVIDER,
        'models': ['kokoro_realtime'],
        'telephony_recommended': True,
        'barge_in_quality': 'qualified',
        'latency_profile': 'low',
        'operator_note': KOKORO_OPERATOR_NOTE,
    },
    {
        'id': 'bf_emma',
        'label': 'Emma',
        'gender': 'female',
        'style_tag': 'british',
        'family': 'kokoro_realtime',
        'provider': DEFAULT_TTS_PROVIDER,
        'models': ['kokoro_realtime'],
        'telephony_recommended': True,
        'barge_in_quality': 'qualified',
        'latency_profile': 'low',
        'operator_note': KOKORO_OPERATOR_NOTE,
    },
    {
        'id': 'bf_isabella',
        'label': 'Isabella',
        'gender': 'female',
        'style_tag': 'british',
        'family': 'kokoro_realtime',
        'provider': DEFAULT_TTS_PROVIDER,
        'models': ['kokoro_realtime'],
        'telephony_recommended': True,
        'barge_in_quality': 'qualified',
        'latency_profile': 'low',
        'operator_note': KOKORO_OPERATOR_NOTE,
    },
    {
        'id': 'bm_george',
        'label': 'George',
        'gender': 'male',
        'style_tag': 'british',
        'family': 'kokoro_realtime',
        'provider': DEFAULT_TTS_PROVIDER,
        'models': ['kokoro_realtime'],
        'telephony_recommended': True,
        'barge_in_quality': 'qualified',
        'latency_profile': 'low',
        'operator_note': KOKORO_OPERATOR_NOTE,
    },
    {
        'id': 'bm_lewis',
        'label': 'Lewis',
        'gender': 'male',
        'style_tag': 'british',
        'family': 'kokoro_realtime',
        'provider': DEFAULT_TTS_PROVIDER,
        'models': ['kokoro_realtime'],
        'telephony_recommended': True,
        'barge_in_quality': 'qualified',
        'latency_profile': 'low',
        'operator_note': KOKORO_OPERATOR_NOTE,
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
        'telephony_recommended': False,
        'barge_in_quality': 'unverified',
        'latency_profile': 'unverified',
        'operator_note': QWEN_OPERATOR_NOTE,
    },
    {
        'id': 'qwen_aiden',
        'label': 'Aiden',
        'gender': 'male',
        'style_tag': 'steady',
        'family': 'qwen_customvoice',
        'provider': DEFAULT_TTS_PROVIDER,
        'models': QWEN_TTS_MODELS,
        'telephony_recommended': False,
        'barge_in_quality': 'unverified',
        'latency_profile': 'unverified',
        'operator_note': QWEN_OPERATOR_NOTE,
    },
    {
        'id': 'qwen_serena',
        'label': 'Serena',
        'gender': 'female',
        'style_tag': 'calm',
        'family': 'qwen_customvoice',
        'provider': DEFAULT_TTS_PROVIDER,
        'models': QWEN_TTS_MODELS,
        'telephony_recommended': False,
        'barge_in_quality': 'unverified',
        'latency_profile': 'unverified',
        'operator_note': QWEN_OPERATOR_NOTE,
    },
    {
        'id': 'qwen_vivian',
        'label': 'Vivian',
        'gender': 'female',
        'style_tag': 'polished',
        'family': 'qwen_customvoice',
        'provider': DEFAULT_TTS_PROVIDER,
        'models': QWEN_TTS_MODELS,
        'telephony_recommended': False,
        'barge_in_quality': 'unverified',
        'latency_profile': 'unverified',
        'operator_note': QWEN_OPERATOR_NOTE,
    },
    {
        'id': 'qwen_uncle_fu',
        'label': 'Uncle Fu',
        'gender': 'male',
        'style_tag': 'warm',
        'family': 'qwen_customvoice',
        'provider': DEFAULT_TTS_PROVIDER,
        'models': QWEN_TTS_MODELS,
        'telephony_recommended': False,
        'barge_in_quality': 'unverified',
        'latency_profile': 'unverified',
        'operator_note': QWEN_OPERATOR_NOTE,
    },
    {
        'id': 'qwen_sohee',
        'label': 'Sohee',
        'gender': 'female',
        'style_tag': 'bright',
        'family': 'qwen_customvoice',
        'provider': DEFAULT_TTS_PROVIDER,
        'models': QWEN_TTS_MODELS,
        'telephony_recommended': False,
        'barge_in_quality': 'unverified',
        'latency_profile': 'unverified',
        'operator_note': QWEN_OPERATOR_NOTE,
    },
    {
        'id': 'qwen_dylan',
        'label': 'Dylan',
        'gender': 'male',
        'style_tag': 'neutral',
        'family': 'qwen_customvoice',
        'provider': DEFAULT_TTS_PROVIDER,
        'models': QWEN_TTS_MODELS,
        'telephony_recommended': False,
        'barge_in_quality': 'unverified',
        'latency_profile': 'unverified',
        'operator_note': QWEN_OPERATOR_NOTE,
    },
    {
        'id': 'qwen_eric',
        'label': 'Eric',
        'gender': 'male',
        'style_tag': 'confident',
        'family': 'qwen_customvoice',
        'provider': DEFAULT_TTS_PROVIDER,
        'models': QWEN_TTS_MODELS,
        'telephony_recommended': False,
        'barge_in_quality': 'unverified',
        'latency_profile': 'unverified',
        'operator_note': QWEN_OPERATOR_NOTE,
    },
    {
        'id': 'qwen_ono_anna',
        'label': 'Ono Anna',
        'gender': 'female',
        'style_tag': 'soft',
        'family': 'qwen_customvoice',
        'provider': DEFAULT_TTS_PROVIDER,
        'models': QWEN_TTS_MODELS,
        'telephony_recommended': False,
        'barge_in_quality': 'unverified',
        'latency_profile': 'unverified',
        'operator_note': QWEN_OPERATOR_NOTE,
    },
]

VOXTRAL_TTS_VOICES = [
    {
        'id': 'voxtral_casual_female',
        'label': 'Voxtral Casual Female',
        'gender': 'female',
        'style_tag': 'casual',
        'family': VOXTRAL_TTS_MODEL,
        'provider': DEFAULT_TTS_PROVIDER,
        'models': [VOXTRAL_TTS_MODEL],
        'telephony_recommended': False,
        'barge_in_quality': 'unverified',
        'latency_profile': 'unverified',
        'operator_note': VOXTRAL_OPERATOR_NOTE,
    },
]


def list_tts_voices() -> list[dict[str, Any]]:
    settings = get_settings()
    default_voice = settings.aether_voice_tts_voice
    default_model = settings.aether_voice_tts_model
    voices: list[dict[str, Any]] = []
    for voice in [*KOKORO_TTS_VOICES, *QWEN_TTS_VOICES, *VOXTRAL_TTS_VOICES]:
        voices.append(
            {
                **voice,
                'is_default': voice['id'] == default_voice and default_model in voice['models'],
            }
        )
    return voices


def extract_voxtream2_studio_voices(payload: Any) -> list[dict[str, Any]]:
    voices = payload.get('voices') if isinstance(payload, dict) else None
    if not isinstance(voices, list):
        return []

    extracted: list[dict[str, Any]] = []
    for raw in voices:
        if not isinstance(raw, dict):
            continue
        runtime_target = str(raw.get('runtime_target') or '').strip()
        if runtime_target != VOXTREAM2_RUNTIME_TARGET:
            continue

        voice_id = str(raw.get('voice_id') or '').strip()
        label = str(raw.get('display_name') or voice_id).strip()
        reference_audio_path = raw.get('reference_audio_path')
        if not voice_id or not label or not reference_audio_path:
            continue

        extracted.append(
            {
                'id': voice_id,
                'label': label,
                'gender': str(raw.get('gender') or 'unknown'),
                'style_tag': str(raw.get('style_tag') or 'clone'),
                'family': VOXTREAM2_RUNTIME_TARGET,
                'provider': DEFAULT_TTS_PROVIDER,
                'models': [VOXTREAM2_RUNTIME_TARGET],
                'reference_audio_path': str(reference_audio_path),
                'is_default': False,
                'telephony_recommended': False,
                'barge_in_quality': 'degraded',
                'latency_profile': 'high',
                'operator_note': VOXTREAM2_OPERATOR_NOTE,
            }
        )
    return extracted


def merge_tts_voices(base: list[dict[str, Any]], extra: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged = list(base)
    existing_ids = {voice.get('id') for voice in merged}
    for voice in extra:
        vid = voice.get('id')
        if not vid or vid in existing_ids:
            continue
        merged.append(voice)
        existing_ids.add(vid)
    return merged


def _aether_voice_auth_headers() -> dict[str, str]:
    settings = get_settings()
    headers: dict[str, str] = {}
    if settings.aether_voice_api_key:
        headers['X-API-Key'] = settings.aether_voice_api_key
    elif settings.aether_voice_bearer_token:
        headers['Authorization'] = f'Bearer {settings.aether_voice_bearer_token}'
    return headers


async def fetch_voxtream2_studio_voices() -> list[dict[str, Any]]:
    settings = get_settings()
    url = f"{settings.aether_voice_http_base.rstrip('/')}/v1/tts/studio/voices"
    headers = {
        **_aether_voice_auth_headers(),
        # Studio registry seeding lives under tenant `default`.
        'X-Tenant-Id': STUDIO_TENANT_HEADER_VALUE,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return extract_voxtream2_studio_voices(response.json())
    except Exception as exc:
        logger.warning(
            'tts.voice_registry.studio_fetch_failed',
            extra={'correlation_id': '', 'tenant_id': '', 'call_id': '', 'error': str(exc)},
        )
        return []
