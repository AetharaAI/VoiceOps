from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user, require_roles
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.metrics import CALLS_COMPLETED, CALLS_STARTED
from app.db.session import get_db
from app.models.models import Agent, Call, CallDirection, CallStatus, OutboundCampaign, TranscriptSegment, UserRole
from app.schemas.call import CallDetailResponse, CallLogResponse, CallResponse, OutboundCallRequest, TranscriptSegmentResponse
from app.services.audit.service import audit_log
from app.services.telephony.event_sink import call_event_sink
from app.services.telephony.telemetry import utc_now_iso
from app.services.telephony.providers import get_telephony_provider

router = APIRouter(tags=['calls'])
logger = get_logger(__name__)


@router.post('/calls/outbound', response_model=CallResponse)
async def create_outbound_call(
    payload: OutboundCallRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.owner, UserRole.admin, UserRole.agent)),
) -> CallResponse:
    if payload.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail='Cross-tenant call creation not allowed')

    campaign = None
    if payload.campaign_id:
        campaign = (
            await db.execute(
                select(OutboundCampaign).where(
                    OutboundCampaign.id == payload.campaign_id,
                    OutboundCampaign.tenant_id == current_user.tenant_id,
                )
            )
        ).scalar_one_or_none()
        if campaign is None:
            raise HTTPException(status_code=404, detail='Outbound campaign not found')

    resolved_agent_id = payload.agent_id or (str(campaign.agent_id) if campaign and campaign.agent_id else None)
    if not resolved_agent_id:
        raise HTTPException(status_code=400, detail='Agent is required when campaign does not provide one')

    agent = (
        await db.execute(select(Agent).where(Agent.id == resolved_agent_id, Agent.tenant_id == current_user.tenant_id))
    ).scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail='Agent not found')

    settings = get_settings()
    from_number = (
        (campaign.caller_id_number if campaign and campaign.caller_id_number else None)
        or settings.twilio_from_number
        or '+10000000000'
    )

    call = Call(
        tenant_id=current_user.tenant_id,
        agent_id=agent.id,
        direction=CallDirection.outbound,
        status=CallStatus.queued,
        from_number=from_number,
        to_number=payload.to_number,
        campaign_id=payload.campaign_id,
        context_payload={
            **payload.context_payload,
            'telephony': {
                **(payload.context_payload.get('telephony') or {}),
                # Outbound calls choose the agent here in the UI/API flow. The later
                # Twilio webhook only reuses this persisted call_id and must not
                # re-resolve the agent from inbound number mapping.
                'route': 'outbound',
                'selected_agent': {
                    'id': str(agent.id),
                    'name': agent.name,
                },
                'campaign': (
                    {
                        'id': str(campaign.id),
                        'name': campaign.name,
                        'objective': campaign.objective,
                        'opening_line': campaign.opening_line,
                        'lead_source': campaign.lead_source,
                    }
                    if campaign
                    else None
                ),
                'outbound_created_at': utc_now_iso(),
            },
        },
    )
    db.add(call)
    await db.flush()

    provider = get_telephony_provider('twilio')
    callback = f'{settings.public_base_url}/api/v1/webhooks/telephony/inbound?call_id={call.id}'
    result = await provider.create_outbound_call(payload.to_number, from_number, callback)
    call.external_call_id = result.external_call_id
    call.status = CallStatus.ringing if result.status in {'queued', 'ringing'} else CallStatus.in_progress
    CALLS_STARTED.labels(tenant_id=current_user.tenant_id, direction='outbound').inc()

    await audit_log(
        db,
        tenant_id=current_user.tenant_id,
        action='call.outbound.create',
        resource_type='call',
        resource_id=str(call.id),
        actor_user_id=current_user.id,
        metadata={'to': payload.to_number, 'agent_id': str(agent.id), 'campaign_id': payload.campaign_id},
    )

    await db.commit()
    await db.refresh(call)
    logger.info(
        'telephony.outbound.call_created',
        extra={
            'correlation_id': '',
            'tenant_id': str(call.tenant_id),
            'call_id': str(call.id),
            'call_sid': call.external_call_id or '',
            'route': 'outbound',
            'from_number': call.from_number,
            'to_number': call.to_number,
            'agent_id': str(agent.id),
            'agent_name': agent.name,
            'campaign_id': call.campaign_id or '',
        },
    )
    call_event_sink.record_event(
        call_event_sink.build_event(
            event_type='telephony.outbound.call_created',
            level='info',
            call_id=str(call.id),
            call_sid=call.external_call_id or '',
            tenant_id=str(call.tenant_id),
            direction='outbound',
            route='outbound',
            agent_id=str(agent.id),
            agent_name=agent.name,
            from_number=call.from_number,
            to_number=call.to_number,
            campaign_id=call.campaign_id or '',
        )
    )
    return _to_call_response(call)


