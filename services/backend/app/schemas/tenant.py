from pydantic import BaseModel, Field


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
