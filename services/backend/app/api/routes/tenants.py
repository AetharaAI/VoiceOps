import re
import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user, require_platform_admin
from app.core.config import get_settings
from app.core.security import create_password_reset_token, get_password_hash, password_fingerprint
from app.db.session import get_db
from app.models.models import Tenant, User
from app.schemas.tenant import (
    TenantBootstrapRequest,
    TenantBootstrapResponse,
    TenantCreate,
    TenantResponse,
)

router = APIRouter(tags=['tenants'])


def _slugify(value: str) -> str:
    normalized = re.sub(r'[^a-zA-Z0-9]+', '-', value.strip().lower()).strip('-')
    normalized = re.sub(r'-{2,}', '-', normalized)
    if len(normalized) < 2:
        return 'tenant'
    return normalized[:255]


async def _next_available_slug(db: AsyncSession, desired: str) -> str:
    base = _slugify(desired)
    candidate = base
    suffix = 2
    while True:
        exists = (await db.execute(select(Tenant).where(Tenant.slug == candidate))).scalar_one_or_none()
        if not exists:
            return candidate
        candidate = f'{base}-{suffix}'
        suffix += 1


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


@router.post(
    '/admin/tenant-bootstrap',
    response_model=TenantBootstrapResponse,
    dependencies=[Depends(require_platform_admin)],
)
async def admin_tenant_bootstrap(
    payload: TenantBootstrapRequest,
    db: AsyncSession = Depends(get_db),
) -> TenantBootstrapResponse:
    settings = get_settings()
    requested_slug = payload.tenant_slug or payload.tenant_name
    tenant_slug = await _next_available_slug(db, requested_slug)

    tenant = Tenant(name=payload.tenant_name, slug=tenant_slug)
    db.add(tenant)
    await db.flush()

    temp_password = secrets.token_urlsafe(24)
    owner = User(
        tenant_id=tenant.id,
        email=payload.owner_email.lower(),
        full_name=payload.owner_full_name,
        role=payload.owner_role,
        hashed_password=get_password_hash(temp_password),
        is_active=True,
    )
    db.add(owner)
    await db.flush()

    reset_token = create_password_reset_token(
        subject=str(owner.id),
        tenant_id=str(tenant.id),
        email=owner.email,
        password_fingerprint_value=password_fingerprint(owner.hashed_password),
        expires_minutes=settings.auth_password_reset_token_minutes,
    )
    await db.commit()

    return TenantBootstrapResponse(
        tenant_id=str(tenant.id),
        tenant_name=tenant.name,
        tenant_slug=tenant.slug,
        owner_user_id=str(owner.id),
        owner_email=owner.email,
        password_reset_token=reset_token,
        password_reset_expires_minutes=settings.auth_password_reset_token_minutes,
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
