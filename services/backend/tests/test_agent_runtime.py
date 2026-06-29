import pytest

from app.models.models import Agent
from app.services.agent_runtime.runtime import agent_runtime


@pytest.mark.asyncio
async def test_escalates_on_sensitive_language() -> None:
    agent = Agent(
        tenant_id='00000000-0000-0000-0000-000000000001',
        name='Support',
        persona='calm',
        script='assist',
        required_fields={},
        tools_config={},
        policy_config={},
        workflow_dsl={},
    )
    turn = await agent_runtime.generate_response(
        agent=agent,
        user_text='I want a manager right now',
        context={},
        collected_fields={},
    )
    assert turn.should_escalate is True
    assert turn.escalation_reason is not None


@pytest.mark.asyncio
async def test_sensitive_language_respects_fsm_escalation_toggle() -> None:
    agent = Agent(
        tenant_id='00000000-0000-0000-0000-000000000001',
        name='Support',
        persona='calm',
        script='assist',
        required_fields={},
        tools_config={},
        policy_config={},
        workflow_dsl={
            'workflow_type': 'inbound',
            'inbound_builder': {
                'fsm_config': {
                    'frustration_escalation_enabled': False,
                }
            },
        },
    )
    turn = await agent_runtime.generate_response(
        agent=agent,
        user_text='I want a manager right now',
        context={},
        collected_fields={},
    )
    assert turn.should_escalate is False


def _make_agent(required_fields: dict | None = None, workflow_dsl: dict | None = None) -> Agent:
    return Agent(
        tenant_id='00000000-0000-0000-0000-000000000001',
        name='Support',
        persona='calm',
        script='assist',
        required_fields=required_fields or {},
        tools_config={},
        policy_config={},
        workflow_dsl=workflow_dsl or {},
    )


def test_human_transfer_config_defaults_are_applied() -> None:
    agent = _make_agent()

    config = agent_runtime.human_transfer_config_for_agent(agent=agent)

    assert config['enabled'] is False
    assert config['trigger_mode'] == 'explicit_or_keyword'
    assert config['destination_type'] == 'phone_number'
    assert config['no_answer_fallback'] == 'return_to_ai'
    assert config['ring_timeout_seconds'] == 20
    assert config['keywords'] == ['human', 'representative', 'real person', 'operator', 'manager', 'sales', 'transfer me']


def test_fsm_config_defaults_are_applied() -> None:
    agent = _make_agent()

    config = agent_runtime.normalized_fsm_config_for_agent(agent=agent)

    assert config['silence_timeout_seconds'] == 10.0
    assert config['max_retries_per_field'] == 3
    assert config['frustration_escalation_enabled'] is True
    assert config['contact_capture'] == {}
    assert config['lanes'] == {}


@pytest.mark.asyncio
async def test_keyword_transfer_uses_structured_action_contract() -> None:
    agent = _make_agent(
        workflow_dsl={
            'workflow_type': 'inbound',
            'inbound_builder': {
                'human_transfer': {
                    'enabled': True,
                    'trigger_mode': 'keyword_only',
                    'keywords': ['human', 'representative'],
                    'destination_type': 'phone_number',
                    'destination': '+18125550100',
                    'label': 'Front Desk',
                    'confirmation_message': 'One moment while I transfer you.',
                    'no_answer_fallback': 'return_to_ai',
                    'ring_timeout_seconds': 20,
                }
            },
        }
    )

    turn = await agent_runtime.generate_response(
        agent=agent,
        user_text='Can you connect me to a human?',
        context={},
        collected_fields={},
    )

    assert turn.should_escalate is True
    assert turn.response_text == 'One moment while I transfer you.'
    assert turn.tool_calls == [
        {
            'action': 'transfer_call',
            'target': 'Front Desk',
            'reason': 'keyword:human',
        }
    ]


