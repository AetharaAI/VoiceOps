import pytest
from fastapi import HTTPException

from app.api.deps import CurrentUser
from app.api.routes.auth import change_password, login
from app.core.security import get_password_hash, verify_password
from app.models.models import User, UserRole
from app.schemas.auth import ChangePasswordRequest, LoginRequest


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
