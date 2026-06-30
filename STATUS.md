# Nyx — Project Status

**Date:** 2026-06-30
**Branch:** `main`
**Owner:** Shreyash Thakur · admin@nashermiles.com
**Repo:** `C:\Users\shrey\Desktop\Dump\Nyx`

> **State:** The Accounts (invoice OCR + reconciliation) module works end-to-end,
> and the platform now has its first three core-layer foundations built and
> tested: **multi-tenancy schema**, an **in-process event bus + durable event
> log**, and **permission-based RBAC**. The core pipeline is verified at runtime.
> Backend: **45 tests passing** on SQLite (was 20). Four confirmed pipeline bugs
> are fixed.

This file is the ground-truth state of the **code**. The design intent lives in
`docs/architecture/` (still authoritative for the long-term vision).

---

## 1. What changed most recently (this work cycle)

A focused push to make the foundation production-real, in dependency order:

1. **Fixed the core pipeline (4 bugs).** Upload → OCR → reconcile now completes
   in both inline and worker modes. (§5)
2. **Tenant-aware schema (ADR-0008).** Every domain table carries `tenant_id`;
   writes are stamped from the acting principal; a default tenant is seeded.
3. **Event bus + durable event log (ADR-0002).** In-process pub/sub backed by an
   append-only `events` table (transactional outbox). Accounts emits real domain
   events; an async fan-out tier remains deferred.
4. **Permission-based RBAC (ADR-0004).** A single `can(user, permission)` gates
   every route. Previously any authenticated user had full authority.
5. **Activity feed.** `GET /api/v1/activity` — the first tenant-scoped read over
   the event log; the dashboard activity panel now renders live events instead
   of a hard-coded array.

Commits this cycle: `0ac03a1`, `f72dc44`, `62a37c3`, `9614f10`, `04c783b`,
`88d00d3`.

---

## 2. Current architecture

### Backend (FastAPI + SQLAlchemy 2.0 + Alembic)

```
app/
  api/v1/        auth · invoices · vendors · reconciliation · dashboard · audit · activity
  services/      auth · invoice · ocr · reconciliation · vendor · dashboard · storage
  repositories/  BaseRepository + per-aggregate repos
  models/        tenant · event · user · vendor · invoice · invoice_item ·
                 reconciliation · processing_job · audit_log   (9 tables)
  workers/       invoice_processor (OCR) · reconciliation_worker · queue (redis|inline)
  core/
    tenancy.py   DEFAULT_TENANT_ID + ensure_default_tenant
    events/      EventBus (subscribe/publish), durable log, transactional outbox
    rbac.py      Permission catalogue + ROLE_PERMISSIONS + can()
    system.py    ensure_system_user (system principal for background jobs)
    security · db_types (portable GUID) · logging · middleware · limiter · exceptions
  config.py      SQLite-first defaults; Postgres/Redis via env
```

**Layering:** API → service → repository → model. Cross-cutting concerns now have
homes: tenancy, events, rbac, system principal.

**Migrations:** `0001` initial · `0002` tenant foundation · `0003` events table.
All portable across SQLite and Postgres; verified applying cleanly on SQLite.

### Frontend (Next.js 15 App Router + TanStack Query + Zustand)

Login + dashboard route groups; typed service/hook layer; JWT interceptor with
refresh. Dashboard activity panel is now live (event log); KPI/chart fallbacks
still contain illustrative numbers when the API has no data (see §4 TD-2b).

### Infrastructure

SQLite + inline queue by default (zero external services); Postgres + Redis +
RQ in production. Local filesystem or S3 storage. CI runs migrations + pytest
on Postgres/Redis.

---

## 3. Implemented features

| Area | Status |
|---|---|
| Auth (register/login/refresh/me/change-password), JWT, bcrypt, login rate-limit | ✅ |
| **RBAC** — `can()`/`require(permission)`; admin/accountant/viewer permission sets | ✅ |
| **Multi-tenant schema** — `tenant_id` on all domain tables; writes stamped from principal | ✅ |
| **Event bus** — durable `events` log + in-process subscribers; outbox semantics | ✅ |
| Invoice upload — content/size validation, SHA-256 dedup, audit, **emits events** | ✅ |
| OCR pipeline (tesseract+regex) — inline & worker modes both complete | ✅ |
| Reconciliation — manual + auto (system principal); tolerance match; duplicate detection | ✅ |
| Vendors — CRUD + normalization | ✅ |
| Dashboard — overview/summaries/queue/trends (SQLite-safe) | ✅ |
| Audit log — write on every state change; queryable (serialization fixed) | ✅ |
| **Activity feed** — tenant-scoped recent events; live on the dashboard | ✅ |

---

## 4. Incomplete / not yet built

**Core layer (designed, not built):** workflow engine (next), task system,
notifications, conversation runtime, tenant **onboarding** (schema is ready,
provisioning flow is not), RBAC **dynamic/DB-backed roles** (static role→perm
mapping today), event bus **async Redis fan-out tier**, audit-as-event-subscriber
(audit still writes directly alongside events).

