from pydantic import BaseModel


class AnalyticsSummary(BaseModel):
    total_calls: int
    completed_calls: int
    containment_rate: float
    booking_rate: float
    avg_handle_seconds: float
    escalation_rate: float
