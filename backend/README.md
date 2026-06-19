# Nyx Backend

FastAPI + SQLAlchemy + Alembic + (optionally) Redis/RQ.
Runs on **SQLite** with **zero external services** by default; switches to
**PostgreSQL + Redis** in production via environment variables.

For project-level orientation see [`../README.md`](../README.md) and the
architecture docs at [`../docs/architecture/`](../docs/architecture/).

---

## Local quick start

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head               # creates backend/nyx.db
uvicorn app.main:app --reload      # http://localhost:8000
```

No `.env` file required. All settings have safe development defaults. See
[`.env.example`](.env.example) to learn what's configurable.

### Health check

```bash
curl http://localhost:8000/health
# → {"status":"healthy",...}  (or "degraded" if Redis is offline — that's fine in dev)
```

OpenAPI docs: **http://localhost:8000/docs** (development only).

---

## What runs without Redis?

The OCR + reconciliation pipeline normally enqueues jobs to Redis via RQ.
When Redis is unavailable (or `QUEUE_BACKEND=inline`), the same job functions
run **inline in the request thread**. The API contract is unchanged — `POST
/api/v1/invoices` still returns 202 — but the work happens before the response
returns instead of in a worker. This is fine for development and demos.

For production set `QUEUE_BACKEND=redis` (or `auto` with `REDIS_URL` reachable)
and run an RQ worker:

```bash
rq worker ocr reconciliation --url redis://localhost:6379/0
```

---

## OCR system dependencies (optional)

`pytesseract` and `pdf2image` need binaries on the host:

- **macOS:** `brew install tesseract poppler`
- **Ubuntu/Debian:** `sudo apt-get install tesseract-ocr poppler-utils`
- **Windows:** install Tesseract from
  [UB-Mannheim](https://github.com/UB-Mannheim/tesseract/wiki) and Poppler from
  [oschwartz10612/poppler-windows](https://github.com/oschwartz10612/poppler-windows/releases),
  then add both to `PATH`.

Without these, the API still runs and uploads still succeed. Only the OCR
worker step fails — the affected invoice ends up in `failed` state with an
explanatory `extraction_notes` row, exactly as it would for any OCR error.

---

## Switching to PostgreSQL

```bash
export DATABASE_URL=postgresql://nyx:nyx@localhost:5432/nyx
alembic upgrade head
```

Alembic migration 0001 is portable across SQLite and PostgreSQL — the same
migration creates the right schema on either engine.

---

## Docker (optional)

```bash
docker compose up --build
```

This still works and brings up Postgres + Redis + API + worker + RQ Dashboard +
frontend. It is **not required**: the local-first path above is the supported
default for development.

For production, the overlay file:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

---

## API reference (summary)

Full interactive docs at `/docs`. High-level surface:

| Group | Routes |
|---|---|
| Auth | `/api/v1/auth/{register,login,refresh,me,change-password}` |
| Invoices | `/api/v1/invoices`, `/{id}`, `/{id}/jobs` |
| Vendors | `/api/v1/vendors`, `/{id}` |
| Reconciliation | `/api/v1/reconciliation`, `/{id}/resolve`, `/invoice/{id}` |
| Dashboard | `/api/v1/dashboard/{overview,invoices/summary,discrepancies/summary,queue/status,analytics/trends}` |
| Audit | `/api/v1/audit` |
| System | `/health`, `/` |

---

## Tests

```bash
pytest
```

The default test DB is in-memory SQLite — no setup needed. To run against
Postgres instead:

```bash
TEST_DATABASE_URL=postgresql://nyx:nyx@localhost:5432/nyx_test pytest
```

---

## Production checklist

- [ ] Set `APP_ENV=production`
- [ ] Generate strong `SECRET_KEY` and `JWT_SECRET_KEY` (`python -c "import secrets; print(secrets.token_hex(32))"`)
- [ ] Set `DATABASE_URL` to your managed Postgres
- [ ] Set `REDIS_URL` and `QUEUE_BACKEND=redis`
- [ ] Set `STORAGE_BACKEND=s3` and configure S3 credentials (or keep `local` with a persistent volume)
- [ ] Configure `ALLOWED_HOSTS` to your domain(s)
- [ ] Set up DB backups
- [ ] Front it with a reverse proxy (nginx / Caddy) terminating TLS
- [ ] Wire structured logs into your aggregator (`LOG_FORMAT=json`)

### Deploy targets

**Render:** create a Web Service from this repo with Dockerfile path `docker/Dockerfile`, add a Postgres add-on and a Redis add-on, configure env vars from `.env.example`, then add a Background Worker service using `docker/Dockerfile.worker` with `rq worker ocr reconciliation --url $REDIS_URL`.

**Railway:** `railway init && railway add postgresql && railway add redis && railway up`; add a second worker service in the same project.
