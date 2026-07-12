from fastapi import APIRouter

from app.modules.allocations.router import router as allocations_router
from app.modules.assets.router import router as assets_router
from app.modules.auth.router import router as auth_router
from app.modules.bookings.router import router as bookings_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(assets_router)
api_router.include_router(allocations_router)
api_router.include_router(bookings_router)
