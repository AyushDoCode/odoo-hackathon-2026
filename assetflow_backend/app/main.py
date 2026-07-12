from fastapi import FastAPI


app = FastAPI(
	title="AssetFlow API",
	version="1.0.0",
	description="Enterprise Asset & Resource Management System",
)


@app.get("/")
async def root() -> dict[str, str]:
	return {
		"status": "success",
		"message": "AssetFlow API is running",
	}


@app.get("/health")
async def health_check() -> dict[str, str]:
	return {"status": "healthy"}
