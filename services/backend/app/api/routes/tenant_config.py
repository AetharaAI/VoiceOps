from datetime import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user, require_roles
from app.db.session import get_db
from app.models.models import BusinessHours, PhoneNumber, RoutingRule, UserRole
from app.schemas.tenant_config import (
    BusinessHourEntry,
    PhoneNumberCreate,
    PhoneNumberResponse,
    RoutingRuleCreate,
    RoutingRuleResponse,
)

router = APIRouter(tags=['tenant-config'])


@router.get('/phone-numbers', response_model=list[PhoneNumberResponse])
async def list_phone_numbers(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[PhoneNumberResponse]:
    rows = (
        await db.execute(select(PhoneNumber).where(PhoneNumber.tenant_id == current_user.tenant_id))
    ).scalars().all()
    return [
        PhoneNumberResponse(
            id=str(row.id), phone_number=row.phone_number, provider=row.provider, agent_id=str(row.agent_id) if row.agent_id else None
        )
        for row in rows
    ]


@router.post('/phone-numbers', response_model=PhoneNumberResponse)
async def create_phone_number(
    payload: PhoneNumberCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.owner, UserRole.admin)),
) -> PhoneNumberResponse:
    row = PhoneNumber(
        tenant_id=current_user.tenant_id,
        phone_number=payload.phone_number,
        provider=payload.provider,
        agent_id=payload.agent_id,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return PhoneNumberResponse(
        id=str(row.id),
        phone_number=row.phone_number,
        provider=row.provider,
        agent_id=str(row.agent_id) if row.agent_id else None,
    )


@router.get('/business-hours', response_model=list[BusinessHourEntry])
async def list_business_hours(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[BusinessHourEntry]:
    rows = (
        await db.execute(
            select(BusinessHours)
            .where(BusinessHours.tenant_id == current_user.tenant_id)
            .order_by(BusinessHours.day_of_week.asc())
        )
    ).scalars().all()
    return [
        BusinessHourEntry(
            day_of_week=row.day_of_week,
            start_time=row.start_time.strftime('%H:%M'),
            end_time=row.end_time.strftime('%H:%M'),
            timezone=row.timezone,
        )
        for row in rows
    ]


@router.put('/business-hours', response_model=list[BusinessHourEntry])
async def replace_business_hours(
    payload: list[BusinessHourEntry],
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.owner, UserRole.admin)),
) -> list[BusinessHourEntry]:
    await db.execute(delete(BusinessHours).where(BusinessHours.tenant_id == current_user.tenant_id))

    for item in payload:
        try:
            start_time = time.fromisoformat(item.start_time)
            end_time = time.fromisoformat(item.end_time)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail='Invalid time format; expected HH:MM') from exc

        db.add(
            BusinessHours(
                tenant_id=current_user.tenant_id,
                day_of_week=item.day_of_week,
                start_time=start_time,
                end_time=end_time,
                timezone=item.timezone,
            )
        )

    await db.commit()
    return payload


@router.get('/routing-rules', response_model=list[RoutingRuleResponse])
async def list_routing_rules(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[RoutingRuleResponse]:
    rows = (
        await db.execute(
            select(RoutingRule)
            .where(RoutingRule.tenant_id == current_user.tenant_id)
            .order_by(RoutingRule.priority.asc())
        )
    ).scalars().all()
    return [
        RoutingRuleResponse(
            id=str(r.id),
            name=r.name,
            priority=r.priority,
            rule_config=r.rule_config,
            target_agent_id=str(r.target_agent_id) if r.target_agent_id else None,
        )
        for r in rows
    ]


@router.post('/routing-rules', response_model=RoutingRuleResponse)
async def create_routing_rule(
    payload: RoutingRuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.owner, UserRole.admin)),
) -> RoutingRuleResponse:
    row = RoutingRule(
        tenant_id=current_user.tenant_id,
        name=payload.name,
        priority=payload.priority,
        rule_config=payload.rule_config,
        target_agent_id=payload.target_agent_id,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return RoutingRuleResponse(
        id=str(row.id),
        name=row.name,
        priority=row.priority,
        rule_config=row.rule_config,
        target_agent_id=str(row.target_agent_id) if row.target_agent_id else None,
    )