@pytest.mark.asyncio
async def test_explicit_transfer_action_contract_from_llm(monkeypatch) -> None:
    agent = _make_agent(
        workflow_dsl={
            'workflow_type': 'inbound',
            'inbound_builder': {
                'human_transfer': {
                    'enabled': True,
                    'trigger_mode': 'explicit_only',
                    'keywords': ['human'],
                    'destination_type': 'phone_number',
                    'destination': '+18125550100',
                    'label': 'Front Desk',
                    'confirmation_message': 'I will transfer you now.',
                    'no_answer_fallback': 'return_to_ai',
                    'ring_timeout_seconds': 20,
                }
            },
        }
    )
    agent.policy_config = {'runtime': {'llm_provider': 'openai', 'llm_model': 'omnicoder'}}

    original_endpoint = agent_runtime.settings.llm_endpoint
    original_api_key = agent_runtime.settings.llm_api_key
    agent_runtime.settings.llm_endpoint = 'https://api.aetherpro.tech/v1/chat/completions'
    agent_runtime.settings.llm_api_key = 'test-key'

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                'choices': [
                    {
                        'message': {
                            'content': '{"action":"transfer_call","target":"Front Desk","reason":"caller requested person"}',
                        }
                    }
                ]
            }

    async def fake_post(url, json, headers):  # noqa: ANN001 - httpx-compatible test shim
        _ = url
        _ = json
        _ = headers
        return FakeResponse()

    monkeypatch.setattr(agent_runtime.http, 'post', fake_post)
    try:
        turn = await agent_runtime.generate_response(
            agent=agent,
            user_text='please connect me now',
            context={},
            collected_fields={},
        )
    finally:
        agent_runtime.settings.llm_endpoint = original_endpoint
        agent_runtime.settings.llm_api_key = original_api_key

    assert turn.should_escalate is True
    assert turn.response_text == 'I will transfer you now.'
    assert turn.tool_calls == [
        {
            'action': 'transfer_call',
            'target': 'Front Desk',
            'reason': 'caller requested person',
        }
    ]


def test_build_opening_prompt_uses_first_required_field() -> None:
    agent = _make_agent(
        {
            'name': {'prompt': 'Can I get your full name?'},
            'phone': {'prompt': 'What is the best callback number?'},
        }
    )

    turn = agent_runtime.build_opening_prompt(agent=agent, collected_fields={})

    assert turn.prompted_field == 'name'
    assert 'Hello, this is Support. How can I help today?' == turn.response_text


def test_build_opening_prompt_prefers_custom_runtime_greeting() -> None:
    agent = _make_agent({'name': {'prompt': 'Can I get your full name?'}})
    agent.policy_config = {
        'runtime': {
            'opening_greeting': 'Thank you for calling Syndicate AI. I can get you routed.'
        }
    }

    turn = agent_runtime.build_opening_prompt(agent=agent, collected_fields={})

    assert turn.prompted_field == 'name'
    assert turn.response_text == 'Thank you for calling Syndicate AI. I can get you routed.'


def test_omnicoder_defaults_to_thinking_disabled() -> None:
    agent = _make_agent()
    agent.policy_config = {'runtime': {'llm_model': 'omnicoder'}}

    overrides = agent_runtime.llm_request_overrides_for_agent(agent=agent)

    assert overrides == {'extra_body': {'chat_template_kwargs': {'enable_thinking': False}}}


def test_runtime_can_explicitly_enable_thinking() -> None:
    agent = _make_agent()
    agent.policy_config = {'runtime': {'llm_model': 'omnicoder', 'enable_thinking': True}}

    overrides = agent_runtime.llm_request_overrides_for_agent(agent=agent)

    assert overrides == {'extra_body': {'chat_template_kwargs': {'enable_thinking': True}}}


def test_tts_runtime_defaults_use_global_settings() -> None:
    agent = _make_agent()

    assert agent_runtime.tts_provider_for_agent(agent=agent) == 'aether_voice'
    assert agent_runtime.tts_model_for_agent(agent=agent) == agent_runtime.settings.aether_voice_tts_model
    assert agent_runtime.tts_voice_for_agent(agent=agent) == agent_runtime.settings.aether_voice_tts_voice
    assert agent_runtime.tts_metadata_for_agent(agent=agent) == {}