**Modules (designed, not built):** Operations, Inventory, Customer Service,
Founder Intelligence. Only Accounts exists; not yet reorganized into
`app/modules/accounts/`.

**Integrations:** Tally, WhatsApp, Shopify — none built.

**Frontend:** KPI sparklines / chart fallbacks still illustrative; module-grouped
nav; settings/analytics depth.

---

## 5. Bugs fixed this cycle (all with regression tests)

| ID | Bug | Fix |
|---|---|---|
| BUG-1 | Inline OCR crashed (`event loop is already running`) — broke the default local path | `StorageService.read_sync()`; worker no longer drives an event loop |
| BUG-2 | Auto-reconcile violated a FK (fake system-user UUID) | Real seeded system principal (`ensure_system_user`) |
| BUG-3 | Dashboard `extract('epoch')` returned garbage on SQLite | Dialect-aware duration (julianday on SQLite) |
| BUG-4 | Inline invoices stuck in `queued` (status clobber after dispatch) | Mark queued before dispatch; targeted `rq_job_id` update; refresh |
| BUG-5 | Audit endpoint 500 on non-empty result (`metadata` vs `extra_data`) | Response model aligned to the renamed column |

**Runtime verification:** register → login → upload → `extracted` → activity →
dashboard → audit all succeed over real HTTP on a migrated SQLite DB; a `viewer`
is correctly `403`'d from uploading; invoices/events/users are tenant-stamped.

---

## 6. Technical debt (remaining)

| # | Debt | Severity |
|---|---|---|
| TD-2b | Frontend KPI/chart fallbacks still show illustrative numbers when API is empty | Low |
| TD-5 | `invoice.upload` still commits in multiple steps (not a single unit of work) | Med |
| TD-6 | Audit is written directly *and* events are emitted; converge audit onto the bus | Med |
| TD-3 | Regex OCR is brittle; needs a human-verify screen + confidence gating | Med |
| TD-7b | Tenant **reads** are not yet uniformly scoped (only activity is); enforce in repos | Med |
| TD-8 | No auth hardening (email verification / reset / token revocation) | Med |
| TD-9 | `backend/uploads/_purge_*` and `frontend/.next/` artifacts tracked in tree | Low |
| TD-10 | `requirements.txt`: `httpx` duplicated; `pypdf2` appears unused | Low |

---

## 7. Test coverage

- **Backend: 45 passing** on in-memory SQLite (`pytest`, ~14s). New suites:
  `test_storage`, `test_workers`, `test_dashboard`, `test_tenancy`, `test_events`,
  `test_rbac`, `test_audit`, `test_activity`, plus an inline-pipeline status test.
- Worker, storage, dashboard, tenancy, event-bus and RBAC paths — previously the
  biggest blind spot — are now covered, including the bugs that lived there.
- **Gaps:** Postgres-specific migration round-trip (CI only); OCR text parsing;
  full inline HTTP integration (the in-memory two-engine split makes it a script,
  not a pytest — see `scratchpad/verify_http.py` pattern); frontend has no tests.

---

## 8. Recommended next steps (dependency order)

1. **Workflow engine (roadmap W2)** — minimal action-registry + durable
   `workflow_instances` runner; express the invoice lifecycle declaratively
   instead of chained service calls. The riskiest architectural bet; prove it on
   existing code first. Keep the surface small and behind a facade.
2. **Converge audit onto the event bus (TD-6)** — make the audit log a `*`
   subscriber; remove direct `audit_repo.log` calls once parity is proven.
3. **Uniform tenant read-scoping (TD-7b)** — push `tenant_id` filtering into the
   repositories so every list/get is tenant-isolated, not just activity.
4. **Accounts module reorg** into `app/modules/accounts/` + `import-linter`.
5. **Human-verify OCR screen** (TD-3) and then the **Tally dry-run** connector.
6. **Conversational layer / WhatsApp** — one approval flow end-to-end.

## 9. Effort estimates (single dev + AI assist)

| Task | Size |
|---|---|
| Workflow engine (runner + instances + registry, invoice lifecycle) | L (1–2 wk) |
| Audit → event subscriber convergence | S–M (1–3 d) |
| Tenant read-scoping in repositories | M (2–4 d) |
| Accounts reorg + import-linter | M (2–3 d) |
| Tally dry-run + human-verify screen | L (1–1.5 wk) |
| Conversational layer (WhatsApp, 1 flow) | L (1.5 wk) |
| Auth hardening | M (2–3 d) |

---

## 10. Architectural concerns

1. **Workflow engine is the next big bet** — keep it right-sized (action registry
   is the only extensibility point; restricted conditions; replaceable facade).
2. **Tenant reads** must catch up to tenant writes before multi-tenant onboarding,
   or isolation is only half-real (TD-7b).
3. **Two write paths for cross-cutting state** (direct audit + events) — converge
   to avoid drift (TD-6).
4. **Transaction boundaries** still loose in `upload` (TD-5); the workflow engine
   should bring a clearer unit-of-work story for multi-step flows.

---

*Regenerated after the foundation cycle. Update whenever the state of the code
changes materially.*
