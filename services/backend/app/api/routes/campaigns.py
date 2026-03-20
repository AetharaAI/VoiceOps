from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user, require_roles
from app.db.session import get_db
from app.models.models import Agent, OutboundCampaign, UserRole
from app.schemas.campaign import OutboundCampaignCreate, OutboundCampaignResponse, OutboundCampaignUpdate
from app.services.audit.service import audit_log

router = APIRouter(tags=['campaigns'])


def _to_campaign_response(campaign: OutboundCampaign) -> OutboundCampaignResponse:
    return OutboundCampaignResponse(
        id=str(campaign.id),
        tenant_id=str(campaign.tenant_id),
        agent_id=str(campaign.agent_id) if campaign.agent_id else None,
        name=campaign.name,
        caller_id_number=campaign.caller_id_number,
        lead_source=campaign.lead_source,
        objective=campaign.objective,
        opening_line=campaign.opening_line,
        qualification_fields=campaign.qualification_fields,
        objection_guidance=campaign.objection_guidance,
        booking_target=campaign.booking_target,
        retry_rules=campaign.retry_rules,
        voicemail_config=campaign.voicemail_config,
        handoff_rules=campaign.handoff_rules,
        crm_mapping=campaign.crm_mapping,
        llm_config=campaign.llm_config,
        tts_config=campaign.tts_config,
        is_active=campaign.is_active,
        created_at=campaign.created_at,
        updated_at=campaign.updated_at,
    )


async def _resolve_agent(
    db: AsyncSession,
    tenant_id: str,
    agent_id: str | None,
) -> Agent | None:
    if not agent_id:
        return None
    return (
        await db.execute(select(Agent).where(Agent.id == agent_id, Agent.tenant_id == tenant_id))
    ).scalar_one_or_none()


@router.post('/campaigns/outbound', response_model=OutboundCampaignResponse)
async def create_outbound_campaign(
    payload: OutboundCampaignCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.owner, UserRole.admin)),
) -> OutboundCampaignResponse:
    agent = await _resolve_agent(db, current_user.tenant_id, payload.agent_id)
    if payload.agent_id and agent is None:
        raise HTTPException(status_code=404, detail='Agent not found')

    campaign = OutboundCampaign(
        tenant_id=current_user.tenant_id,
        agent_id=payload.agent_id,
        name=payload.name,
        caller_id_number=payload.caller_id_number,
        lead_source=payload.lead_source,
        objective=payload.objective,
        opening_line=payload.opening_line,
        qualification_fields=payload.qualification_fields,
        objection_guidance=payload.objection_guidance,
        booking_target=payload.booking_target,
        retry_rules=payload.retry_rules,
        voicemail_config=payload.voicemail_config,
        handoff_rules=payload.handoff_rules,
        crm_mapping=payload.crm_mapping,
        llm_config=payload.llm_config,
        tts_config=payload.tts_config,
        is_active=payload.is_active,
    )
    db.add(campaign)
    await db.flush()

    await audit_log(
        db,
        tenant_id=current_user.tenant_id,
        action='campaign.outbound.create',
        resource_type='outbound_campaign',
        resource_id=str(campaign.id),
        actor_user_id=current_user.id,
        metadata={'name': payload.name, 'agent_id': payload.agent_id},
    )
    await db.commit()
    await db.refresh(campaign)
    return _to_campaign_response(campaign)


@router.get('/campaigns/outbound', response_model=list[OutboundCampaignResponse])
async def list_outbound_campaigns(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[OutboundCampaignResponse]:
    rows = (
        await db.execute(
            select(OutboundCampaign)
            .where(OutboundCampaign.tenant_id == current_user.tenant_id)
            .order_by(OutboundCampaign.created_at.desc())
        )
    ).scalars().all()
    return [_to_campaign_response(row) for row in rows]


@router.put('/campaigns/outbound/{campaign_id}', response_model=OutboundCampaignResponse)
async def update_outbound_campaign(
    campaign_id: str,
    payload: OutboundCampaignUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.owner, UserRole.admin)),
) -> OutboundCampaignResponse:
    campaign = (
        await db.execute(
            select(OutboundCampaign).where(
                OutboundCampaign.id == campaign_id,
                OutboundCampaign.tenant_id == current_user.tenant_id,
            )
        )
    ).scalar_one_or_none()
    if campaign is None:
        raise HTTPException(status_code=404, detail='Outbound campaign not found')

    if payload.agent_id is not None:
        agent = await _resolve_agent(db, current_user.tenant_id, payload.agent_id)
        if payload.agent_id and agent is None:
            raise HTTPException(status_code=404, detail='Agent not found')

    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(campaign, key, value)

    await audit_log(
        db,
        tenant_id=current_user.tenant_id,
        action='campaign.outbound.update',
        resource_type='outbound_campaign',
        resource_id=str(campaign.id),
        actor_user_id=current_user.id,
        metadata={'updated_fields': list(changes.keys())},
    )
    await db.commit()
    await db.refresh(campaign)
    return _to_campaign_response(campaign)