def test_tts_runtime_can_override_provider_model_voice_and_metadata() -> None:
    agent = _make_agent()
    agent.policy_config = {
        'runtime': {
            'tts_provider': 'aether_voice',
            'tts_model': 'qwen_customvoice_streaming',
            'tts_voice': 'qwen_serena',
            'tts_metadata': {
                'lane': 'live_probe',
                'extra': {
                    'qwen_instructions': 'Speak in a calm, telephony-friendly style.',
                },
            },
        }
    }

    assert agent_runtime.tts_provider_for_agent(agent=agent) == 'aether_voice'
    assert agent_runtime.tts_model_for_agent(agent=agent) == 'qwen_customvoice_streaming'
    assert agent_runtime.tts_voice_for_agent(agent=agent) == 'qwen_serena'
    assert agent_runtime.tts_metadata_for_agent(agent=agent) == {
        'lane': 'live_probe',
        'extra': {
            'qwen_instructions': 'Speak in a calm, telephony-friendly style.',
        },
    }


def test_recovery_prompts_vary_and_avoid_immediate_repeat() -> None:
    agent = _make_agent({'name': {'prompt': 'Can I have your full name?'}})

    first = agent_runtime.build_field_retry_prompt(
        agent=agent,
        field_name='name',
        retry_count=1,
        retry_reason='no_speech',
        previous_prompt='',
    )
    second = agent_runtime.build_field_retry_prompt(
        agent=agent,
        field_name='name',
        retry_count=2,
        retry_reason='no_speech',
        previous_prompt=first,
    )

    assert first != second
    assert 'full name' in first.lower()
    assert 'full name' in second.lower()


def test_capture_required_fields_only_targets_prompted_field() -> None:
    agent = _make_agent(
        {
            'name': {'prompt': 'Can I have your full name?'},
            'organization': {'prompt': 'What company are you with?'},
        }
    )

    captured = agent_runtime.capture_required_fields(
        agent=agent,
        user_text="It's good, Corey.",
        collected_fields={},
        prompted_field='name',
    )

    assert captured == {'name': 'Corey'}


def test_capture_records_prompted_soft_field_from_substantive_answer() -> None:
    # A free-text field the agent explicitly asked about must be recorded from the
    # spoken answer even when no specialized extractor normalizes it, so the flow
    # does not loop back and ask the same question again.
    agent = _make_agent(
        {
            'name': {'prompt': 'Can I have your full name?'},
            'service_interest': {'prompt': 'What service are you interested in?'},
        }
    )

    captured = agent_runtime.capture_required_fields(
        agent=agent,
        user_text="I've never been there before, I just want to schedule an appointment.",
        collected_fields={'name': 'Corey'},
        prompted_field='service_interest',
    )

    assert 'service_interest' in captured
    assert agent_runtime.missing_required_fields(
        agent=agent,
        collected_fields={'name': 'Corey', **captured},
    ) == []


def test_capture_does_not_fabricate_structured_field_from_vague_answer() -> None:
    # Structured fields (name/phone) must NOT be satisfied by an un-parseable answer;
    # they keep strict extraction so the retry/skip-ahead path still runs.
    agent = _make_agent({'phone': {'prompt': 'What is the best callback number?'}})

    captured = agent_runtime.capture_required_fields(
        agent=agent,
        user_text='I am not really sure right now',
        collected_fields={},
        prompted_field='phone',
    )

    assert 'phone' not in captured


