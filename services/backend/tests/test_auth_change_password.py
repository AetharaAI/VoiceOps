import pytest
from fastapi import HTTPException

from app.api.deps import CurrentUser
from app.api.routes.auth import change_password, forgot_password, login, reset_password
from app.core.config import get_settings
from app.core.security import get_password_hash, verify_password
from app.models.models import User, UserRole
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    ResetPasswordRequest,
)


class _FakeResult:
    def __init__(self, user):
        self._user = user

    def scalar_one_or_none(self):
        return self._user


class _FakeDB:
    def __init__(self, user):
        self._user = user
        self.commit_called = False

    async def execute(self, stmt):  # noqa: ANN001 - AsyncSession compatibility
        _ = stmt
        return _FakeResult(self._user)

    def add(self, instance):  # noqa: ANN001 - AsyncSession compatibility
        _ = instance

    async def commit(self):
        self.commit_called = True


class _EmptyDB:
    async def execute(self, stmt):  # noqa: ANN001 - AsyncSession compatibility
        _ = stmt
        return _FakeResult(None)


def _current_user(user: User) -> CurrentUser:
    return CurrentUser(
        id=str(user.id),
        tenant_id=str(user.tenant_id),
        email=user.email,
        role=user.role,
    )


def _make_user() -> User:
    return User(
        tenant_id='00000000-0000-0000-0000-000000000001',
        email='owner@example.com',
        full_name='Owner User',
        role=UserRole.owner,
        hashed_password=get_password_hash('old-password-123'),
        is_active=True,
    )


@pytest.mark.asyncio
async def test_change_password_success_updates_hash():
    user = _make_user()
    db = _FakeDB(user)

    response = await change_password(
        payload=ChangePasswordRequest(
            current_password='old-password-123',
            new_password='new-password-456',
        ),
        current_user=_current_user(user),
        db=db,
    )

    assert response.ok is True
    assert db.commit_called is True
    assert verify_password('new-password-456', user.hashed_password) is True
    assert verify_password('old-password-123', user.hashed_password) is False


@pytest.mark.asyncio
async def test_change_password_rejects_bad_current_password():
    user = _make_user()
    db = _FakeDB(user)

    with pytest.raises(HTTPException) as exc:
        await change_password(
            payload=ChangePasswordRequest(
                current_password='wrong-password',
                new_password='new-password-456',
            ),
            current_user=_current_user(user),
            db=db,
        )

    assert exc.value.status_code == 401
    assert db.commit_called is False


@pytest.mark.asyncio
async def test_change_password_requires_new_password_to_differ():
    user = _make_user()
    db = _FakeDB(user)

    with pytest.raises(HTTPException) as exc:
        await change_password(
            payload=ChangePasswordRequest(
                current_password='old-password-123',
                new_password='old-password-123',
            ),
            current_user=_current_user(user),
            db=db,
        )

    assert exc.value.status_code == 400
    assert db.commit_called is False


@pytest.mark.asyncio
async def test_login_still_works_for_valid_credentials():
    user = _make_user()
    db = _FakeDB(user)

    response = await login(
        payload=LoginRequest(email=user.email, password='old-password-123'),
        db=db,
    )

    assert response.token_type == 'bearer'
    assert isinstance(response.access_token, str)
    assert len(response.access_token) > 20


@pytest.mark.asyncio
async def test_login_rejects_invalid_credentials():
    db = _EmptyDB()

    with pytest.raises(HTTPException) as exc:
        await login(
            payload=LoginRequest(email='owner@example.com', password='wrong-password'),
            db=db,
        )

    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_forgot_password_platform_admin_returns_token(monkeypatch):
    user = _make_user()
    db = _FakeDB(user)
    settings = get_settings()
    monkeypatch.setattr(settings, 'platform_admin_key', 'admin-secret')
    monkeypatch.setattr(settings, 'auth_password_reset_allow_debug_token_response', False)

    response = await forgot_password(
        payload=ForgotPasswordRequest(email=user.email),
        x_platform_admin_key='admin-secret',
        db=db,
    )

    assert response.ok is True
    assert isinstance(response.reset_token, str)
    assert len(response.reset_token) > 20
    assert db.commit_called is True


@pytest.mark.asyncio
async def test_reset_password_success_and_token_reuse_rejected(monkeypatch):
    user = _make_user()
    db = _FakeDB(user)
    settings = get_settings()
    monkeypatch.setattr(settings, 'platform_admin_key', 'admin-secret')
    monkeypatch.setattr(settings, 'auth_password_reset_allow_debug_token_response', False)

    forgot = await forgot_password(
        payload=ForgotPasswordRequest(email=user.email),
        x_platform_admin_key='admin-secret',
        db=db,
    )
    token = forgot.reset_token
    assert token is not None

    first = await reset_password(
        payload=ResetPasswordRequest(token=token, new_password='new-password-789'),
        db=db,
    )
    assert first.ok is True
    assert verify_password('new-password-789', user.hashed_password) is True
    assert verify_password('old-password-123', user.hashed_password) is False

    with pytest.raises(HTTPException) as exc:
        await reset_password(
            payload=ResetPasswordRequest(token=token, new_password='other-password-000'),
            db=db,
        )
    assert exc.value.status_code == 400
