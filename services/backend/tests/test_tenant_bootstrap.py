import uuid

import pytest

from app.api.routes.tenants import _slugify, admin_tenant_bootstrap
from app.core.config import get_settings
from app.core.security import decode_token
from app.models.models import Tenant, User
from app.schemas.tenant import TenantBootstrapRequest


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _FakeDB:
    def __init__(self):
        self.commit_called = False
        self._tenant_slug_attempts = 0
        self.added = []

    async def execute(self, stmt):  # noqa: ANN001
        _ = stmt
        self._tenant_slug_attempts += 1
        if self._tenant_slug_attempts == 1:
            existing = Tenant(name='Existing', slug='blues-electric')
            existing.id = uuid.uuid4()
            return _FakeResult(existing)
        return _FakeResult(None)

    def add(self, instance):  # noqa: ANN001
        self.added.append(instance)

    async def flush(self):
        for item in self.added:
            if getattr(item, 'id', None) is None:
                item.id = uuid.uuid4()

    async def commit(self):
        self.commit_called = True


def test_slugify_handles_symbols_and_collapses_dashes():
    assert _slugify(" Blue's   Electric !! ") == 'blue-s-electric'


@pytest.mark.asyncio
async def test_admin_tenant_bootstrap_creates_owner_and_reset_token():
    db = _FakeDB()
    settings = get_settings()
    settings.auth_password_reset_token_minutes = 30

    response = await admin_tenant_bootstrap(
        payload=TenantBootstrapRequest(
            tenant_name="Blue's Electric",
            owner_full_name='Blue Owner',
            owner_email='Owner@Example.com',
        ),
        db=db,
    )

    assert response.tenant_slug == 'blue-s-electric-2'
    assert response.owner_email == 'owner@example.com'
    assert response.password_reset_expires_minutes == 30
    assert db.commit_called is True

    claims = decode_token(response.password_reset_token)
    assert claims['scope'] == 'password_reset'
    assert claims['email'] == 'owner@example.com'
    assert claims['tenant_id'] == response.tenant_id
    assert claims['sub'] == response.owner_user_id

    assert any(isinstance(item, Tenant) for item in db.added)
    assert any(isinstance(item, User) for item in db.added)