@pytest.mark.asyncio
async def test_generate_response_replays_conversation_history_to_llm(monkeypatch) -> None:
    agent = _make_agent({'service_interest': {'prompt': 'What service are you interested in?'}})
    agent.policy_config = {'runtime': {'llm_provider': 'openai', 'llm_model': 'omnicoder'}}

    original_endpoint = agent_runtime.settings.llm_endpoint
    original_api_key = agent_runtime.settings.llm_api_key
    agent_runtime.settings.llm_endpoint = 'https://api.aetherpro.tech/v1/chat/completions'
    agent_runtime.settings.llm_api_key = 'test-key'

    captured_payload: dict = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {'choices': [{'message': {'content': 'Got it, thanks!'}}]}

    async def fake_post(url, json, headers):  # noqa: ANN001 - httpx-compatible test shim
        _ = url
        _ = headers
        captured_payload.update(json)
        return FakeResponse()

    monkeypatch.setattr(agent_runtime.http, 'post', fake_post)
    history = [
        {'role': 'assistant', 'content': 'What service are you interested in?'},
        {'role': 'user', 'content': 'I just want to book an appointment.'},
    ]
    try:
        await agent_runtime.generate_response(
            agent=agent,
            user_text='My number is 812-721-2341.',
            context={},
            collected_fields={'service_interest': 'book an appointment'},
            prompted_field='service_interest',
            conversation_history=history,
        )
    finally:
        agent_runtime.settings.llm_endpoint = original_endpoint
        agent_runtime.settings.llm_api_key = original_api_key

    roles = [m['role'] for m in captured_payload['messages']]
    assert roles == ['system', 'assistant', 'user', 'user']
    assert captured_payload['messages'][1]['content'] == 'What service are you interested in?'
    assert captured_payload['messages'][-1]['content'] == 'My number is 812-721-2341.'


def test_active_field_tracks_asked_field_not_dict_order() -> None:
    # required_fields dict order is name, phone, service — but if we are mid-way
    # through asking 'service_interest', the active field must stay service_interest
    # (the field actually being asked), not jump to phone just because it is first.
    missing = ['phone_number', 'service_interest']
    assert agent_runtime._active_field('service_interest', missing) == 'service_interest'
    # Once the asked field is satisfied (no longer missing), advance to the next one.
    assert agent_runtime._active_field('service_interest', ['phone_number']) == 'phone_number'
    assert agent_runtime._active_field(None, ['phone_number']) == 'phone_number'
    assert agent_runtime._active_field('name', []) is None


def test_system_prompt_objective_follows_asked_field_over_dict_order() -> None:
    agent = _make_agent(
        {
            'name': {'prompt': 'Who do I have the pleasure of speaking with?'},
            'phone_number': {'prompt': 'What is the best callback number?'},
            'service_interest': {'prompt': 'What service or treatment are you interested in?'},
        }
    )
    prompt = agent_runtime.build_llm_system_prompt(
        agent=agent,
        context={},
        collected_fields={'name': 'Corey'},
        missing_fields=['phone_number', 'service_interest'],
        prompted_field='service_interest',
        detected_intent='general',
    )
    objective_line = next(line for line in prompt.splitlines() if line.startswith('Current objective'))
    assert 'service interest' in objective_line
    assert 'callback number' not in objective_line


def test_extract_name_handles_noisy_phrase() -> None:
    assert agent_runtime._extract_name('Why, Mary,') == 'Mary'


def test_extract_name_ignores_trailing_and_after_last_name() -> None:
    assert agent_runtime._extract_name('Gibson and 812-363-2424') == 'Gibson'


def test_extract_name_rejects_service_word_phrase() -> None:
    assert agent_runtime._extract_name('and electrical') is None


def test_missing_required_fields_skips_organization_by_default() -> None:
    agent = _make_agent(
        {
            'name': {'prompt': 'Name?'},
            'organization': {'prompt': 'Organization?'},
        }
    )

    missing = agent_runtime.missing_required_fields(agent=agent, collected_fields={})
    assert missing == ['name']