@router.get('/calls', response_model=list[CallResponse])
async def list_calls(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[CallResponse]:
    rows = (
        await db.execute(select(Call).where(Call.tenant_id == current_user.tenant_id).order_by(Call.started_at.desc()))
    ).scalars().all()
    return [_to_call_response(call) for call in rows]


@router.get('/calls/{call_id}', response_model=CallDetailResponse)
async def call_detail(
    call_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> CallDetailResponse:
    call = (
        await db.execute(select(Call).where(Call.id == call_id, Call.tenant_id == current_user.tenant_id))
    ).scalar_one_or_none()
    if not call:
        raise HTTPException(status_code=404, detail='Call not found')

    transcript_rows = (
        await db.execute(
            select(TranscriptSegment)
            .where(TranscriptSegment.call_id == call.id, TranscriptSegment.tenant_id == current_user.tenant_id)
            .order_by(TranscriptSegment.created_at.asc())
        )
    ).scalars().all()

    return CallDetailResponse(
        **_to_call_response(call).model_dump(),
        transcript=[
            TranscriptSegmentResponse(
                id=str(seg.id),
                speaker=seg.speaker,
                text=seg.text,
                is_final=seg.is_final,
                confidence=seg.confidence,
                started_ms=seg.started_ms,
                ended_ms=seg.ended_ms,
            )
            for seg in transcript_rows
        ],
    )


@router.get('/call-logs/latest', response_model=list[CallLogResponse])
async def latest_call_logs(
    limit: int = Query(default=1, ge=1, le=20),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[CallLogResponse]:
    logs = call_event_sink.latest_logs(limit=limit, tenant_id=str(current_user.tenant_id))
    return [CallLogResponse(**log) for log in logs]


@router.get('/call-logs/by-call-sid/{call_sid}', response_model=CallLogResponse)
async def call_log_by_call_sid(
    call_sid: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> CallLogResponse:
    log = call_event_sink.find_by_call_sid(call_sid=call_sid, tenant_id=str(current_user.tenant_id))
    if log is None:
        raise HTTPException(status_code=404, detail='Call log not found')
    return CallLogResponse(**log)


async def mark_call_completed(db: AsyncSession, call: Call, status: CallStatus) -> None:
    call.status = status
    call.ended_at = datetime.now(timezone.utc)
    CALLS_COMPLETED.labels(tenant_id=str(call.tenant_id), status=status.value).inc()
    await db.flush()


def _to_call_response(call: Call) -> CallResponse:
    return CallResponse(
        id=str(call.id),
        tenant_id=str(call.tenant_id),
        agent_id=str(call.agent_id) if call.agent_id else None,
        external_call_id=call.external_call_id,
        direction=call.direction,
        status=call.status,
        from_number=call.from_number,
        to_number=call.to_number,
        campaign_id=call.campaign_id,
        context_payload=call.context_payload,
        outcome=call.outcome,
        outcome_tags=call.outcome_tags,
        escalation_reason=call.escalation_reason,
        started_at=call.started_at,
        ended_at=call.ended_at,
    )
