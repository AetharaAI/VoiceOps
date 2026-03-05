from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Call, CallStatus
from app.schemas.analytics import AnalyticsSummary


async def summary_for_tenant(db: AsyncSession, tenant_id: str) -> AnalyticsSummary:
    total_calls = (
        await db.execute(select(func.count()).select_from(Call).where(Call.tenant_id == tenant_id))
    ).scalar_one()

    completed_calls = (
        await db.execute(
            select(func.count())
            .select_from(Call)
            .where(Call.tenant_id == tenant_id, Call.status == CallStatus.completed)
        )
    ).scalar_one()

    escalated_calls = (
        await db.execute(
            select(func.count())
            .select_from(Call)
            .where(Call.tenant_id == tenant_id, Call.status == CallStatus.escalated)
        )
    ).scalar_one()

    booked_calls = (
        await db.execute(
            select(func.count())
            .select_from(Call)
            .where(Call.tenant_id == tenant_id, Call.outcome == 'booked')
        )
    ).scalar_one()

    duration_rows = (
        await db.execute(
            select(Call.started_at, Call.ended_at).where(
                Call.tenant_id == tenant_id, Call.ended_at.is_not(None), Call.started_at.is_not(None)
            )
        )
    ).all()

    avg_handle_seconds = 0.0
    if duration_rows:
        seconds = []
        for started_at, ended_at in duration_rows:
            if isinstance(started_at, datetime) and isinstance(ended_at, datetime):
                seconds.append((ended_at - started_at).total_seconds())
        if seconds:
            avg_handle_seconds = sum(seconds) / len(seconds)

    containment_rate = (completed_calls / total_calls) if total_calls else 0.0
    booking_rate = (booked_calls / total_calls) if total_calls else 0.0
    escalation_rate = (escalated_calls / total_calls) if total_calls else 0.0

    return AnalyticsSummary(
        total_calls=total_calls,
        completed_calls=completed_calls,
        containment_rate=round(containment_rate, 4),
        booking_rate=round(booking_rate, 4),
        avg_handle_seconds=round(avg_handle_seconds, 2),
        escalation_rate=round(escalation_rate, 4),
    )
