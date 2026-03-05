from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user, require_roles
from app.core.config import get_settings
from app.core.metrics import CALLS_COMPLETED, CALLS_STARTED
from app.db.session import get_db
from app.models.models import Agent, Call, CallDirection, CallStatus, TranscriptSegment, UserRole
from app.schemas.call import CallDetailResponse, CallResponse, OutboundCallRequest, TranscriptSegmentResponse
from app.services.audit.service import audit_log
from app.services.telephony.providers import get_telephony_provider

router = APIRouter(tags=['calls'])


@router.post('/calls/outbound', response_model=CallResponse)
async def create_outbound_call(
    payload: OutboundCallRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.owner, UserRole.admin, UserRole.agent)),
) -> CallResponse:
    if payload.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail='Cross-tenant call creation not allowed')

    agent = (
        await db.execute(select(Agent).where(Agent.id == payload.agent_id, Agent.tenant_id == current_user.tenant_id))
    ).scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail='Agent not found')

    settings = get_settings()
    from_number = settings.twilio_from_number or '+10000000000'

    call = Call(
        tenant_id=current_user.tenant_id,
        agent_id=payload.agent_id,
        direction=CallDirection.outbound,
        status=CallStatus.queued,
        from_number=from_number,
        to_number=payload.to_number,
        campaign_id=payload.campaign_id,
        context_payload=payload.context_payload,
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
        metadata={'to': payload.to_number, 'agent_id': payload.agent_id},
    )

    await db.commit()
    await db.refresh(call)
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
        escalation_reason=call.escalation_reason,
        started_at=call.started_at,
        ended_at=call.ended_at,
    )
