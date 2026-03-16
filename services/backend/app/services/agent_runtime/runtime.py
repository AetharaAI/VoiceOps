import re
from dataclasses import dataclass, field

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.models import Agent
from app.services.realtime.audio import strip_control_markup

logger = get_logger(__name__)

ESCALATION_KEYWORDS = {'lawyer', 'sue', 'cancel now', 'human', 'manager', 'angry'}
GENERIC_NOISE = {'yes', 'yeah', 'yep', 'no', 'nope', 'hello', 'hi', 'okay', 'ok', 'sure'}
NAME_PREFIX_PATTERN = re.compile(r'^(my name is|name is|this is|i am|i\'m|it is|it\'s)\s+', re.IGNORECASE)
ISSUE_PREFIX_PATTERN = re.compile(
    r'^(i need|i am calling about|i\'m calling about|calling about|it\'s about|the issue is)\s+',
    re.IGNORECASE,
)
PHONE_WORDS = {
    'zero': '0',
    'oh': '0',
    'o': '0',
    'one': '1',
    'two': '2',
    'to': '2',
    'too': '2',
    'three': '3',
    'four': '4',
    'for': '4',
    'five': '5',
    'six': '6',
    'seven': '7',
    'eight': '8',
    'ate': '8',
    'nine': '9',
}


@dataclass
class AgentTurn:
    response_text: str
    should_escalate: bool = False
    escalation_reason: str | None = None
    outcome: str | None = None
    tool_calls: list[dict] | None = None
    prompted_field: str | None = None
    captured_fields: dict[str, str] = field(default_factory=dict)
    missing_fields: list[str] = field(default_factory=list)


