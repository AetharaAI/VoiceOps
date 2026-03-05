from pydantic import BaseModel


class PhoneNumberCreate(BaseModel):
    phone_number: str
    provider: str = 'twilio'
    agent_id: str | None = None


class PhoneNumberResponse(BaseModel):
    id: str
    phone_number: str
    provider: str
    agent_id: str | None


class BusinessHourEntry(BaseModel):
    day_of_week: int
    start_time: str
    end_time: str
    timezone: str = 'America/Indiana/Indianapolis'


class RoutingRuleCreate(BaseModel):
    name: str
    priority: int = 100
    rule_config: dict
    target_agent_id: str | None = None


class RoutingRuleResponse(BaseModel):
    id: str
    name: str
    priority: int
    rule_config: dict
    target_agent_id: str | None
