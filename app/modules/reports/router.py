from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_role
from app.database.session import get_db
from app.modules.reports.schemas import ReportsSummary
from app.modules.reports.service import ReportsService
from app.modules.users.models import User, UserRole

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get(
    "/summary",
    response_model=ReportsSummary,
    dependencies=[Depends(require_role(UserRole.ADMIN, UserRole.ASSET_MANAGER))],
)
async def summary(
    session: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> ReportsSummary:
    service = ReportsService(session)
    return await service.summary()


@router.get(
    "/export",
    dependencies=[Depends(require_role(UserRole.ADMIN, UserRole.ASSET_MANAGER))],
)
async def export_csv(
    session: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    service = ReportsService(session)
    report = await service.summary()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["section", "field1", "field2", "field3", "value"])
    for utilization in report.utilization_by_department:
        writer.writerow(["utilization_by_department", utilization.department_name, "", "", utilization.active_allocation_count])
    for used_asset in report.most_used_assets:
        writer.writerow(["most_used_assets", used_asset.asset_tag, used_asset.asset_name, "", used_asset.usage_count])
    for idle_asset in report.idle_assets:
        writer.writerow(["idle_assets", idle_asset.asset_tag, idle_asset.asset_name, "", idle_asset.usage_count])
    for frequency in report.maintenance_frequency:
        writer.writerow(["maintenance_frequency", frequency.asset_tag, frequency.category_name, "", frequency.request_count])
    for due_asset in report.due_for_maintenance_or_retirement:
        writer.writerow(["due_for_maintenance_or_retirement", due_asset.asset_tag, due_asset.asset_name, due_asset.reason, ""])
    for bucket in report.booking_heatmap:
        writer.writerow(["booking_heatmap", bucket.hour_of_day, "", "", bucket.booking_count])

    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=assetflow_report.csv"},
    )