def test_missing_required_fields_can_require_organization_when_enabled() -> None:
    agent = _make_agent(
        {
            'name': {'prompt': 'Name?'},
            'organization': {'prompt': 'Organization?'},
        }
    )
    agent.policy_config = {'runtime': {'require_organization': True}}

    missing = agent_runtime.missing_required_fields(agent=agent, collected_fields={})
    assert missing == ['name', 'organization']


@pytest.mark.asyncio
async def test_generate_response_sends_enable_thinking_in_extra_body(monkeypatch) -> None:
    agent = _make_agent()
    agent.policy_config = {'runtime': {'llm_provider': 'openai', 'llm_model': 'omnicoder'}}

    captured_request: dict = {}
    original_endpoint = agent_runtime.settings.llm_endpoint
    original_api_key = agent_runtime.settings.llm_api_key
    agent_runtime.settings.llm_endpoint = 'https://api.aetherpro.tech/v1/chat/completions'
    agent_runtime.settings.llm_api_key = 'test-key'

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                'choices': [
                    {
                        'message': {
                            'content': '<reserved_12> thinking <reserved_13> ```python\nnoop()\n```',
                        }
                    }
                ]
            }

    async def fake_post(url, json, headers):  # noqa: ANN001 - httpx-compatible test shim
        captured_request['url'] = url
        captured_request['json'] = json
        captured_request['headers'] = headers
        return FakeResponse()

    monkeypatch.setattr(agent_runtime.http, 'post', fake_post)

    try:
        turn = await agent_runtime.generate_response(
            agent=agent,
            user_text='Tell me about your services',
            context={},
            collected_fields={},
        )
    finally:
        agent_runtime.settings.llm_endpoint = original_endpoint
        agent_runtime.settings.llm_api_key = original_api_key

    assert captured_request['json']['extra_body'] == {'chat_template_kwargs': {'enable_thinking': False}}
    assert turn.response_text == 'Let me help with that.'
    assert turn.llm_mode == 'live'


@pytest.mark.asyncio
async def test_booking_intent_uses_llm_path_instead_of_canned_time(monkeypatch) -> None:
    agent = _make_agent()
    agent.policy_config = {'runtime': {'llm_provider': 'openai', 'llm_model': 'omnicoder'}}

    captured_request: dict = {}
    original_endpoint = agent_runtime.settings.llm_endpoint
    original_api_key = agent_runtime.settings.llm_api_key
    agent_runtime.settings.llm_endpoint = 'https://api.aetherpro.tech/v1/chat/completions'
    agent_runtime.settings.llm_api_key = 'test-key'

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                'choices': [
                    {
                        'message': {
                            'content': 'Absolutely. What day and time works best for the demo?',
                        }
                    }
                ]
            }

    async def fake_post(url, json, headers):  # noqa: ANN001 - httpx-compatible test shim
        captured_request['url'] = url
        captured_request['json'] = json
        captured_request['headers'] = headers
        return FakeResponse()

    monkeypatch.setattr(agent_runtime.http, 'post', fake_post)

    try:
        turn = await agent_runtime.generate_response(
            agent=agent,
            user_text='I want to book a demo',
            context={},
            collected_fields={},
        )
    finally:
        agent_runtime.settings.llm_endpoint = original_endpoint
        agent_runtime.settings.llm_api_key = original_api_key

    assert captured_request['json']['messages'][1]['content'] == 'I want to book a demo'
    assert turn.response_text == 'Absolutely. What day and time works best for the demo?'
    assert 'tomorrow at 2' not in turn.response_text.lower()
    assert turn.tool_calls is None
    assert turn.llm_mode == 'live'


