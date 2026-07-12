from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import app.database.models_registry as _models_registry  # noqa: F401
from app.api import api_router
from app.core.config import settings

app = FastAPI(
	title="AssetFlow API",
	version="1.0.0",
	description="Enterprise Asset & Resource Management System",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Every API route lives under /api -- this is what keeps them from colliding with
# the frontend's own top-level paths (e.g. the frontend's static "assets/" folder
# vs. this API's "assets" resource).
app.include_router(api_router, prefix="/api")


@app.get("/api")
async def api_root() -> dict[str, str]:
	return {
		"status": "success",
		"message": "AssetFlow API is running",
	}


@app.get("/health")
async def health_check() -> dict[str, str]:
	return {"status": "healthy"}


# Serves the static frontend (login page, dashboard, etc.) from the same process,
# so the whole app runs from a single `uvicorn app.main:app` command. This must be
# mounted last: Starlette checks routes in registration order, so the routes above
# (including the /api/* routers) are always matched first, and this mount only
# catches whatever's left. html=True makes "/" resolve to frontend/index.html and
# lets a request for "/dashboard.html" resolve to that file directly.
_frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/", StaticFiles(directory=_frontend_dir, html=True), name="frontend")
