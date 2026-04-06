from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.analytics import AnalyticsSummary


class PortalAgentModeResponse(BaseModel):
    mode: str = Field(description='enabled | bypass | after_hours_only')
    fallback_destination: str = ''
    reason: str = ''
    updated_at: datetime | None = None
    updated_by_user_id: str | None = None
    updated_by_email: str | None = None
    effective_in_live_routing: bool = False


class PortalAgentModeUpdateRequest(BaseModel):
    mode: str = Field(description='enabled | bypass | after_hours_only')
    fallback_destination: str = ''
    reason: str = ''


class PortalDashboardRecentCall(BaseModel):
    id: str
    started_at: datetime | None = None
    status: str
    direction: str
    outcome: str | None = None
    from_number: str
    to_number: str


class PortalDashboardResponse(BaseModel):
    analytics: AnalyticsSummary
    agent_mode: PortalAgentModeResponse
    recent_calls: list[PortalDashboardRecentCall]


class PortalBusinessProfileResponse(BaseModel):
    legal_business_name: str
    public_business_name: str
    website: str = ''
    timezone: str
    service_area_summary: str = ''
    primary_contact_name: str = ''
    primary_contact_email: str = ''
    primary_contact_phone: str = ''
    after_hours_instructions: str = ''


class PortalAuditLogEntry(BaseModel):
    id: str
    created_at: datetime | None
    action: str
    resource_type: str
    resource_id: str
    actor_user_id: str | None
    metadata: dict


class PortalAuditLogResponse(BaseModel):
    entries: list[PortalAuditLogEntry]
