from app.api.routes.agents import derive_llm_models_url, extract_llm_model_ids


def test_derive_llm_models_url_from_chat_completions() -> None:
    assert (
        derive_llm_models_url('https://api.aetherpro.tech/v1/chat/completions')
        == 'https://api.aetherpro.tech/v1/models'
    )


def test_derive_llm_models_url_from_completions() -> None:
    assert derive_llm_models_url('https://gateway.example.com/v1/completions') == 'https://gateway.example.com/v1/models'


def test_extract_llm_model_ids_preserves_order_and_deduplicates() -> None:
    payload = {
        'object': 'list',
        'data': [
            {'id': 'qwen3.5-35b'},
            {'id': 'glm-ocr'},
            {'id': 'qwen3.5-35b'},
            {'id': ''},
            {},
        ],
    }

    assert extract_llm_model_ids(payload) == ['qwen3.5-35b', 'glm-ocr']
