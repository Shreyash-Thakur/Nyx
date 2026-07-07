# Nyx — Project Status

**Date:** 2026-07-08 (verified against the repo; test count and two post-regen commits folded in)
**Branch:** `main`
**Owner:** Shreyash Thakur · admin@nashermiles.com
**Repo:** `C:\Users\shrey\Desktop\Dump\Nyx`

> **State:** The Accounts (invoice OCR + reconciliation) module runs a **complete,
> connected business pipeline** end to end, driven by the workflow engine and the
> event bus rather than hand-chained service calls. A real invoice flows
> Upload → OCR → Extraction → **workflow** → (human-verify gate → approval gate) →
> Reconciliation → **RECONCILED** → Tally export, with the audit trail, dashboard,
> events and in-app notifications all updating as a side effect. The three core
> foundations (multi-tenancy, event bus + durable log, RBAC) are in place and the
> workflow engine is now the single execution path for post-extraction work.
> Backend: **107 tests passing** on SQLite, including a real HTTP-level
> end-to-end pipeline walk and adversarial cases.

This file is the ground-truth state of the **code**. The long-term design intent
lives in `docs/architecture/` and `docs/architecture/adr/`.

---

## 1. What changed most recently (this work cycle)

A push to turn the strong foundation into a genuinely usable, connected pipeline:

1. **Tenant isolation closed end-to-end.** Reads, writes and the audit log are
   uniformly tenant-scoped in the repositories/services; cross-tenant get/update/
   verify are 404, not leaks. (TD-7b)
2. **Audit converged onto the event bus (TD-6, ADR-0002).** Audit is now a `"*"`
   subscriber — one write, two views (event log + audit trail); no more dual-write
   drift.
3. **Workflow engine is the real pipeline (ADR-0003).** The post-extraction path
   (reconciliation and the gates) runs through the engine; the old bespoke
   `reconciliation_worker` is gone. Retry / failure-recovery for failed instances.
4. **Finance approval gate (Priority 1).** Invoices over
   `FOUNDER_APPROVAL_THRESHOLD_INR` park at `pending_approval`; approve/reject
   endpoints resume the same workflow.
5. **Human-verify OCR queue (TD-3, Priority 5).** Low-confidence reads park at a
   new `needs_verification` status; a verify endpoint resumes the workflow. The
   verify gate runs *before* the approval gate (a low-confidence amount can't be
   trusted to drive the approval decision).
6. **Reconciliation completes.** With no external PO to match, reconcile now falls
   back to a self-consistency check (subtotal + taxes vs total) so a clean invoice
   actually reaches `RECONCILED`; reconcile is idempotent on replay.
7. **Tally XML export (Priority 5)** — dry-run voucher XML for reconciled invoices.
8. **In-app notification engine (Priority 1/5)** — event-driven notifications for
   approval-required, needs-verification, rejections, and discrepancies; plus
   unread-count and mark-all-read endpoints (per-user scoped) for a usable UI.
9. **Health check respects the inline queue** — `/health` no longer reports
   degraded when the inline queue is the intended backend; Redis is only
   required in explicit redis mode.

Commits this cycle: `38e94da`, `53bf1d5`, `f52f45d`, `7f8bbf7`, `3c069ec`,
`9f14783`, `0325092`, `5a35e24`, `9289ac9`, `cffc68d`, `fec7e78`, `164edf2`,
`29c058b`, `3c18142`, `32ee782`, `017b58a`.

---

## 2. Current architecture

### Backend (FastAPI + SQLAlchemy 2.0 + Alembic)

```
app/
  api/v1/        auth · invoices · vendors · reconciliation · dashboard · audit ·
                 activity · notifications · workflows
  services/      auth · invoice · ocr · reconciliation · vendor · dashboard ·
                 storage · tally_export
  repositories/  BaseRepository + per-aggregate repos (tenant-scoped)
  models/        tenant · event · user · vendor · invoice · invoice_item ·
                 reconciliation · processing_job · audit_log · notification ·
                 workflow   (12 tables)
  workers/       invoice_processor (OCR) · workflow_worker (post-extraction) ·
                 queue (redis|inline, with retry + inline fallback)
  core/
    tenancy.py   DEFAULT_TENANT_ID + ensure_default_tenant
    events/      EventBus (subscribe/publish) · durable log · outbox ·
                 audit_subscriber (*) · notification_subscriber
    workflow/    engine (runner + restricted conditions) · actions (registry +
                 invoice_post_extraction definition + gates)
    rbac.py      Permission catalogue + ROLE_PERMISSIONS + can()
    system.py    ensure_system_user (system principal for background jobs)
    security · db_types (portable GUID) · logging · middleware · limiter · exceptions
  config.py      SQLite-first defaults; Postgres/Redis via env
```

**Layering:** API → service → repository → model. Cross-cutting concerns have
homes: tenancy, events (+ subscribers), workflow engine, rbac, system principal.

**Post-extraction workflow** (`invoice_post_extraction`), steps in order:
1. `check_confidence_gate` — park at `needs_verification` if OCR confidence is low
2. `check_approval_gate` — park at `pending_approval` if amount > threshold
3. `reconcile_invoice` — reconcile (self-consistency fallback) → `reconciled`

Each gate sets the workflow context `status`, which is what makes downstream
steps' `when` clauses skip — no bespoke branching.

**Migrations:** `0001` initial · `0002` tenant foundation · `0003` events ·
`0004` workflow_instances · `0005` approval status/audit enums ·
`0006` notifications · `0007` verification status/audit enums. Portable across
SQLite and Postgres (enum ADDs are Postgres-only, no-op on SQLite).

