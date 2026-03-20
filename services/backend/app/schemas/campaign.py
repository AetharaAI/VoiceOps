from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class OutboundCampaignCreate(BaseModel):
    name: str
    agent_id: str | None = None
    caller_id_number: str | None = None
    lead_source: str | None = None
    objective: str
    opening_line: str
    qualification_fields: dict[str, Any] = Field(default_factory=dict)
    objection_guidance: str | None = None
    booking_target: str | None = None
    retry_rules: dict[str, Any] = Field(default_factory=dict)
    voicemail_config: dict[str, Any] = Field(default_factory=dict)
    handoff_rules: dict[str, Any] = Field(default_factory=dict)
    crm_mapping: dict[str, Any] = Field(default_factory=dict)
    llm_config: dict[str, Any] = Field(default_factory=dict)
    tts_config: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class OutboundCampaignUpdate(BaseModel):
    name: str | None = None
    agent_id: str | None = None
    caller_id_number: str | None = None
    lead_source: str | None = None
    objective: str | None = None
    opening_line: str | None = None
    qualification_fields: dict[str, Any] | None = None
    objection_guidance: str | None = None
    booking_target: str | None = None
    retry_rules: dict[str, Any] | None = None
    voicemail_config: dict[str, Any] | None = None
    handoff_rules: dict[str, Any] | None = None
    crm_mapping: dict[str, Any] | None = None
    llm_config: dict[str, Any] | None = None
    tts_config: dict[str, Any] | None = None
    is_active: bool | None = None


class OutboundCampaignResponse(BaseModel):
    id: str
    tenant_id: str
    agent_id: str | None
    name: str
    caller_id_number: str | None
    lead_source: str | None
    objective: str
    opening_line: str
    qualification_fields: dict[str, Any]
    objection_guidance: str | None
    booking_target: str | None
    retry_rules: dict[str, Any]
    voicemail_config: dict[str, Any]
    handoff_rules: dict[str, Any]
    crm_mapping: dict[str, Any]
    llm_config: dict[str, Any]
    tts_config: dict[str, Any]
    is_active: bool
    created_at: datetime | None
    updated_at: datetime | None
