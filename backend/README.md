# Nyx

**Finance Operations & Invoice Reconciliation Platform**

A production-oriented backend built with FastAPI, PostgreSQL, Redis, and RQ — designed for invoice lifecycle management, OCR extraction, and automated reconciliation.

---

## Architecture

```
nyx/
├── app/
│   ├── api/v1/         # Route handlers (auth, invoices, vendors, reconciliation, dashboard, audit)
│   ├── models/         # SQLAlchemy ORM models
│   ├── schemas/        # Pydantic request/response schemas
│   ├── services/       # Business logic layer
│   ├── repositories/   # Data access layer (repository pattern)
│   ├── workers/        # RQ background job handlers
│   ├── core/           # Security, exceptions, logging, middleware
│   ├── config.py       # Pydantic Settings (env-driven)
│   ├── database.py     # SQLAlchemy engine + session
│   ├── dependencies.py # FastAPI dependency injection
│   └── main.py         # FastAPI application entry
├── alembic/            # Database migrations
├── docker/             # Dockerfiles (API + Worker)
├── tests/              # pytest test suite
├── docker-compose.yml
└── docker-compose.prod.yml
```

### Key Design Decisions

| Concern | Approach |
|---|---|
| Architecture | Modular monolith — all features in one deployable unit |
| Background jobs | Redis + RQ (no Kafka/Celery complexity) |
| Auth | Stateless JWT (access + refresh tokens) |
| File storage | Local or S3-compatible (swap via `STORAGE_BACKEND` env var) |
| OCR | pytesseract + pdf2image — runs in worker process |
| Idempotency | SHA-256 checksum prevents duplicate uploads |
| Audit | Every significant action appended to `audit_logs` |
| Migrations | Alembic with explicit up/down for every change |

---

## Quick Start (Docker Compose)

### Prerequisites
- Docker & Docker Compose

### 1. Clone and configure

```bash
git clone <repo>
cd nyx/backend
cp .env.example .env
# Edit .env — fill in SECRET_KEY, JWT_SECRET_KEY, and POSTGRES_PASSWORD at minimum
# Generate secrets: openssl rand -hex 32
```

### 2. Start all services

**Development:**
```bash
docker compose up --build
```

**Production:**
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

This starts:
- **PostgreSQL** on `localhost:5432`
- **Redis** on `localhost:6379`
- **API** on `http://localhost:8000`
- **Worker** (OCR + reconciliation queues)
- **RQ Dashboard** on `http://localhost:9181`

Alembic migrations run automatically when the API starts.

### 3. Verify

```bash
curl http://localhost:8000/health
# → {"status":"healthy","version":"1.0.0",...}
```

Interactive API docs: **http://localhost:8000/docs**

---

## Development Setup (Local)

```bash
# Python 3.12+
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Start Postgres and Redis (or point .env at existing instances)
cp .env.example .env

# Run migrations
alembic upgrade head

# Start API
uvicorn app.main:app --reload --port 8000

# Start worker (separate terminal)
rq worker ocr reconciliation --url redis://localhost:6379/0
```

---

## API Reference

### Authentication

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/auth/register` | Create account |
| POST | `/api/v1/auth/login` | Get JWT tokens |
| POST | `/api/v1/auth/refresh` | Refresh access token |
| GET | `/api/v1/auth/me` | Current user profile |
| POST | `/api/v1/auth/change-password` | Change password |

### Invoices

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/invoices` | Upload PDF invoice (multipart) |
| GET | `/api/v1/invoices` | List with filters + pagination |
| GET | `/api/v1/invoices/{id}` | Invoice detail with line items |
| PATCH | `/api/v1/invoices/{id}` | Manual field correction |
| GET | `/api/v1/invoices/{id}/jobs` | Processing job history |

**Upload flow:**
1. `POST /api/v1/invoices` → HTTP 202 (accepted)
2. OCR job queued in Redis → worker extracts fields
3. Poll `GET /api/v1/invoices/{id}` — `status` progresses: `uploaded → queued → processing → extracted → reconciled`

