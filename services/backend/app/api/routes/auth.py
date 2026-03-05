from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user, require_platform_admin
from app.core.security import create_access_token, get_password_hash, verify_password
from app.db.session import get_db
from app.models.models import Tenant, User, UserRole
from app.schemas.auth import BootstrapRequest, LoginRequest, TokenResponse, UserResponse

router = APIRouter(prefix='/auth', tags=['auth'])


@router.post('/bootstrap', response_model=TokenResponse, dependencies=[Depends(require_platform_admin)])
async def bootstrap(payload: BootstrapRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    existing_tenant = (
        await db.execute(select(Tenant).where(Tenant.slug == payload.tenant_slug))
    ).scalar_one_or_none()
    if existing_tenant:
        raise HTTPException(status_code=409, detail='Tenant slug already exists')

    tenant = Tenant(name=payload.tenant_name, slug=payload.tenant_slug)
    db.add(tenant)
    await db.flush()

    user = User(
        tenant_id=tenant.id,
        email=payload.email,
        full_name=payload.full_name,
        role=UserRole.owner,
        hashed_password=get_password_hash(payload.password),
    )
    db.add(user)
    await db.commit()

    token = create_access_token(subject=str(user.id), tenant_id=str(tenant.id), role=user.role.value)
    return TokenResponse(access_token=token)


@router.post('/login', response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    user = (await db.execute(select(User).where(User.email == payload.email))).scalar_one_or_none()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid credentials')

    token = create_access_token(
        subject=str(user.id),
        tenant_id=str(user.tenant_id),
        role=user.role.value,
    )
    return TokenResponse(access_token=token)


@router.get('/me', response_model=UserResponse)
async def me(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    user = (await db.execute(select(User).where(User.id == current_user.id))).scalar_one()
    return UserResponse(
        id=str(user.id),
        tenant_id=str(user.tenant_id),
        email=user.email,
        full_name=user.full_name,
        role=user.role,
    )
