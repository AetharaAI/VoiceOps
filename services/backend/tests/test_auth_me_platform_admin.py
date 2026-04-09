import uuid

import pytest

from app.api.deps import CurrentUser
from app.api.routes.auth import me
from app.models.models import User, UserRole


class _FakeResult:
    def __init__(self, user: User):
        self._user = user

    def scalar_one(self):
        return self._user


class _FakeDB:
    def __init__(self, user: User):
        self._user = user

    async def execute(self, stmt):  # noqa: ANN001
        _ = stmt
        return _FakeResult(self._user)


def _make_user(*, is_platform_admin: bool) -> User:
    user = User(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        email='ops@example.com',
        full_name='Ops User',
        role=UserRole.owner,
        hashed_password='hash',
        is_active=True,
        is_platform_admin=is_platform_admin,
    )
    return user


@pytest.mark.asyncio
async def test_auth_me_includes_platform_admin_true():
    user = _make_user(is_platform_admin=True)
    current = CurrentUser(
        id=str(user.id),
        tenant_id=str(user.tenant_id),
        email=user.email,
        role=user.role,
        is_platform_admin=True,
    )
    response = await me(current_user=current, db=_FakeDB(user))
    assert response.is_platform_admin is True
    assert response.role == UserRole.owner


@pytest.mark.asyncio
async def test_auth_me_includes_platform_admin_false():
    user = _make_user(is_platform_admin=False)
    current = CurrentUser(
        id=str(user.id),
        tenant_id=str(user.tenant_id),
        email=user.email,
        role=user.role,
        is_platform_admin=False,
    )
    response = await me(current_user=current, db=_FakeDB(user))
    assert response.is_platform_admin is False
    assert response.role == UserRole.owner
