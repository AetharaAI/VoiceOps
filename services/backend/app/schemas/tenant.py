from pydantic import BaseModel, EmailStr, Field

from app.models.models import UserRole


class TenantCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    slug: str = Field(min_length=2, max_length=255)
    recording_enabled: bool = False
    pii_redaction_enabled: bool = True
    retention_days: int = 90


class TenantResponse(BaseModel):
    id: str
    name: str
    slug: str
    recording_enabled: bool
    pii_redaction_enabled: bool
    retention_days: int


class TenantBootstrapRequest(BaseModel):
    tenant_name: str = Field(min_length=2, max_length=255)
    owner_full_name: str = Field(min_length=2, max_length=255)
    owner_email: EmailStr
    tenant_slug: str | None = Field(default=None, min_length=2, max_length=255)
    owner_role: UserRole = UserRole.owner


class TenantBootstrapResponse(BaseModel):
    tenant_id: str
    tenant_name: str
    tenant_slug: str
    owner_user_id: str
    owner_email: EmailStr
    password_reset_token: str
    password_reset_expires_minutes: int
