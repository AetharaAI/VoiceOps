from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user, require_platform_admin
from app.db.session import get_db
from app.models.models import Tenant
from app.schemas.tenant import TenantCreate, TenantResponse

router = APIRouter(tags=['tenants'])


@router.post('/tenants', response_model=TenantResponse, dependencies=[Depends(require_platform_admin)])
async def create_tenant(payload: TenantCreate, db: AsyncSession = Depends(get_db)) -> TenantResponse:
    exists = (await db.execute(select(Tenant).where(Tenant.slug == payload.slug))).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail='Tenant slug already exists')

    tenant = Tenant(
        name=payload.name,
        slug=payload.slug,
        recording_enabled=payload.recording_enabled,
        pii_redaction_enabled=payload.pii_redaction_enabled,
        retention_days=payload.retention_days,
    )
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)

    return TenantResponse(
        id=str(tenant.id),
        name=tenant.name,
        slug=tenant.slug,
        recording_enabled=tenant.recording_enabled,
        pii_redaction_enabled=tenant.pii_redaction_enabled,
        retention_days=tenant.retention_days,
    )


@router.get('/tenants/me', response_model=TenantResponse)
async def tenant_me(
    current_user: CurrentUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> TenantResponse:
    tenant = (await db.execute(select(Tenant).where(Tenant.id == current_user.tenant_id))).scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail='Tenant not found')
    return TenantResponse(
        id=str(tenant.id),
        name=tenant.name,
        slug=tenant.slug,
        recording_enabled=tenant.recording_enabled,
        pii_redaction_enabled=tenant.pii_redaction_enabled,
        retention_days=tenant.retention_days,
    )
