from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.db.session import get_db
from app.schemas.analytics import AnalyticsSummary
from app.services.analytics.service import summary_for_tenant

router = APIRouter(tags=['analytics'])


@router.get('/analytics/summary', response_model=AnalyticsSummary)
async def analytics_summary(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> AnalyticsSummary:
    return await summary_for_tenant(db, current_user.tenant_id)
