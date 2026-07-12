from fastapi import FastAPI

import app.database.models_registry  # noqa: F401 - populate ORM mapper registry
from app.api import api_router


app = FastAPI(
	title="AssetFlow API",
	version="1.0.0",
	description="Enterprise Asset & Resource Management System",
)

app.include_router(api_router)


@app.get("/")
async def root() -> dict[str, str]:
	return {
		"status": "success",
		"message": "AssetFlow API is running",
	}


@app.get("/health")
async def health_check() -> dict[str, str]:
	return {"status": "healthy"}
