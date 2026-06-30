# Nyx

> Modular Internal Business Operations Platform for SMEs.
> FastAPI + Next.js. SQLite for dev, PostgreSQL for prod.

[![Status](https://img.shields.io/badge/phase-stabilization-blue)](docs/architecture/11-roadmap.md)
[![License](https://img.shields.io/badge/license-MIT-green)](#)

Nyx is a configurable operations platform for 20–500 person companies. Accounts/invoices is the first module; Operations, Inventory, Customer Service, and Founder Intelligence are designed but not yet built. The full architecture is documented in [`docs/architecture/`](docs/architecture/) — start with [`00-vision.md`](docs/architecture/00-vision.md).

---

## Quick start (no Postgres, no Redis)

Requirements:

- **Python 3.12+**
- **Node.js 20+**

```bash
git clone <repo-url>
cd Nyx

# One command sets up everything (venv, deps, migrations).
./scripts/setup.sh        # macOS / Linux / WSL
# or on Windows:
.\scripts\setup.ps1
```

Then run the dev servers:

```bash
./scripts/dev.sh          # macOS / Linux / WSL
# or:
.\scripts\dev.ps1         # Windows
```

You now have:

- Backend API at **http://localhost:8000** (OpenAPI docs at `/docs`)
- Frontend at **http://localhost:3000**
- A SQLite database at `backend/nyx.db`
- Background jobs running **inline** (no Redis required)

That's it. No external services, no `.env` editing needed for development.

---

## Manual setup (if scripts don't suit you)

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head               # creates backend/nyx.db
uvicorn app.main:app --reload      # http://localhost:8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev                        # http://localhost:3000
```

---

## What's optional and why

| Component | Required for dev? | Required for prod? | Notes |
|---|---|---|---|
| Python 3.12+ | ✅ yes | ✅ yes | |
| Node 20+ | ✅ yes | ✅ yes | |
| SQLite | ✅ default | ⚠️ not recommended | Built into Python; nothing to install |
| PostgreSQL 16 | ❌ no | ✅ yes | Set `DATABASE_URL=postgresql://...` |
| Redis | ❌ no | ✅ yes | Without it, OCR + reconciliation run inline in the request thread |
| Tesseract + Poppler | ❌ no¹ | ✅ if using OCR | Without these, uploads still succeed; OCR job fails gracefully |

¹ The API still runs, uploads still succeed, and reconciliation still works on already-extracted invoices. Only the OCR worker step needs Tesseract — when missing, the invoice ends up in `failed` state with a note, exactly as it would for any OCR error.

### Installing Tesseract + Poppler (when you want OCR locally)

- **macOS:** `brew install tesseract poppler`
- **Ubuntu/Debian:** `sudo apt-get install tesseract-ocr poppler-utils`
- **Windows:** install from [tesseract-ocr/tesseract](https://github.com/UB-Mannheim/tesseract/wiki) and [poppler releases](https://github.com/oschwartz10612/poppler-windows/releases) and add both to PATH.

---

## Running tests

```bash
cd backend
. .venv/bin/activate
pytest
```

Tests run against an in-memory SQLite by default — no setup required.

---

## Project layout

```
Nyx/
├── backend/                  # FastAPI app + Alembic + workers
│   ├── app/
│   │   ├── api/v1/           # route handlers
│   │   ├── models/           # SQLAlchemy ORM (portable across SQLite + Postgres)
│   │   ├── schemas/          # Pydantic DTOs
│   │   ├── services/         # business logic
│   │   ├── repositories/     # data access
│   │   ├── workers/          # background jobs (RQ or inline)
│   │   ├── core/             # logging, security, db types, etc.
│   │   ├── config.py
│   │   ├── database.py
│   │   └── main.py
│   ├── alembic/              # database migrations
│   ├── tests/                # pytest suite
│   ├── .env.example          # all env vars are optional in dev
│   └── requirements.txt
│
├── frontend/                 # Next.js 15 (App Router) + Tailwind + TanStack Query
│   ├── app/                  # routes (auth + dashboard groups)
│   ├── components/
│   ├── services/             # axios API clients
│   ├── hooks/                # TanStack Query hooks
│   ├── store/                # Zustand stores
│   └── package.json
│
├── docs/architecture/        # the authoritative architecture docs
├── scripts/                  # setup.{sh,ps1}  dev.{sh,ps1}
├── Makefile                  # `make help` for shortcuts
└── STATUS.md                 # current project status
```

---

## Production deployment

Production uses PostgreSQL + Redis. Follow the platform-specific deployment notes in [`backend/README.md`](backend/README.md) (Render, Railway).

---

## Documentation

- **[STATUS.md](STATUS.md)** — what's done, what's next.
- **[docs/architecture/](docs/architecture/)** — the full platform architecture, module breakdown, 8 Architecture Decision Records, and 8-week roadmap.
- **[backend/README.md](backend/README.md)** — backend-specific API reference and deploy notes.

---

## License

MIT. See [LICENSE](LICENSE) (TBD).
