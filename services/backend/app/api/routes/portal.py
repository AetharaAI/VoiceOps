from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user, require_roles
from app.db.session import get_db
from app.models.models import AuditEvent, BusinessHours, Call, Tenant, User, UserRole
from app.schemas.portal import (
    PortalAgentModeResponse,
    PortalAgentModeUpdateRequest,
    PortalAuditLogEntry,
    PortalAuditLogResponse,
    PortalBusinessProfileResponse,
    PortalDashboardRecentCall,
    PortalDashboardResponse,
)
from app.services.analytics.service import summary_for_tenant
from app.services.audit.service import audit_log

router = APIRouter(prefix='/portal', tags=['portal'])

_ALLOWED_AGENT_MODES = {'enabled', 'bypass', 'after_hours_only'}
_AGENT_MODE_AUDIT_ACTION = 'portal.agent_mode.updated'
_AGENT_MODE_RESOURCE_TYPE = 'portal_agent_mode'


def _default_agent_mode() -> PortalAgentModeResponse:
    return PortalAgentModeResponse(mode='enabled', effective_in_live_routing=False)


def _coerce_mode(value: str) -> str:
    normalized = (value or '').strip().lower()
    if normalized not in _ALLOWED_AGENT_MODES:
        raise HTTPException(
            status_code=400,
            detail=f'Invalid mode. Expected one of: {", ".join(sorted(_ALLOWED_AGENT_MODES))}',
        )
    return normalized


async def _latest_agent_mode_event(
    db: AsyncSession,
    *,
    tenant_id: str,
) -> AuditEvent | None:
    stmt = (
        select(AuditEvent)
        .where(
            AuditEvent.tenant_id == tenant_id,
            AuditEvent.action == _AGENT_MODE_AUDIT_ACTION,
            AuditEvent.resource_type == _AGENT_MODE_RESOURCE_TYPE,
        )
        .order_by(AuditEvent.created_at.desc())
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def _agent_mode_from_audit(
    db: AsyncSession,
    *,
    tenant_id: str,
) -> PortalAgentModeResponse:
    event = await _latest_agent_mode_event(db, tenant_id=tenant_id)
    if event is None:
        return _default_agent_mode()

    metadata = event.event_metadata or {}
    mode = metadata.get('mode') or ''
    if mode not in _ALLOWED_AGENT_MODES:
        return _default_agent_mode()

    updated_by_email: str | None = metadata.get('updated_by_email')
    if not updated_by_email and event.actor_user_id:
        user_stmt = select(User).where(User.id == event.actor_user_id)
        user = (await db.execute(user_stmt)).scalar_one_or_none()
        if user is not None:
            updated_by_email = user.email

    return PortalAgentModeResponse(
        mode=mode,
        fallback_destination=str(metadata.get('fallback_destination') or ''),
        reason=str(metadata.get('reason') or ''),
        updated_at=event.created_at,
        updated_by_user_id=str(event.actor_user_id) if event.actor_user_id else None,
        updated_by_email=updated_by_email,
        # Explicitly false until live routing reads this state in the call path.
        effective_in_live_routing=False,
    )


@router.get('/agent-mode', response_model=PortalAgentModeResponse)
async def get_agent_mode(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> PortalAgentModeResponse:
    return await _agent_mode_from_audit(db, tenant_id=current_user.tenant_id)


@router.put('/agent-mode', response_model=PortalAgentModeResponse)
async def put_agent_mode(
    payload: PortalAgentModeUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.owner, UserRole.admin)),
) -> PortalAgentModeResponse:
    mode = _coerce_mode(payload.mode)
    await audit_log(
        db,
        tenant_id=current_user.tenant_id,
        action=_AGENT_MODE_AUDIT_ACTION,
        resource_type=_AGENT_MODE_RESOURCE_TYPE,
        resource_id=f'tenant:{current_user.tenant_id}',
        actor_user_id=current_user.id,
        metadata={
            'mode': mode,
            'fallback_destination': payload.fallback_destination or '',
            'reason': payload.reason or '',
            'updated_by_email': current_user.email,
        },
    )
    await db.commit()
    return await _agent_mode_from_audit(db, tenant_id=current_user.tenant_id)


@router.get('/dashboard', response_model=PortalDashboardResponse)
async def portal_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> PortalDashboardResponse:
    analytics = await summary_for_tenant(db, current_user.tenant_id)
    recent_rows = (
        await db.execute(
            select(Call)
            .where(Call.tenant_id == current_user.tenant_id)
            .order_by(Call.started_at.desc())
            .limit(10)
        )
    ).scalars().all()
    recent_calls = [
        PortalDashboardRecentCall(
            id=str(call.id),
            started_at=call.started_at,
            status=call.status.value if hasattr(call.status, 'value') else str(call.status),
            direction=call.direction.value if hasattr(call.direction, 'value') else str(call.direction),
            outcome=call.outcome,
            from_number=call.from_number,
            to_number=call.to_number,
        )
        for call in recent_rows
    ]
    agent_mode = await _agent_mode_from_audit(db, tenant_id=current_user.tenant_id)
    return PortalDashboardResponse(
        analytics=analytics,
        agent_mode=agent_mode,
        recent_calls=recent_calls,
    )


@router.get('/business-profile', response_model=PortalBusinessProfileResponse)
async def portal_business_profile(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> PortalBusinessProfileResponse:
    tenant = (
        await db.execute(select(Tenant).where(Tenant.id == current_user.tenant_id))
    ).scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=404, detail='Tenant not found')

    tz_row = (
        await db.execute(
            select(BusinessHours.timezone)
            .where(BusinessHours.tenant_id == current_user.tenant_id)
            .limit(1)
        )
    ).first()
    timezone = tz_row[0] if tz_row else 'America/Indiana/Indianapolis'

    return PortalBusinessProfileResponse(
        legal_business_name=tenant.name,
        public_business_name=tenant.name,
        timezone=timezone,
    )


@router.get('/audit-log', response_model=PortalAuditLogResponse)
async def portal_audit_log(
    limit: int = Query(default=50, ge=1, le=200),
    action: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> PortalAuditLogResponse:
    stmt = select(AuditEvent).where(AuditEvent.tenant_id == current_user.tenant_id)
    if action:
        stmt = stmt.where(AuditEvent.action == action)
    stmt = stmt.order_by(AuditEvent.created_at.desc()).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()

    return PortalAuditLogResponse(
        entries=[
            PortalAuditLogEntry(
                id=str(row.id),
                created_at=row.created_at,
                action=row.action,
                resource_type=row.resource_type,
                resource_id=row.resource_id,
                actor_user_id=str(row.actor_user_id) if row.actor_user_id else None,
                metadata=row.event_metadata or {},
            )
            for row in rows
        ]
    )