### Vendors

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/vendors` | Create vendor |
| GET | `/api/v1/vendors` | List/search vendors |
| GET | `/api/v1/vendors/{id}` | Vendor detail |
| PATCH | `/api/v1/vendors/{id}` | Update vendor |

### Reconciliation

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/reconciliation` | Trigger reconciliation for invoice |
| GET | `/api/v1/reconciliation` | List records with filters |
| GET | `/api/v1/reconciliation/invoice/{id}` | Records for specific invoice |
| POST | `/api/v1/reconciliation/{id}/resolve` | Manually resolve discrepancy |

### Dashboard

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/dashboard/overview` | Full metrics snapshot |
| GET | `/api/v1/dashboard/invoices/summary` | Invoice status counts |
| GET | `/api/v1/dashboard/discrepancies/summary` | Discrepancy breakdown |
| GET | `/api/v1/dashboard/queue/status` | Worker queue depth |
| GET | `/api/v1/dashboard/analytics/trends` | 30-day trends |

### Audit Logs

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/audit` | Query audit trail (filterable) |

---

## Database Schema

```
users                 → roles: admin / accountant / viewer
vendors               → GST/PAN indexed, normalized name for matching
invoices              → full lifecycle status, financial fields, checksum
invoice_items         → line items extracted from invoice
processing_jobs       → RQ job tracking with retry state
reconciliation_records→ match status, discrepancy type, confidence score
audit_logs            → immutable event log (JSONB metadata)
```

All tables use:
- UUID primary keys
- `created_at` / `updated_at` with DB-level `updated_at` trigger
- UTC timestamps

---

## Reconciliation Engine

The engine runs automatically after OCR extraction and can also be triggered manually.

**Logic:**
1. **Duplicate check** — same invoice number + vendor + date within configurable window
2. **Amount matching** — compare `total_amount` vs `expected_amount` with tolerance
3. **Confidence scoring** — `1 - (diff / expected)`
4. **Status assignment** — `matched` / `partial_match` / `discrepancy` / `duplicate`

Tolerance is configurable: `RECONCILIATION_TOLERANCE_PERCENT=0.01` (1%).

---

## Environment Variables

See `.env.example` for the full reference. Critical production variables:

```bash
SECRET_KEY=<openssl rand -hex 32>
JWT_SECRET_KEY=<openssl rand -hex 32>
DATABASE_URL=postgresql://user:pass@host:5432/dbname
REDIS_URL=redis://host:6379/0
STORAGE_BACKEND=s3  # or local
APP_ENV=production
```

---

## Running Tests

```bash
# Requires a running test database
TEST_DATABASE_URL=postgresql://nyx:nyx@localhost:5432/nyx_test \
pytest --cov=app --cov-report=term-missing
```

---

## Deploying to Render / Railway

### Render

1. Create a **Web Service** pointing to this repo
2. Set **Dockerfile path**: `docker/Dockerfile`
3. Set **Docker target**: `production`
4. Add environment variables from `.env.example`
5. Add a **PostgreSQL** add-on → copy `DATABASE_URL`
6. Add a **Redis** add-on → copy `REDIS_URL`
7. Create a second **Background Worker** service with the same env vars but:
   - Dockerfile: `docker/Dockerfile.worker`
   - Start command: `rq worker ocr reconciliation --url $REDIS_URL`

### Railway

```bash
# Install Railway CLI
railway login
railway init
railway add postgresql
railway add redis
railway up
```

Set environment variables in Railway dashboard. Deploy the worker as a second service in the same project.

---

## Production Checklist

- [ ] Change `SECRET_KEY` and `JWT_SECRET_KEY` to random 32-byte hex strings
- [ ] Set `APP_ENV=production`
- [ ] Set `STORAGE_BACKEND=s3` and configure S3 credentials
- [ ] Configure `ALLOWED_HOSTS` to your domain
- [ ] Set up database backups
- [ ] Configure a reverse proxy (nginx/Caddy) with TLS
- [ ] Set up log aggregation (e.g., Datadog, Loki)
- [ ] Monitor the RQ dashboard (`/9181`) or connect to an APM
