# NearFix Backend

FastAPI backend for NearFix using a monolithic architecture, MySQL, SQLAlchemy, Alembic, and JWT authentication.

## Local Python Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

## Docker Setup

```powershell
docker compose up --build
```

FastAPI docs will be available at `http://localhost:8000/docs`.
MySQL is exposed on host port `3307` and container port `3306`.

## Auth Routes

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `POST /api/v1/auth/logout`
- `POST /api/v1/customer/register`
- `POST /api/v1/customer/login`
- `GET /api/v1/customer/me`
- `POST /api/v1/provider/register`
- `POST /api/v1/provider/login`
- `GET /api/v1/provider/me`
- `GET /api/v1/admin/providers/pending`
- `PATCH /api/v1/admin/providers/{id}/verification-status`
- `POST /api/v1/admin/login`
- `GET /api/v1/admin/summary`
- `GET /api/v1/admin/providers`
- `GET /api/v1/admin/provider-document-change-requests`
- `GET /api/v1/admin/customers`
- `GET /api/v1/admin/bookings`
- `GET /api/v1/admin/banners`
- `GET /api/v1/admin/services`

## Create Admin

```powershell
python scripts/create_admin.py --phone 9999999999 --password Test1234 --name "Admin"
```

## Health Routes

- `GET /api/v1/health`
- `GET /api/v1/health/db`
