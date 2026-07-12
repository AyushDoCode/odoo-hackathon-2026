# AssetFlow Backend

AssetFlow is a FastAPI backend for building asset management and workflow automation features. The project is structured to support a clean API layer, typed configuration, database migrations, and testable application modules.

## Tech Stack

- FastAPI
- Uvicorn
- SQLAlchemy
- Alembic
- Pydantic Settings
- Pytest
- Black
- Ruff
- Mypy

## Project Structure

```text
assetflow_backend/
├── alembic/
├── app/
│   ├── api/
│   ├── core/
│   ├── database/
│   ├── middleware/
│   ├── modules/
│   ├── utils/
│   └── main.py
├── tests/
├── pyproject.toml
├── requirements.txt
└── README.md
```

## Setup Instructions

1. Create and activate a Python 3.12+ virtual environment.
2. Install the project with development tools:

	```bash
	pip install -e .[dev]
	```

3. Configure environment variables if needed by copying `.env.example` to `.env`.

## Run Commands

Start the API server in development:

```bash
uvicorn app.main:app --reload
```

Run the test suite:

```bash
pytest
```

Format the codebase:

```bash
black .
```

Lint with Ruff:

```bash
ruff check .
```

Run static typing checks:

```bash
mypy app tests
```

## API Documentation URL

When the server is running locally, interactive API documentation is available at:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Future Modules

- Authentication and authorization
- Asset inventory management
- Approval and workflow engine
- Reporting and analytics
- Audit logging
- Background jobs and scheduled tasks
- External integrations and webhooks
