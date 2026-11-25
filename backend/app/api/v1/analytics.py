"""Analytics endpoints (admin insights over support activity)."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import AdminUser, DbSession
from app.schemas.analytics import AnalyticsOverview
from app.services import analytics_service

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview", response_model=AnalyticsOverview)
async def get_overview(db: DbSession, _: AdminUser) -> AnalyticsOverview:
    """Workspace-wide AI support metrics (admin only)."""
    return await analytics_service.overview(db)