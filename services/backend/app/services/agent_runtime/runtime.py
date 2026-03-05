from dataclasses import dataclass

import httpx

from app.core.config import get_settings
from app.models.models import Agent

ESCALATION_KEYWORDS = {'lawyer', 'sue', 'cancel now', 'human', 'manager', 'angry'}


@dataclass
class AgentTurn:
    response_text: str
    should_escalate: bool = False
    escalation_reason: str | None = None
    outcome: str | None = None
    tool_calls: list[dict] | None = None


class AgentRuntime:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.http = httpx.AsyncClient(timeout=25)

    async def generate_response(
        self,
        *,
        agent: Agent,
        user_text: str,
        context: dict,
        collected_fields: dict,
    ) -> AgentTurn:
        lowered = user_text.lower()
        if any(k in lowered for k in ESCALATION_KEYWORDS):
            return AgentTurn(
                response_text='I am transferring you to a human specialist now.',
                should_escalate=True,
                escalation_reason='sensitive_or_angry_signal',
            )

        required_fields = agent.required_fields or {}
        missing = [f for f in required_fields.keys() if not collected_fields.get(f)]
        if missing:
            prompt_field = missing[0]
            question = required_fields.get(prompt_field, {}).get(
                'prompt', f'Could you share your {prompt_field}?'
            )
            return AgentTurn(response_text=question)

        if 'book' in lowered or 'appointment' in lowered:
            return AgentTurn(
                response_text='I can book that now. Does tomorrow at 2:00 PM work for you?',
                tool_calls=[{'tool': 'booking_webhook', 'action': 'propose_time'}],
            )

        if self.settings.llm_provider in {'api', 'openai'} and self.settings.llm_endpoint:
            try:
                headers = {}
                if self.settings.llm_api_key:
                    headers['Authorization'] = f'Bearer {self.settings.llm_api_key}'
                if self.settings.llm_provider == 'openai':
                    payload = {
                        'model': self.settings.llm_model,
                        'messages': [
                            {
                                'role': 'system',
                                'content': (
                                    f'{agent.persona}\n\n'
                                    f'Script: {agent.script}\n'
                                    f'Policy: {agent.policy_config}\n'
                                    f'Context: {context}'
                                ),
                            },
                            {'role': 'user', 'content': user_text},
                        ],
                        'temperature': 0.2,
                    }
                    response = await self.http.post(
                        self.settings.llm_endpoint, json=payload, headers=headers
                    )
                    response.raise_for_status()
                    body = response.json()
                    choices = body.get('choices', [])
                    if choices:
                        model_text = (
                            choices[0].get('message', {}).get('content')
                            or 'How can I help further?'
                        )
                    else:
                        model_text = 'How can I help further?'
                else:
                    payload = {
                        'system_prompt': f'{agent.persona}\n\nPolicy:{agent.policy_config}',
                        'user_prompt': user_text,
                        'context': context,
                    }
                    response = await self.http.post(
                        self.settings.llm_endpoint, json=payload, headers=headers
                    )
                    response.raise_for_status()
                    model_text = response.json().get('text', 'How can I help further?')
                return AgentTurn(response_text=model_text)
            except Exception:
                pass

        return AgentTurn(response_text='Thanks, I captured that. What else can I help you with today?')


agent_runtime = AgentRuntime()