### Frontend (Next.js 15 App Router + TanStack Query + Zustand)

Login + dashboard route groups; typed service/hook layer; JWT interceptor with
refresh. Dashboard activity panel is live (event log). Some KPI/chart fallbacks
still show illustrative numbers when the API has no data (TD-2b).

### Infrastructure

SQLite + inline queue by default (zero external services); Postgres + Redis + RQ
in production. Local filesystem or S3 storage.

---

## 3. Implemented features

| Area | Status |
|---|---|
| Auth (register/login/refresh/me/change-password), JWT, bcrypt, login rate-limit | ✅ |
| RBAC — `can()`/`require(permission)`; admin/accountant/viewer permission sets | ✅ |
| Multi-tenant schema + **uniform tenant read/write/audit isolation** | ✅ |
| Event bus — durable `events` log + in-process subscribers; outbox semantics | ✅ |
| **Audit = event subscriber** (one write, two views; no dual-write drift) | ✅ |
| **Workflow engine** — durable instances, restricted conditions, retry/recovery | ✅ |
| Invoice upload — content/size validation, SHA-256 dedup, emits events | ✅ |
| OCR pipeline (tesseract+regex) — inline & worker modes both complete | ✅ |
| **Human-verify queue** — low-confidence reads park at `needs_verification` | ✅ |
| **Finance approval gate** — high-value invoices park at `pending_approval` | ✅ |
| Reconciliation — self-consistency + reference match; idempotent; duplicate detect | ✅ |
| **Tally XML export** — dry-run voucher XML for reconciled invoices | ✅ |
| **Notifications** — event-driven in-app notifications + read/unread/unread-count/mark-all-read API | ✅ |
| Vendors — CRUD + normalization | ✅ |
| Dashboard — overview/summaries/queue/trends (SQLite-safe); verify/approval counts | ✅ |
| Activity feed — tenant-scoped recent events; live on the dashboard | ✅ |

---

## 4. Incomplete / not yet built

**Core layer (designed, not built):** task system, conversation runtime,
tenant **onboarding/provisioning** (schema is ready, flow is not), RBAC
**dynamic/DB-backed roles** (static role→perm mapping today), event bus
**async Redis fan-out tier** (subscribers run synchronously in the publishing
transaction today).

**Modules (designed, not built):** Operations, Inventory, Customer Service,
Founder Intelligence. Only Accounts exists; not yet reorganized into
`app/modules/accounts/`.

**Integrations:** Tally is **dry-run only** (XML built, nothing pushed);
WhatsApp, Shopify — none built.

**Frontend:** KPI/chart fallbacks still illustrative when the API is empty;
module-grouped nav; settings/analytics depth; no frontend tests.

---

## 5. Technical debt (remaining)

| # | Debt | Severity |
|---|---|---|
| TD-2b | Frontend KPI/chart fallbacks show illustrative numbers when API is empty | Low |
| TD-5 | `invoice.upload` still commits in multiple steps (not a single unit of work) | Med |
| TD-8 | No auth hardening (email verification / reset / token revocation) | Med |
| TD-11 | Event subscribers run synchronously in the publishing transaction — a slow/failing subscriber blocks the producer; needs the async fan-out tier | Med |
| TD-12 | Upload dedup (check-then-insert) isn't atomic — a concurrent duplicate upload can race past it (no unique constraint, to keep FAILED re-upload working) | Low |
| TD-10 | `requirements.txt`: `httpx` duplicated; `pypdf2` appears unused | Low |

---

## 6. Test coverage

- **Backend: 107 passing** on in-memory SQLite (`pytest`, ~34s).
- **`test_e2e_pipeline.py`** walks the whole connected pipeline over real HTTP
  (upload → OCR → extract → workflow → gates → reconcile → Tally export →
  dashboard → events → audit), mocking only OCR text extraction and blob I/O.
  Adversarial cases: duplicate upload, empty file, cross-tenant verify (404),
  malformed extraction.
- Per-feature suites: tenancy, events, audit subscriber, rbac, workflow (+ API),
  approval gate, verification queue, tally export, notifications, reconciliation,
  dashboard, storage, workers, invoices, activity, auth.
- **Gaps:** Postgres migration round-trip (CI only); real OCR text parsing (needs
  tesseract); frontend has no tests.

---

## 7. Recommended next steps (dependency order)

1. **Async event fan-out tier (TD-11)** — move subscribers off the producer's
   transaction (outbox → worker) so a slow/failing subscriber can't block a
   business write. The last structural gap in the event architecture.
2. **Auth hardening (TD-8)** — email verification, password reset, token
   revocation; required before any real multi-user deployment.
3. **Accounts module reorg** into `app/modules/accounts/` + `import-linter` —
   before a second module exists and the boundary is harder to draw.
4. **Real Tally push** behind the existing dry-run (currently XML-only).
5. **Tenant onboarding/provisioning flow** — the schema is tenant-aware; the
   sign-up/provision path is not.
6. **Conversational layer / WhatsApp** — one approval flow end-to-end (ADR-0006).

---

## 8. Architectural notes

1. **The workflow engine is now load-bearing** — it is the single post-extraction
   execution path. Keep it right-sized (action registry is the only extensibility
   point; restricted conditions; replaceable).
2. **Event subscribers are synchronous** (TD-11) — correct and simple today, but
   the producer pays for subscriber latency/failure. The async tier is the fix.
3. **Transaction boundaries** are still loose in `upload` (TD-5).
4. **Reconciliation without a reference** relies on invoice self-consistency —
   defensible, but a real PO/GRN match is stronger once those documents exist.

---

*Regenerated after the connected-pipeline cycle. Update whenever the state of the
code changes materially.*
