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

    assert overrides == {'chat_template_kwargs': {'enable_thinking': False}}


def test_runtime_can_explicitly_enable_thinking() -> None:
    agent = _make_agent()
    agent.policy_config = {'runtime': {'llm_model': 'omnicoder', 'enable_thinking': True}}

    overrides = agent_runtime.llm_request_overrides_for_agent(agent=agent)

    assert overrides == {'chat_template_kwargs': {'enable_thinking': True}}


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
