from app.services.tts.voice_registry import list_tts_voices


def test_tts_voice_registry_exposes_full_inventory() -> None:
    voices = list_tts_voices()
    voice_ids = {voice['id'] for voice in voices}

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
    }.issubset(voice_ids)
    assert any(voice['is_default'] for voice in voices)
