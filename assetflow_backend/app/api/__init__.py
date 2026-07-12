from fastapi import APIRouter

from app.modules.allocations.router import router as allocations_router
from app.modules.assets.router import router as assets_router
from app.modules.auth.router import router as auth_router
from app.modules.bookings.router import router as bookings_router
from app.modules.categories.router import router as categories_router
from app.modules.departments.router import router as departments_router
from app.modules.activity.router import router as activity_router
from app.modules.audit.router import router as audit_router
from app.modules.dashboard.router import router as dashboard_router
from app.modules.maintenance.router import router as maintenance_router
from app.modules.reports.router import router as reports_router
from app.modules.users.router import router as users_router
from app.modules.uploads.router import router as uploads_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(departments_router)
api_router.include_router(categories_router)
api_router.include_router(users_router)
api_router.include_router(uploads_router)
api_router.include_router(assets_router)
api_router.include_router(allocations_router)
api_router.include_router(bookings_router)
api_router.include_router(maintenance_router)
api_router.include_router(audit_router)
api_router.include_router(activity_router)
api_router.include_router(dashboard_router)
api_router.include_router(reports_router)
