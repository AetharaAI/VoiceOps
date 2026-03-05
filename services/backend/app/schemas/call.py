from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.models import CallDirection, CallStatus


class OutboundCallRequest(BaseModel):
    tenant_id: str
    to_number: str
    agent_id: str
    campaign_id: str | None = None
    context_payload: dict[str, Any] = Field(default_factory=dict)


class CallResponse(BaseModel):
    id: str
    tenant_id: str
    agent_id: str | None
    external_call_id: str | None
    direction: CallDirection
    status: CallStatus
    from_number: str
    to_number: str
    campaign_id: str | None
    context_payload: dict[str, Any]
    outcome: str | None
    escalation_reason: str | None
    started_at: datetime | None
    ended_at: datetime | None


class TranscriptSegmentResponse(BaseModel):
    id: str
    speaker: str
    text: str
    is_final: bool
    confidence: float | None
    started_ms: int | None
    ended_ms: int | None


class CallDetailResponse(CallResponse):
    transcript: list[TranscriptSegmentResponse]