class AgentRuntime:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.http = httpx.AsyncClient(timeout=25)

    def missing_required_fields(self, *, agent: Agent, collected_fields: dict) -> list[str]:
        required_fields = agent.required_fields or {}
        return [field_name for field_name in required_fields.keys() if not collected_fields.get(field_name)]

    def build_opening_prompt(self, *, agent: Agent, collected_fields: dict) -> AgentTurn:
        missing_fields = self.missing_required_fields(agent=agent, collected_fields=collected_fields)
        if not missing_fields:
            return AgentTurn(response_text=f'Hello, this is {agent.name}. How can I help today?')

        prompt_field = missing_fields[0]
        prompt = self._field_prompt(agent=agent, field_name=prompt_field)
        return AgentTurn(
            response_text=f'Hello, this is {agent.name}. {prompt}',
            prompted_field=prompt_field,
            missing_fields=missing_fields,
        )

    def build_retry_prompt(self, *, agent: Agent, field_name: str, retry_count: int) -> str:
        prompt = self._field_prompt(agent=agent, field_name=field_name)
        if retry_count <= 1:
            return f'Sorry, I missed that. {prompt}'
        return f'I want to make sure I get that right. {prompt}'

    def build_skip_ahead_prompt(self, *, agent: Agent, field_name: str, next_field: str | None) -> str:
        if next_field:
            return (
                f'No problem, we can come back to your {self._field_label(field_name)}. '
                f'{self._field_prompt(agent=agent, field_name=next_field)}'
            )
        return f'No problem. Please tell me a little about how I can help today.'

    async def generate_response(
        self,
        *,
        agent: Agent,
        user_text: str,
        context: dict,
        collected_fields: dict,
        prompted_field: str | None = None,
        telemetry_context: dict | None = None,
    ) -> AgentTurn:
        lowered = user_text.lower()
        if any(keyword in lowered for keyword in ESCALATION_KEYWORDS):
            return AgentTurn(
                response_text='I am transferring you to a human specialist now.',
                should_escalate=True,
                escalation_reason='sensitive_or_angry_signal',
                outcome='transfer_needed',
            )

        captured_fields = self.capture_required_fields(
            agent=agent,
            user_text=user_text,
            collected_fields=collected_fields,
            prompted_field=prompted_field,
        )
        if captured_fields:
            collected_fields.update(captured_fields)

        missing_fields = self.missing_required_fields(agent=agent, collected_fields=collected_fields)
        if missing_fields:
            next_field = missing_fields[0]
            return AgentTurn(
                response_text=self._field_prompt(agent=agent, field_name=next_field),
                prompted_field=next_field,
                captured_fields=captured_fields,
                missing_fields=missing_fields,
                outcome='partial_intake' if captured_fields else None,
            )

        if 'book' in lowered or 'appointment' in lowered:
            return AgentTurn(
                response_text='I can book that now. Does tomorrow at 2:00 PM work for you?',
                tool_calls=[{'tool': 'booking_webhook', 'action': 'propose_time'}],
                captured_fields=captured_fields,
                outcome='success',
            )

        if self.settings.llm_provider in {'api', 'openai'} and self.settings.llm_endpoint:
            try:
                headers = {}
                if self.settings.llm_api_key:
                    headers['Authorization'] = f'Bearer {self.settings.llm_api_key}'
                if telemetry_context:
                    logger.info(
                        'call.llm.request.start',
                        extra={
                            **telemetry_context,
                            'llm_provider': self.settings.llm_provider,
                            'llm_model': self.settings.llm_model,
                        },
                    )
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
                                    f'Context: {context}\n'
                                    f'Collected fields: {collected_fields}'
                                ),
                            },
                            {'role': 'user', 'content': user_text},
                        ],
                        'temperature': 0.2,
                    }
                    response = await self.http.post(self.settings.llm_endpoint, json=payload, headers=headers)
                    response.raise_for_status()
                    body = response.json()
                    choices = body.get('choices', [])
                    if choices:
                        model_text = choices[0].get('message', {}).get('content') or 'How can I help further?'
                    else:
                        model_text = 'How can I help further?'
                else:
                    payload = {
                        'system_prompt': f'{agent.persona}\n\nPolicy:{agent.policy_config}',
                        'user_prompt': user_text,
                        'context': context,
                    }
                    response = await self.http.post(self.settings.llm_endpoint, json=payload, headers=headers)
                    response.raise_for_status()
                    model_text = response.json().get('text', 'How can I help further?')
                if telemetry_context:
                    logger.info(
                        'call.llm.request.end',
                        extra={
                            **telemetry_context,
                            'llm_provider': self.settings.llm_provider,
                            'llm_model': self.settings.llm_model,
                            'llm_output_chars': len(model_text),
                        },
                    )
                return AgentTurn(
                    response_text=strip_control_markup(model_text),
                    captured_fields=captured_fields,
                    outcome='success',
                )
            except Exception as exc:
                if telemetry_context:
                    logger.warning(
                        'call.llm.request.failed',
                        extra={
                            **telemetry_context,
                            'llm_provider': self.settings.llm_provider,
                            'llm_model': self.settings.llm_model,
                            'error_type': type(exc).__name__,
                            'error': str(exc),
                        },
                    )

        return AgentTurn(
            response_text='Thank you. I have the details I need for now. What else can I help you with today?',
            captured_fields=captured_fields,
            outcome='success',
        )

    def capture_required_fields(
        self,
        *,
        agent: Agent,
        user_text: str,
        collected_fields: dict,
        prompted_field: str | None = None,
    ) -> dict[str, str]:
        missing_fields = self.missing_required_fields(agent=agent, collected_fields=collected_fields)
        ordered_fields: list[str] = []
        if prompted_field and prompted_field in missing_fields:
            ordered_fields.append(prompted_field)
        ordered_fields.extend(field_name for field_name in missing_fields if field_name not in ordered_fields)

        captured: dict[str, str] = {}
        for field_name in ordered_fields:
            value = self._extract_field_value(field_name=field_name, user_text=user_text)
            if value:
                captured[field_name] = value
        return captured

    def _field_prompt(self, *, agent: Agent, field_name: str) -> str:
        return (agent.required_fields or {}).get(field_name, {}).get(
            'prompt',
            f'Could you share your {self._field_label(field_name)}?',
        )

    def _field_label(self, field_name: str) -> str:
        return field_name.replace('_', ' ')

    def _extract_field_value(self, *, field_name: str, user_text: str) -> str | None:
        lowered_name = field_name.lower()
        if lowered_name in {'name', 'full_name', 'customer_name'}:
            return self._extract_name(user_text)
        if lowered_name in {'phone', 'phone_number', 'callback_number', 'callback_phone', 'best_callback_number'}:
            return self._extract_phone(user_text)
        if lowered_name in {'issue', 'service_request', 'problem', 'reason_for_call', 'appointment_type'}:
            return self._extract_issue(user_text)
        return self._extract_generic_text(user_text)

    def _extract_name(self, user_text: str) -> str | None:
        cleaned = NAME_PREFIX_PATTERN.sub('', user_text).strip(" .,!?:;\"'")
        if not cleaned or any(char.isdigit() for char in cleaned):
            return None
        parts = [part for part in re.split(r'\s+', cleaned) if part]
        if not 1 <= len(parts) <= 4:
            return None
        if any(part.lower() in {'need', 'calling', 'issue', 'problem', 'service'} for part in parts):
            return None
        if ' '.join(parts).lower() in GENERIC_NOISE:
            return None
        if not all(re.fullmatch(r"[A-Za-z][A-Za-z'\-]*", part) for part in parts):
            return None
        return ' '.join(part.capitalize() for part in parts)

    def _extract_phone(self, user_text: str) -> str | None:
        digits = ''.join(char for char in user_text if char.isdigit())
        if len(digits) < 10:
            normalized_tokens = []
            for token in re.findall(r"[A-Za-z0-9']+", user_text.lower()):
                if token.isdigit():
                    normalized_tokens.append(token)
                elif token in PHONE_WORDS:
                    normalized_tokens.append(PHONE_WORDS[token])
            digits = ''.join(normalized_tokens)

        if len(digits) == 11 and digits.startswith('1'):
            return f'+{digits}'
        if len(digits) >= 10:
            return digits[-10:]
        return None

    def _extract_issue(self, user_text: str) -> str | None:
        cleaned = ISSUE_PREFIX_PATTERN.sub('', user_text).strip(" .,!?:;\"'")
        if len(cleaned) < 8:
            return None
        if cleaned.lower() in GENERIC_NOISE:
            return None
        return cleaned

    def _extract_generic_text(self, user_text: str) -> str | None:
        cleaned = user_text.strip(" .,!?:;\"'")
        if len(cleaned) < 3 or cleaned.lower() in GENERIC_NOISE:
            return None
        return cleaned


agent_runtime = AgentRuntime()
