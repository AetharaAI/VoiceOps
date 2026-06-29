from typing import Any

from pydantic import BaseModel, Field


class AgentCreate(BaseModel):
    name: str
    persona: str
    script: str
    required_fields: dict[str, Any] = Field(default_factory=dict)
    tools_config: dict[str, Any] = Field(default_factory=dict)
    policy_config: dict[str, Any] = Field(default_factory=dict)
    workflow_dsl: dict[str, Any] = Field(default_factory=dict)


class AgentUpdateConfig(BaseModel):
    name: str | None = None
    persona: str | None = None
    script: str | None = None
    required_fields: dict[str, Any] | None = None
    tools_config: dict[str, Any] | None = None
    policy_config: dict[str, Any] | None = None
    workflow_dsl: dict[str, Any] | None = None


class AgentResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    persona: str
    script: str
    required_fields: dict[str, Any]
    tools_config: dict[str, Any]
    policy_config: dict[str, Any]
    workflow_dsl: dict[str, Any]


class TTSVoiceOption(BaseModel):
    id: str
    label: str
    gender: str
    style_tag: str
    family: str
    provider: str
    models: list[str] = Field(default_factory=list)
    reference_audio_path: str | None = None
    is_default: bool = False
    telephony_recommended: bool = False
    barge_in_quality: str = 'unverified'
    latency_profile: str = 'unknown'
    operator_note: str | None = None
