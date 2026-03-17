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


def _make_agent(required_fields: dict | None = None) -> Agent:
    return Agent(
        tenant_id='00000000-0000-0000-0000-000000000001',
        name='Support',
        persona='calm',
        script='assist',
        required_fields=required_fields or {},
        tools_config={},
        policy_config={},
        workflow_dsl={},
    )


def test_build_opening_prompt_uses_first_required_field() -> None:
    agent = _make_agent(
        {
            'name': {'prompt': 'Can I get your full name?'},
            'phone': {'prompt': 'What is the best callback number?'},
        }
    )

    turn = agent_runtime.build_opening_prompt(agent=agent, collected_fields={})

    assert turn.prompted_field == 'name'
    assert 'Can I get your full name?' in turn.response_text


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
