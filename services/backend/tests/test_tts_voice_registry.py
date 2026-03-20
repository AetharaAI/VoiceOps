from app.services.tts.voice_registry import list_tts_voices


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
