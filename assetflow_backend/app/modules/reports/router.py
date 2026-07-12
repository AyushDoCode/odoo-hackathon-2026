from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.database.session import get_db
from app.modules.reports.schemas import ReportsSummary
from app.modules.reports.service import ReportsService
from app.modules.users.models import User

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/summary", response_model=ReportsSummary)
async def summary(
    session: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> ReportsSummary:
    service = ReportsService(session)
    return await service.summary()


@router.get("/export")
async def export_csv(
    session: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    service = ReportsService(session)
    report = await service.summary()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["section", "field1", "field2", "field3", "value"])
    for row in report.utilization_by_department:
        writer.writerow(["utilization_by_department", row.department_name, "", "", row.active_allocation_count])
    for row in report.most_used_assets:
        writer.writerow(["most_used_assets", row.asset_tag, row.asset_name, "", row.usage_count])
    for row in report.idle_assets:
        writer.writerow(["idle_assets", row.asset_tag, row.asset_name, "", row.usage_count])
    for row in report.maintenance_frequency:
        writer.writerow(["maintenance_frequency", row.asset_tag, row.category_name, "", row.request_count])
    for row in report.due_for_maintenance_or_retirement:
        writer.writerow(["due_for_maintenance_or_retirement", row.asset_tag, row.asset_name, row.reason, ""])
    for row in report.booking_heatmap:
        writer.writerow(["booking_heatmap", row.hour_of_day, "", "", row.booking_count])

    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=assetflow_report.csv"},
    )