@pytest.mark.asyncio
async def test_missing_required_fields_still_use_live_llm(monkeypatch) -> None:
    agent = _make_agent(
        {
            'name': {'prompt': 'Can I get your full name?'},
            'phone': {'prompt': 'What is the best callback number?'},
        }
    )
    agent.policy_config = {'runtime': {'llm_provider': 'openai', 'llm_model': 'qwen3.5-35b'}}

    captured_request: dict = {}
    original_endpoint = agent_runtime.settings.llm_endpoint
    original_api_key = agent_runtime.settings.llm_api_key
    agent_runtime.settings.llm_endpoint = 'https://api.aetherpro.tech/v1/chat/completions'
    agent_runtime.settings.llm_api_key = 'test-key'

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                'choices': [
                    {
                        'message': {
                            'content': 'I can help with that. What name should I put on this request?',
                        }
                    }
                ]
            }

    async def fake_post(url, json, headers):  # noqa: ANN001 - httpx-compatible test shim
        captured_request['url'] = url
        captured_request['json'] = json
        captured_request['headers'] = headers
        return FakeResponse()

    monkeypatch.setattr(agent_runtime.http, 'post', fake_post)

    try:
        turn = await agent_runtime.generate_response(
            agent=agent,
            user_text='I need to schedule service for tomorrow',
            context={},
            collected_fields={},
        )
    finally:
        agent_runtime.settings.llm_endpoint = original_endpoint
        agent_runtime.settings.llm_api_key = original_api_key

    assert 'Missing required fields' in captured_request['json']['messages'][0]['content']
    assert turn.llm_mode == 'live'
    assert turn.detected_intent == 'booking'
    assert turn.prompted_field == 'name'
    assert turn.missing_fields == ['name', 'phone']
    assert 'name should I put on this request' in turn.response_text


@pytest.mark.asyncio
async def test_llm_failure_falls_back_to_backend_prompt(monkeypatch) -> None:
    agent = _make_agent({'phone': {'prompt': 'What is the best callback number?'}})
    agent.policy_config = {'runtime': {'llm_provider': 'openai', 'llm_model': 'qwen3.5-35b'}}

    original_endpoint = agent_runtime.settings.llm_endpoint
    original_api_key = agent_runtime.settings.llm_api_key
    agent_runtime.settings.llm_endpoint = 'https://api.aetherpro.tech/v1/chat/completions'
    agent_runtime.settings.llm_api_key = 'test-key'

    async def fake_post(url, json, headers):  # noqa: ANN001 - httpx-compatible test shim
        raise RuntimeError('gateway offline')

    monkeypatch.setattr(agent_runtime.http, 'post', fake_post)

    try:
        turn = await agent_runtime.generate_response(
            agent=agent,
            user_text='I need help with my account',
            context={},
            collected_fields={},
        )
    finally:
        agent_runtime.settings.llm_endpoint = original_endpoint
        agent_runtime.settings.llm_api_key = original_api_key

    assert turn.llm_mode == 'fallback'
    assert turn.response_source == 'fallback_backend_flow'
    assert turn.fallback_reason == 'llm_request_failed'
    assert turn.prompted_field == 'phone'
    assert 'callback number' in turn.response_text.lower()


@pytest.mark.asyncio
async def test_captures_name_then_prompts_for_phone() -> None:
    agent = _make_agent(
        {
            'name': {'prompt': 'Can I get your full name?'},
            'phone': {'prompt': 'What is the best callback number?'},
        }
    )
    collected_fields: dict[str, str] = {}

    turn = await agent_runtime.generate_response(
        agent=agent,
        user_text='My name is Cory Smith',
        context={},
        collected_fields=collected_fields,
        prompted_field='name',
    )

    assert collected_fields['name'] == 'Cory Smith'
    assert turn.prompted_field == 'phone'
    assert 'callback number' in turn.response_text.lower()


@pytest.mark.asyncio
async def test_captures_phone_from_spoken_digits() -> None:
    agent = _make_agent({'phone': {'prompt': 'What is the best callback number?'}})
    collected_fields: dict[str, str] = {}

    turn = await agent_runtime.generate_response(
        agent=agent,
        user_text='eight one two nine six nine one three seven one',
        context={},
        collected_fields=collected_fields,
        prompted_field='phone',
    )

    assert collected_fields['phone'] == '8129691371'
    assert turn.outcome == 'success'
