from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FormCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    form_schema: dict[str, Any] = Field(alias='schema')
    workflow_config: dict[str, Any] = Field(default_factory=dict)


class FormSubmitRequest(BaseModel):
    payload: dict[str, Any]


class FormResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    tenant_id: str
    name: str
    form_schema: dict[str, Any] = Field(alias='schema')
    workflow_config: dict[str, Any]


class FormSubmissionResponse(BaseModel):
    id: str
    form_id: str
    tenant_id: str
    payload: dict[str, Any]
    linked_call_id: str | None
    created_at: datetime
