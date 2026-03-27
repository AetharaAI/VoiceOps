from app.services.tts.voice_registry import (
    extract_voxtream2_studio_voices,
    list_tts_voices,
    merge_tts_voices,
)


def test_tts_voice_registry_exposes_full_inventory() -> None:
    voices = list_tts_voices()
    voice_ids = {voice['id'] for voice in voices}
    voice_index = {voice['id']: voice for voice in voices}

    assert {
        'af_bella',
        'af_heart',
        'af_nicole',
        'af_sarah',
        'af_sky',
        'am_adam',
        'am_michael',
        'bf_emma',
        'bf_isabella',
        'bm_george',
        'bm_lewis',
        'qwen_ryan',
        'qwen_aiden',
        'qwen_serena',
        'qwen_vivian',
        'qwen_uncle_fu',
        'qwen_sohee',
        'qwen_dylan',
        'qwen_eric',
        'qwen_ono_anna',
    }.issubset(voice_ids)
    assert voice_index['qwen_serena']['provider'] == 'aether_voice'
    assert voice_index['qwen_serena']['models'] == [
        'qwen_customvoice',
        'qwen_customvoice_streaming',
        'qwen_voice_design',
    ]
    assert any(voice['is_default'] for voice in voices)


def test_extract_voxtream2_studio_voices_filters_runtime_target_and_requires_reference_audio() -> None:
    payload = {
        'voices': [
            {
                'voice_id': 'vx2_female_01',
                'display_name': 'Maya Natural',
                'runtime_target': 'voxtream2_realtime',
                'reference_audio_path': '/voices/maya.wav',
                'gender': 'female',
                'style_tag': 'natural',
            },
            {
                'voice_id': 'qwen_ryan',
                'display_name': 'Ryan',
                'runtime_target': 'qwen_customvoice_streaming',
                'reference_audio_path': '/voices/ryan.wav',
            },
            {
                'voice_id': 'vx2_missing_ref',
                'display_name': 'Missing Ref',
                'runtime_target': 'voxtream2_realtime',
                'reference_audio_path': None,
            },
        ]
    }

    voices = extract_voxtream2_studio_voices(payload)

    assert len(voices) == 1
    assert voices[0] == {
        'id': 'vx2_female_01',
        'label': 'Maya Natural',
        'gender': 'female',
        'style_tag': 'natural',
        'family': 'voxtream2_realtime',
        'provider': 'aether_voice',
        'models': ['voxtream2_realtime'],
        'reference_audio_path': '/voices/maya.wav',
        'is_default': False,
    }


def test_merge_tts_voices_dedupes_by_id() -> None:
    base = [{'id': 'af_bella', 'label': 'Bella'}]
    extra = [
        {'id': 'af_bella', 'label': 'Bella Duplicate'},
        {'id': 'vx2_female_01', 'label': 'Maya Natural'},
    ]

    merged = merge_tts_voices(base, extra)

    assert merged == [
        {'id': 'af_bella', 'label': 'Bella'},
        {'id': 'vx2_female_01', 'label': 'Maya Natural'},
    ]
