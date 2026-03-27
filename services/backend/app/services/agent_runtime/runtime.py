import re
from dataclasses import dataclass, field

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.models import Agent
from app.services.realtime.audio import strip_control_markup
from app.services.telephony.event_sink import call_event_sink

logger = get_logger(__name__)

ESCALATION_KEYWORDS = {'lawyer', 'sue', 'cancel now', 'human', 'manager', 'angry'}
GENERIC_NOISE = {'yes', 'yeah', 'yep', 'no', 'nope', 'hello', 'hi', 'okay', 'ok', 'sure'}
NAME_NOISE_WORDS = {
    'my', 'name', 'is', 'this', 'i', 'am', "i'm", 'it', "it's",
    'uh', 'um', 'hmm', 'well', 'why', 'like', 'so', 'just',
}
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
RECOVERY_PREFIXES = {
    'no_speech': [
        "I didn't hear anything there.",
        'The line was quiet for a moment.',
        "I'm not getting any audio just yet.",
    ],
    'partial_unclear_speech': [
        "I caught part of that, but not enough to be sure.",
        'That came through a little unclear.',
        "I only got part of that on my end.",
    ],
    'unusable_input': [
        "I didn't catch that clearly.",
        "I want to make sure I heard you right.",
        'That sounded a little unclear to me.',
    ],
    'caller_interruption': [
        "No problem, let's pick that back up.",
        "You're fine, let's try that once more.",
        "Let's start from there again.",
    ],
    'line_artifact': [
        'The line broke up for a second.',
        'That sounded a little distorted on my end.',
        'The audio cut out there for a moment.',
    ],
    'generic': [
        "Let's try that one more time.",
        'Could you say that again for me?',
        "Let's go over that once more.",
    ],
}
CONNECTION_CHECK_PROMPTS = [
    "I'm having trouble hearing you clearly on this line.",
    'The audio is still breaking up on my end.',
]


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
    llm_mode: str = 'scripted'
    response_source: str = 'scripted_backend_flow'
    detected_intent: str = 'general'
    fallback_reason: str | None = None


