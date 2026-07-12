import os
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

app.include_router(api_router)


@app.get("/api")
async def root() -> dict[str, str]:
	return {
		"status": "success",
		"message": "AssetFlow API is running",
	}


@app.get("/health")
async def health_check() -> dict[str, str]:
	return {"status": "healthy"}

# Mount the frontend directory (the root of the project)
frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
