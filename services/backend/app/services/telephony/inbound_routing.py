from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Agent, PhoneNumber


TWILIO_WEBHOOK_METADATA_FIELDS = (
    'CallerName',
    'CalledVia',
    'CallStatus',
    'CallToken',
    'Direction',
    'ForwardedFrom',
    'ParentCallSid',
    'StirVerstat',
)


def normalize_phone_number(number: str | None) -> str:
    if not number:
        return ''

    stripped = number.strip()
    if not stripped:
        return ''

    digits = ''.join(char for char in stripped if char.isdigit())
    if not digits:
        return ''
    if len(digits) == 10:
        return f'+1{digits}'
    if len(digits) == 11 and digits.startswith('1'):
        return f'+{digits}'
    return f'+{digits}'


def phone_number_matches(stored_number: str | None, incoming_number: str | None) -> bool:
    normalized_stored = normalize_phone_number(stored_number)
    normalized_incoming = normalize_phone_number(incoming_number)
    if not normalized_stored or not normalized_incoming:
        return False
    return normalized_stored == normalized_incoming


@dataclass(slots=True)
class InboundWebhookPayload:
    from_number: str
    to_number: str
    call_sid: str
    metadata: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    raw_form: dict[str, str] = field(default_factory=dict)

    @property
    def normalized_from_number(self) -> str:
        return normalize_phone_number(self.from_number)

    @property
    def normalized_to_number(self) -> str:
        return normalize_phone_number(self.to_number)


@dataclass(slots=True)
class InboundAgentResolution:
    tenant_id: str
    agent: Agent
    normalized_to_number: str
    normalized_from_number: str
    resolution_source: str
    phone_number_id: str | None = None
    matched_phone_number: str | None = None
    fallback_reason: str | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def used_fallback(self) -> bool:
        return self.fallback_reason is not None

    def to_context_payload(self) -> dict[str, Any]:
        return {
            'route': 'inbound',
            'resolver': {
                'source': self.resolution_source,
                'phone_number_id': self.phone_number_id,
                'matched_phone_number': self.matched_phone_number,
                'normalized_to_number': self.normalized_to_number,
                'normalized_from_number': self.normalized_from_number,
                'fallback_reason': self.fallback_reason,
                'warnings': list(self.warnings),
            },
            'resolved_agent': {
                'id': str(self.agent.id),
                'name': self.agent.name,
            },
        }


def build_inbound_webhook_payload(
    form_data: dict[str, Any],
    *,
    from_number: str = '',
    to_number: str = '',
    call_sid: str = '',
) -> InboundWebhookPayload:
    normalized_form = {str(key): str(value) for key, value in form_data.items()}

    payload = InboundWebhookPayload(
        from_number=from_number or normalized_form.get('From', ''),
        to_number=to_number or normalized_form.get('To', ''),
        call_sid=call_sid or normalized_form.get('CallSid', ''),
        metadata={field: normalized_form.get(field, '') for field in TWILIO_WEBHOOK_METADATA_FIELDS if normalized_form.get(field)},
        raw_form=normalized_form,
    )

    if not payload.from_number:
        payload.warnings.append('missing_from_number')
    if not payload.to_number:
        payload.warnings.append('missing_to_number')
    if not payload.call_sid:
        payload.warnings.append('missing_call_sid')
    if payload.metadata.get('ForwardedFrom'):
        payload.warnings.append('forwarded_call_detected')

    return payload


async def resolve_inbound_agent(
    db: AsyncSession,
    *,
    payload: InboundWebhookPayload,
) -> InboundAgentResolution:
    phone_rows = (await db.execute(select(PhoneNumber).order_by(PhoneNumber.created_at.asc()))).scalars().all()
    matching_rows = [row for row in phone_rows if phone_number_matches(row.phone_number, payload.to_number)]

    warnings: list[str] = []
    phone_row: PhoneNumber | None = None
    if matching_rows:
        phone_row = next((row for row in matching_rows if row.agent_id), matching_rows[0])
        if len(matching_rows) > 1:
            warnings.append('duplicate_phone_number_mapping')

    agent: Agent | None = None
    resolution_source = ''
    fallback_reason: str | None = None

    if phone_row and phone_row.agent_id:
        agent = (
            await db.execute(
                select(Agent).where(
                    Agent.id == phone_row.agent_id,
                    Agent.tenant_id == phone_row.tenant_id,
                    Agent.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
        if agent:
            resolution_source = 'phone_number_mapping'
        else:
            warnings.append('mapped_agent_missing_or_inactive')
            fallback_reason = 'mapped_agent_missing_or_inactive'

    if phone_row and agent is None:
        tenant_agents = (
            await db.execute(
                select(Agent)
                .where(Agent.tenant_id == phone_row.tenant_id, Agent.is_active.is_(True))
                .order_by(Agent.created_at.asc())
            )
        ).scalars().all()
        if len(tenant_agents) == 1:
            agent = tenant_agents[0]
            resolution_source = 'tenant_single_active_agent_fallback'
        elif tenant_agents:
            agent = tenant_agents[0]
            resolution_source = 'tenant_oldest_active_agent_fallback'
        if agent and fallback_reason is None:
            fallback_reason = 'mapped_number_missing_agent'

    if agent is None:
        global_agents = (
            await db.execute(select(Agent).where(Agent.is_active.is_(True)).order_by(Agent.created_at.asc()))
        ).scalars().all()
        if len(global_agents) == 1:
            agent = global_agents[0]
            resolution_source = 'global_single_active_agent_fallback'
        elif global_agents:
            agent = global_agents[0]
            resolution_source = 'global_oldest_active_agent_fallback'
        if agent and fallback_reason is None:
            fallback_reason = 'phone_number_mapping_not_found'

    if agent is None:
        raise LookupError('No active agent configured for inbound calls')

    return InboundAgentResolution(
        tenant_id=str(agent.tenant_id),
        agent=agent,
        normalized_to_number=payload.normalized_to_number,
        normalized_from_number=payload.normalized_from_number,
        resolution_source=resolution_source,
        phone_number_id=str(phone_row.id) if phone_row else None,
        matched_phone_number=phone_row.phone_number if phone_row else None,
        fallback_reason=fallback_reason,
        warnings=[*payload.warnings, *warnings],
    )
