# AssetFlow - Odoo Hackathon 2026

AssetFlow is an enterprise asset and resource management system built for the
Odoo Hackathon 2026. It brings asset registration, allocation, transfer,
resource booking, maintenance, audits, notifications, and reports into one
full-stack application.

The project is intentionally focused on operational asset workflows. It does
not include purchasing, invoicing, accounting, external authentication, hosted
analytics, email delivery, cloud storage, or background workers.

## Design

Figma design reference: [odoo design](https://www.figma.com/design/dCF62HroJcJkobjTF9sLQE/odoo-design?node-id=0-1&t=koth2t1r8psk9Zg9-1)

## Project links

- Design: [odoo design](https://www.figma.com/design/dCF62HroJcJkobjTF9sLQE/odoo-design?node-id=0-1&t=koth2t1r8psk9Zg9-1)
- Google Drive file: [shared project file](https://drive.google.com/file/d/1ldDjT4PMhk19dl23MNHtCwy3B8gqw3fd/view?usp=sharing)
- Short link: [project resource](https://bit.ly/4w1p8t9)

## Tech stack

- Backend: FastAPI, SQLAlchemy async, Alembic, Pydantic
- Database: MySQL 8 in Docker, with SQLite support useful for local tests
- Frontend: Static HTML, CSS, and vanilla JavaScript
- Auth: JWT access tokens
- Files: Local upload storage under `data/uploads`

`app/main.py` serves both the API and the frontend. API routes live under
`/api`, while the static frontend is mounted at `/`, so one backend process runs
the complete app.

## Setup

Python 3.12 or newer is required.

1. Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Install dependencies:

```powershell
pip install -e ".[dev]"
```

3. Create `.env`.

If `.env.example` is present, copy it:

```powershell
Copy-Item .env.example .env
```

Otherwise create `.env` with values like:

```env
DATABASE_URL=mysql+aiomysql://root:root@localhost:3307/assetflow
SECRET_KEY=replace-with-a-long-random-secret
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
PASSWORD_RESET_EXPIRE_MINUTES=15
CORS_ORIGINS=http://localhost:5173,http://localhost:3000,http://localhost:5500,http://127.0.0.1:5500,http://localhost:8080,null
UPLOAD_DIRECTORY=data/uploads
MAX_UPLOAD_BYTES=5000000
BOOTSTRAP_ADMIN_NAME=AssetFlow Admin
BOOTSTRAP_ADMIN_EMAIL=admin@assetflow.app
BOOTSTRAP_ADMIN_PASSWORD=replace-with-a-strong-password
```

4. Start MySQL:

```powershell
docker compose up -d mysql
```

5. Run migrations and create the first admin:

```powershell
alembic upgrade head
python -m app.scripts.bootstrap_admin
```

6. Start the app:

```powershell
uvicorn app.main:app --reload
```

Open:

- Home page: `http://localhost:8000/`
- Login page: `http://localhost:8000/login.html`
- App dashboard: `http://localhost:8000/dashboard.html`
- Swagger UI: `http://localhost:8000/docs`
- OpenAPI JSON: `http://localhost:8000/openapi.json`
- Health check: `http://localhost:8000/health`

## Docker setup

To run the complete app and MySQL together:

```powershell
docker compose up --build
```

The app container uses:

- `DATABASE_URL=mysql+aiomysql://root:root@mysql:3306/assetflow`
- local upload volume mounted at `/app/data/uploads`
- app port `8000`
- MySQL host port `3307`

## How it works

1. Users sign up as Employees or log in with an existing account.
2. Admins configure departments, categories, and employee roles.
3. Asset Managers register assets and mark selected assets as bookable shared resources.
4. Assets can be allocated to users or departments, transferred, returned, and checked in with condition notes.
5. Bookable assets can be reserved through the resource booking workflow.
6. Maintenance tickets move through approval, technician assignment, progress, and resolution.
7. Audit cycles verify asset condition and resolve missing or damaged items.
8. Notifications and the dashboard surface reminders, overdue returns, and recent activity.
9. Reports use real backend data for utilization, bookings by hour, maintenance frequency, idle assets, most-used assets, and watchlist assets.

The frontend calls `frontend/assets/api.js`, which prefixes requests with
`/api`, attaches the JWT bearer token, and redirects unauthenticated users to
`login.html`.

## Roles

| Role | Core permissions |
| --- | --- |
| Admin | Organization setup, employee role assignment, audit cycles, organization analytics |
| Asset Manager | Asset registration/allocation, transfer and return approval, maintenance approval, discrepancy resolution, reports |
| Department Head | Department-scoped assets, transfers, bookings, and audit visibility |
| Employee | Own allocated assets, bookings, maintenance requests, transfer/return requests, and notifications |

Signup always creates an `EMPLOYEE`. Roles can only be changed through the
Admin employee management workflow.

## Main workflows

### Organization setup

- `GET/POST/PATCH /api/departments`
- `GET/POST/PATCH /api/categories`
- `GET/PATCH /api/users`

Admin users manage departments, categories, activation, department assignment,
and role promotion.

### Assets and allocation

- Assets receive automatic `AF-0001` style tags.
- Search supports tag, serial number, QR code, category, status, department, and location.
- Allocation locks the asset row and rejects double allocation.
- Transfer and return requests require the correct approver before the asset state changes.

### Resource booking

- Only assets marked `is_bookable` can be booked.
- Booking overlap uses half-open intervals: `[start_time, end_time)`.
- Booking status is derived as `UPCOMING`, `ONGOING`, `COMPLETED`, or `CANCELLED`.
- Owners, Admins, Asset Managers, and responsible Department Heads can manage the relevant bookings.

### Maintenance

Maintenance follows this state machine:

```text
PENDING -> APPROVED/REJECTED -> TECHNICIAN_ASSIGNED -> IN_PROGRESS -> RESOLVED
```

Approving a request checks in any active allocation and moves the asset to
Maintenance. Resolving the request returns the asset to Available.

### Audit

Admins create scoped audit cycles and assign auditors. Missing or damaged
discrepancies require Asset Manager/Admin resolution before the audit can close.
Closing an audit locks the cycle and updates affected asset states.

### Notifications and activity

- `GET /api/activity/notifications` returns personal notifications and materializes booking reminders and overdue-return alerts.
- `POST /api/activity/notifications/{id}/read` marks a notification as read.
- `GET /api/activity/logs` returns the privileged organization audit log.

## Verification

Recommended checks:

```powershell
pytest -q
python -m compileall -q app tests
ruff check app tests
mypy app tests
```

The integration tests use `DATABASE_URL` from `.env`. Never point tests at a
production database.
