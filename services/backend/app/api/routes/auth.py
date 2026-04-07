import asyncio
import logging
import smtplib
from email.message import EmailMessage
from urllib.parse import quote

from fastapi import APIRouter, Depends, Header, HTTPException, status
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user, require_platform_admin
from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    create_password_reset_token,
    decode_token,
    get_password_hash,
    password_fingerprint,
    verify_password,
)
from app.db.session import get_db
from app.models.models import AuditEvent, Tenant, User, UserRole
from app.schemas.auth import (
    BootstrapRequest,
    ChangePasswordRequest,
    ChangePasswordResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    ResetPasswordRequest,
    ResetPasswordResponse,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix='/auth', tags=['auth'])
logger = logging.getLogger(__name__)


def _build_reset_link(token: str) -> str:
    settings = get_settings()
    base = settings.auth_password_reset_url_base.strip()
    if not base:
        return ''
    delimiter = '&' if '?' in base else '?'
    return f'{base}{delimiter}token={quote(token, safe="")}'


def _send_password_reset_email(*, to_email: str, reset_link: str) -> None:
    settings = get_settings()

    message = EmailMessage()
    message['Subject'] = 'Reset your Aether VoiceOps password'
    message['From'] = settings.smtp_from_email
    message['To'] = to_email
    message.set_content(
        (
            'A password reset was requested for your account.\n\n'
            f'Use this secure link to reset your password:\n{reset_link}\n\n'
            'If you did not request this, you can ignore this message.'
        )
    )

    if settings.smtp_use_ssl:
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)
        return

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)


async def _deliver_password_reset_email(*, to_email: str, token: str) -> bool:
    settings = get_settings()
    if not settings.smtp_host or not settings.smtp_from_email:
        return False
    reset_link = _build_reset_link(token)
    if not reset_link:
        return False
    try:
        await asyncio.to_thread(_send_password_reset_email, to_email=to_email, reset_link=reset_link)
        return True
    except Exception:
        logger.exception('auth.password_reset.email_send_failed', extra={'email': to_email})
        return False


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


@router.post('/change-password', response_model=ChangePasswordResponse)
async def change_password(
    payload: ChangePasswordRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChangePasswordResponse:
    user = (await db.execute(select(User).where(User.id == current_user.id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')

    if not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Current password is incorrect')

    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='New password must be different')

    user.hashed_password = get_password_hash(payload.new_password)
    await db.commit()
    return ChangePasswordResponse()


@router.post('/forgot-password', response_model=ForgotPasswordResponse)
async def forgot_password(
    payload: ForgotPasswordRequest,
    x_platform_admin_key: str = Header(default=''),
    db: AsyncSession = Depends(get_db),
) -> ForgotPasswordResponse:
    settings = get_settings()
    response = ForgotPasswordResponse()
    user = (await db.execute(select(User).where(User.email == payload.email))).scalar_one_or_none()
    if not user or not user.is_active:
        return response

    token = create_password_reset_token(
        subject=str(user.id),
        tenant_id=str(user.tenant_id),
        email=user.email,
        password_fingerprint_value=password_fingerprint(user.hashed_password),
        expires_minutes=settings.auth_password_reset_token_minutes,
    )

    db.add(
        AuditEvent(
            tenant_id=user.tenant_id,
            actor_user_id=None,
            action='auth.password_reset_requested',
            resource_type='user',
            resource_id=str(user.id),
            event_metadata={'email': user.email},
        )
    )
    await db.commit()

    is_platform_admin = bool(x_platform_admin_key) and x_platform_admin_key == settings.platform_admin_key
    if is_platform_admin or settings.auth_password_reset_allow_debug_token_response:
        response.reset_token = token
        return response

    sent = await _deliver_password_reset_email(to_email=user.email, token=token)
    if not sent:
        logger.warning(
            'auth.password_reset.delivery_unconfigured_or_failed',
            extra={'email': user.email},
        )
    return response


@router.post('/reset-password', response_model=ResetPasswordResponse)
async def reset_password(
    payload: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> ResetPasswordResponse:
    try:
        claims = decode_token(payload.token)
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid or expired reset token') from exc

    if claims.get('scope') != 'password_reset':
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid reset token scope')

    user_id = claims.get('sub')
    token_tenant_id = claims.get('tenant_id')
    token_email = claims.get('email')
    token_pwdv = claims.get('pwdv')
    if not user_id or not token_tenant_id or not token_email or not token_pwdv:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Malformed reset token')

    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid reset token')

    if str(user.tenant_id) != str(token_tenant_id) or user.email.lower() != str(token_email).lower():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid reset token')

    if password_fingerprint(user.hashed_password) != token_pwdv:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Reset token is no longer valid',
        )

    if verify_password(payload.new_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='New password must be different',
        )

    user.hashed_password = get_password_hash(payload.new_password)
    db.add(
        AuditEvent(
            tenant_id=user.tenant_id,
            actor_user_id=user.id,
            action='auth.password_reset_completed',
            resource_type='user',
            resource_id=str(user.id),
            event_metadata={'email': user.email},
        )
    )
    await db.commit()
    return ResetPasswordResponse()