class AgentRuntime:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.http = httpx.AsyncClient(timeout=25)

    def runtime_config(self, *, agent: Agent) -> dict:
        return ((agent.policy_config or {}).get('runtime') or {})

    def llm_provider_for_agent(self, *, agent: Agent) -> str:
        return self.runtime_config(agent=agent).get('llm_provider', self.settings.llm_provider)

    def llm_model_for_agent(self, *, agent: Agent) -> str:
        return self.runtime_config(agent=agent).get('llm_model', self.settings.llm_model)

    def tts_provider_for_agent(self, *, agent: Agent) -> str:
        return self.runtime_config(agent=agent).get('tts_provider', 'aether_voice')

    def tts_model_for_agent(self, *, agent: Agent) -> str:
        return self.runtime_config(agent=agent).get('tts_model', self.settings.aether_voice_tts_model)

    def tts_voice_for_agent(self, *, agent: Agent) -> str:
        return self.runtime_config(agent=agent).get('tts_voice', self.settings.aether_voice_tts_voice)

    def tts_metadata_for_agent(self, *, agent: Agent) -> dict:
        metadata = self.runtime_config(agent=agent).get('tts_metadata')
        return metadata if isinstance(metadata, dict) else {}

    def opening_greeting_for_agent(self, *, agent: Agent) -> str:
        greeting = self.runtime_config(agent=agent).get('opening_greeting', '')
        return greeting.strip() if isinstance(greeting, str) else ''

    def llm_request_overrides_for_agent(self, *, agent: Agent) -> dict:
        runtime = self.runtime_config(agent=agent)
        model = self.llm_model_for_agent(agent=agent)
        model_name = model.lower()
        enable_thinking = runtime.get('enable_thinking')
        if enable_thinking is None and (model_name.startswith('qwen') or model_name == 'omnicoder'):
            enable_thinking = False

        if enable_thinking is None:
            return {}
        return {
            'extra_body': {
                'chat_template_kwargs': {
                    'enable_thinking': bool(enable_thinking),
                }
            },
        }

    def missing_required_fields(self, *, agent: Agent, collected_fields: dict) -> list[str]:
        required_fields = agent.required_fields or {}
        runtime = self.runtime_config(agent=agent)
        require_organization = bool(runtime.get('require_organization', False))
        optional_org_fields = {'organization', 'company', 'company_name', 'business_name'}

        missing: list[str] = []
        for field_name in required_fields.keys():
            if field_name.lower() in optional_org_fields and not require_organization:
                continue
            if not collected_fields.get(field_name):
                missing.append(field_name)
        return missing

    def build_opening_prompt(self, *, agent: Agent, collected_fields: dict) -> AgentTurn:
        missing_fields = self.missing_required_fields(agent=agent, collected_fields=collected_fields)
        custom_greeting = self.opening_greeting_for_agent(agent=agent)
        first_missing_field = missing_fields[0] if missing_fields else None
        if not missing_fields:
            response_text = custom_greeting or f'Hello, this is {agent.name}. How can I help today?'
            return AgentTurn(response_text=response_text, llm_mode='scripted', response_source='scripted_greeting')

        if custom_greeting:
            response_text = custom_greeting
        else:
            response_text = f'Hello, this is {agent.name}. How can I help today?'
        return AgentTurn(
            response_text=response_text,
            prompted_field=first_missing_field,
            missing_fields=missing_fields,
            llm_mode='scripted',
            response_source='scripted_greeting',
        )

    def detect_intent(self, *, user_text: str, collected_fields: dict) -> str:
        lowered = user_text.lower()
        if any(keyword in lowered for keyword in {'book', 'appointment', 'schedule', 'demo'}):
            return 'booking'
        if any(keyword in lowered for keyword in {'quote', 'estimate', 'pricing', 'price'}):
            return 'quote'
        if any(keyword in lowered for keyword in {'support', 'help', 'issue', 'problem', 'broken'}):
            return 'support'
        if any(keyword in lowered for keyword in {'sales', 'buy', 'service', 'install'}):
            return 'sales'
        if collected_fields:
            return 'intake_in_progress'
        return 'general'

    def build_llm_system_prompt(
        self,
        *,
        agent: Agent,
        context: dict,
        collected_fields: dict,
        missing_fields: list[str],
        prompted_field: str | None,
        detected_intent: str,
    ) -> str:
        active_field = prompted_field or (missing_fields[0] if missing_fields else '')
        return (
            f'{agent.persona}\n\n'
            f'Script: {agent.script}\n'
            f'Policy: {agent.policy_config}\n'
            f'Context: {context}\n'
            f'Detected intent: {detected_intent}\n'
            f'Collected fields: {collected_fields}\n'
            f'Missing required fields: {missing_fields}\n'
            f'Current extraction target: {active_field}\n\n'
            'You are responding on a live phone call. Speak naturally, briefly, and conversationally.\n'
            'Use plain spoken sentences only. Do not include chuckles, laughter, stage directions, or sound effects.\n'
            'Do not use filler words (for example: um, uh, hmm) and avoid trailing ellipses.\n'
            'Keep each response to 1-2 short sentences unless the caller explicitly asks for more detail.\n'
            'Lead with understanding the caller intent and guide the conversation from there.\n'
            'If required fields are still missing, gather them naturally during the conversation instead of reading a rigid checklist.\n'
            'Ask only the next most useful question. Do not ask multiple stacked questions in one turn.\n'
            'Do not invent confirmed appointments, times, transfers, or external actions that have not actually executed.\n'
            'If the caller already gave a detail, acknowledge it and move forward.\n'
            'Return only the exact spoken reply text for the next turn.'
        )

    def build_retry_prompt(self, *, agent: Agent, field_name: str, retry_count: int) -> str:
        return self.build_field_retry_prompt(
            agent=agent,
            field_name=field_name,
            retry_count=retry_count,
            retry_reason='unusable_input',
            previous_prompt='',
        )

    def build_field_retry_prompt(
        self,
        *,
        agent: Agent,
        field_name: str,
        retry_count: int,
        retry_reason: str,
        previous_prompt: str,
    ) -> str:
        prompt = self._field_prompt(agent=agent, field_name=field_name)
        prefix = self._choose_recovery_prefix(
            retry_reason=retry_reason,
            retry_count=retry_count,
            previous_prompt=previous_prompt,
            include_prompt=prompt,
        )
        return f'{prefix} {prompt}'.strip()

    def build_general_recovery_prompt(
        self,
        *,
        retry_reason: str,
        retry_count: int,
        previous_prompt: str,
    ) -> str:
        return self._choose_recovery_prefix(
            retry_reason=retry_reason,
            retry_count=retry_count,
            previous_prompt=previous_prompt,
            include_prompt='',
        )

    def build_skip_ahead_prompt(self, *, agent: Agent, field_name: str, next_field: str | None) -> str:
        if next_field:
            return (
                f'No problem, we can come back to your {self._field_label(field_name)}. '
                f'{self._field_prompt(agent=agent, field_name=next_field)}'
            )
        return f'No problem. Please tell me a little about how I can help today.'

    def build_connection_check_prompt(self, *, previous_prompt: str) -> str:
        for prompt in CONNECTION_CHECK_PROMPTS:
            if prompt != previous_prompt:
                return prompt
        return CONNECTION_CHECK_PROMPTS[0]

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
        detected_intent = self.detect_intent(user_text=user_text, collected_fields=collected_fields)
        if any(keyword in lowered for keyword in ESCALATION_KEYWORDS):
            return AgentTurn(
                response_text='I am transferring you to a human specialist now.',
                should_escalate=True,
                escalation_reason='sensitive_or_angry_signal',
                outcome='transfer_needed',
                llm_mode='scripted',
                response_source='guardrail_escalation',
                detected_intent=detected_intent,
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
        llm_provider = self.llm_provider_for_agent(agent=agent)
        llm_model = self.llm_model_for_agent(agent=agent)
        llm_request_overrides = self.llm_request_overrides_for_agent(agent=agent)
        if llm_provider in {'api', 'openai'} and self.settings.llm_endpoint:
            try:
                headers = {}
                if self.settings.llm_api_key:
                    headers['Authorization'] = f'Bearer {self.settings.llm_api_key}'
                if telemetry_context:
                    event = call_event_sink.build_event(
                        event_type='call.llm.request.start',
                        level='info',
                        llm_provider=llm_provider,
                        llm_model=llm_model,
                        llm_mode='live',
                        call_id=telemetry_context.get('call_id', ''),
                        call_sid=telemetry_context.get('call_sid', ''),
                        tenant_id=telemetry_context.get('tenant_id', ''),
                        direction=telemetry_context.get('direction', telemetry_context.get('route', '')),
                        route=telemetry_context.get('route', ''),
                        agent_id=telemetry_context.get('resolved_agent_id', ''),
                        agent_name=telemetry_context.get('resolved_agent_name', ''),
                        correlation_id=telemetry_context.get('correlation_id', ''),
                        from_number=telemetry_context.get('from_number', ''),
                        to_number=telemetry_context.get('to_number', ''),
                        llm_request_index=telemetry_context.get('llm_request_index'),
                        resolved_model=llm_model,
                        non_thinking_enabled=bool(
                            ((llm_request_overrides.get('extra_body') or {}).get('chat_template_kwargs') or {}).get(
                                'enable_thinking'
                            )
                            is False
                        ),
                        llm_request_shape={
                            'message_count': 2,
                            'temperature': 0.2,
                            'has_extra_body': bool(llm_request_overrides.get('extra_body')),
                            'extra_body_keys': sorted((llm_request_overrides.get('extra_body') or {}).keys()),
                        },
                        llm_request_overrides=llm_request_overrides,
                    )
                    logger.info('call.llm.request.start', extra=event)
                    call_event_sink.record_event(event)
                if llm_provider == 'openai':
                    payload = {
                        'model': llm_model,
                        'messages': [
                            {
                                'role': 'system',
                                'content': self.build_llm_system_prompt(
                                    agent=agent,
                                    context=context,
                                    collected_fields=collected_fields,
                                    missing_fields=missing_fields,
                                    prompted_field=prompted_field,
                                    detected_intent=detected_intent,
                                ),
                            },
                            {'role': 'user', 'content': user_text},
                        ],
                        'temperature': 0.2,
                    }
                    payload.update(llm_request_overrides)
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
                    event = call_event_sink.build_event(
                        event_type='call.llm.request.end',
                        level='info',
                        llm_provider=llm_provider,
                        llm_model=llm_model,
                        llm_mode='live',
                        call_id=telemetry_context.get('call_id', ''),
                        call_sid=telemetry_context.get('call_sid', ''),
                        tenant_id=telemetry_context.get('tenant_id', ''),
                        direction=telemetry_context.get('direction', telemetry_context.get('route', '')),
                        route=telemetry_context.get('route', ''),
                        agent_id=telemetry_context.get('resolved_agent_id', ''),
                        agent_name=telemetry_context.get('resolved_agent_name', ''),
                        correlation_id=telemetry_context.get('correlation_id', ''),
                        from_number=telemetry_context.get('from_number', ''),
                        to_number=telemetry_context.get('to_number', ''),
                        llm_output_chars=len(model_text),
                        llm_request_index=telemetry_context.get('llm_request_index'),
                        llm_request_overrides=llm_request_overrides,
                    )
                    logger.info('call.llm.request.end', extra=event)
                    call_event_sink.record_event(event)
                sanitized_text = strip_control_markup(model_text)
                if not sanitized_text:
                    sanitized_text = 'Let me help with that.'
                return AgentTurn(
                    response_text=sanitized_text,
                    prompted_field=missing_fields[0] if missing_fields else None,
                    captured_fields=captured_fields,
                    missing_fields=missing_fields,
                    outcome='partial_intake' if missing_fields else 'success',
                    llm_mode='live',
                    response_source='live_llm_generation',
                    detected_intent=detected_intent,
                )
            except Exception as exc:
                if telemetry_context:
                    event = call_event_sink.build_event(
                        event_type='call.llm.request.failed',
                        level='warning',
                        llm_provider=llm_provider,
                        llm_model=llm_model,
                        llm_mode='fallback',
                        call_id=telemetry_context.get('call_id', ''),
                        call_sid=telemetry_context.get('call_sid', ''),
                        tenant_id=telemetry_context.get('tenant_id', ''),
                        direction=telemetry_context.get('direction', telemetry_context.get('route', '')),
                        route=telemetry_context.get('route', ''),
                        agent_id=telemetry_context.get('resolved_agent_id', ''),
                        agent_name=telemetry_context.get('resolved_agent_name', ''),
                        correlation_id=telemetry_context.get('correlation_id', ''),
                        from_number=telemetry_context.get('from_number', ''),
                        to_number=telemetry_context.get('to_number', ''),
                        llm_request_index=telemetry_context.get('llm_request_index'),
                        llm_request_overrides=llm_request_overrides,
                        error_type=type(exc).__name__,
                        error=str(exc),
                    )
                    logger.warning('call.llm.request.failed', extra=event)
                    call_event_sink.record_event(event)
                    call_event_sink.record_event(
                        call_event_sink.build_event(
                            event_type='call.llm.request.fail',
                            level='warning',
                            llm_provider=llm_provider,
                            llm_model=llm_model,
                            llm_mode='fallback',
                            call_id=telemetry_context.get('call_id', ''),
                            call_sid=telemetry_context.get('call_sid', ''),
                            tenant_id=telemetry_context.get('tenant_id', ''),
                            direction=telemetry_context.get('direction', telemetry_context.get('route', '')),
                            route=telemetry_context.get('route', ''),
                            agent_id=telemetry_context.get('resolved_agent_id', ''),
                            agent_name=telemetry_context.get('resolved_agent_name', ''),
                            correlation_id=telemetry_context.get('correlation_id', ''),
                            from_number=telemetry_context.get('from_number', ''),
                            to_number=telemetry_context.get('to_number', ''),
                            llm_request_index=telemetry_context.get('llm_request_index'),
                            llm_request_overrides=llm_request_overrides,
                            error_type=type(exc).__name__,
                            error=str(exc),
                        )
                    )
                next_field = missing_fields[0] if missing_fields else None
                fallback_text = (
                    self._field_prompt(agent=agent, field_name=next_field)
                    if next_field
                    else 'Thank you. I have the details I need for now. What else can I help you with today?'
                )
                return AgentTurn(
                    response_text=fallback_text,
                    prompted_field=next_field,
                    captured_fields=captured_fields,
                    missing_fields=missing_fields,
                    outcome='partial_intake' if missing_fields else 'success',
                    llm_mode='fallback',
                    response_source='fallback_backend_flow',
                    detected_intent=detected_intent,
                    fallback_reason='llm_request_failed',
                )

        next_field = missing_fields[0] if missing_fields else None
        fallback_text = (
            self._field_prompt(agent=agent, field_name=next_field)
            if next_field
            else 'Thank you. I have the details I need for now. What else can I help you with today?'
        )
        return AgentTurn(
            response_text=fallback_text,
            prompted_field=next_field,
            captured_fields=captured_fields,
            missing_fields=missing_fields,
            outcome='partial_intake' if missing_fields else 'success',
            llm_mode='scripted',
            response_source='scripted_backend_flow',
            detected_intent=detected_intent,
            fallback_reason='llm_not_configured',
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
        ordered_fields: list[str]
        if prompted_field and prompted_field in missing_fields:
            # Keep extraction aligned with the current question to avoid
            # polluting unrelated fields from noisy utterances.
            ordered_fields = [prompted_field]
        else:
            ordered_fields = list(missing_fields)

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
            cleaned = ''
        parts = [part for part in re.split(r'\s+', cleaned) if part]
        if 1 <= len(parts) <= 4:
            if any(part.lower() in {'need', 'calling', 'issue', 'problem', 'service'} for part in parts):
                return None
            if ' '.join(parts).lower() in GENERIC_NOISE:
                return None
            if all(re.fullmatch(r"[A-Za-z][A-Za-z'\-]*", part) for part in parts):
                return ' '.join(part.capitalize() for part in parts)

        # Fallback for noisy telephony snippets like "Why, Mary" or "it's good, Corey".
        tokens = re.findall(r"[A-Za-z][A-Za-z'\-]*", user_text)
        if len(tokens) > 4:
            return None
        candidates = [t for t in tokens if t.lower() not in NAME_NOISE_WORDS]
        if not candidates:
            return None
        candidate = candidates[-1]
        if len(candidate) < 2:
            return None
        return candidate.capitalize()

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

    def _choose_recovery_prefix(
        self,
        *,
        retry_reason: str,
        retry_count: int,
        previous_prompt: str,
        include_prompt: str,
    ) -> str:
        options = RECOVERY_PREFIXES.get(retry_reason, RECOVERY_PREFIXES['generic'])
        preferred_index = max(0, min(retry_count - 1, len(options) - 1))
        ordered_candidates = options[preferred_index:] + options[:preferred_index]
        for candidate in ordered_candidates:
            combined = f'{candidate} {include_prompt}'.strip()
            if combined != previous_prompt:
                return candidate
        return ordered_candidates[0]


agent_runtime = AgentRuntime()
