# Nyx — Project Status

**Date:** 2026-06-19
**Branch:** `main` (clean) · **Last commit:** `516cbb1` — *docs(arch): reposition Nyx as a Modular Business Operations Platform*
**Owner:** Shreyash Thakur · admin@nashermiles.com
**Repo:** `C:\Users\shrey\Desktop\Dump\Nyx`

> **Phase complete:** architectural redesign. Nyx is repositioned from a finance product to a **Modular Internal Business Operations Platform** for Indian SMEs (20–500 employees). 24 architecture documents (~6,100 lines) committed. Code implementation under the new layout has not yet started — that's Week 1 of the roadmap.

---

## 1. The repositioning, in one paragraph

Nyx is no longer "a finance ops + invoice OCR product." Nyx is a **modular operating system for SME operations** — Accounts is one of five modules. The five modules share a common Core (RBAC, events, workflows, tasks, notifications, conversation runtime, integrations). The defining capabilities are: **workflow orchestration**, **WhatsApp as a primary UI** (not just notifications), **a unified audit trail across every action**, and **Tally-friendly accounts**. We are not competing with SAP or Odoo Enterprise — we win by being smaller, opinionated, WhatsApp-native, and Tally-friendly for 20–500 person Indian companies.

## 2. What was just delivered (commit `516cbb1`)

**24 architecture documents under [`docs/architecture/`](docs/architecture/) — ~6,100 lines, single coherent commit, no code changes.**

### Core architecture docs

| File | Lines | What it answers |
|---|---:|---|
| [`00-vision.md`](docs/architecture/00-vision.md) | 116 | What Nyx is, who it serves, 10 principles, explicit non-goals |
| [`01-platform-overview.md`](docs/architecture/01-platform-overview.md) | 148 | Three-layer architecture and inter-layer rules |
| [`02-modules.md`](docs/architecture/02-modules.md) | 224 | What each of the five modules owns/emits/subscribes/refuses |
| [`03-folder-structure.md`](docs/architecture/03-folder-structure.md) | 232 | Target backend + frontend layout; migration map from current |
| [`04-database.md`](docs/architecture/04-database.md) | 803 | Naming, tenancy, core+module tables, indexes, JSONB policy |
| [`05-event-bus.md`](docs/architecture/05-event-bus.md) | 545 | Two-tier delivery, persisted log, replay, ordering, naming |
| [`06-workflow-engine.md`](docs/architecture/06-workflow-engine.md) | 1089 | YAML DSL, runner, conditions, actions, approval chains |
| [`07-rbac.md`](docs/architecture/07-rbac.md) | 243 | Role × permission × scope; web + WhatsApp + worker parity |
| [`08-integrations.md`](docs/architecture/08-integrations.md) | 632 | Connector ABC, registry, Tally deep-dive, pull/push/receive |
| [`09-conversational.md`](docs/architecture/09-conversational.md) | 754 | WhatsApp runtime; rule-first / LLM-fallback; pending prompts |
| [`10-founder-intelligence.md`](docs/architecture/10-founder-intelligence.md) | 188 | Event-fed aggregates; daily snapshot; alerts |
| [`11-roadmap.md`](docs/architecture/11-roadmap.md) | 206 | 8-week plan with weekly exit criteria; pre-decided cuts list |
| [`12-tech-debt-risks.md`](docs/architecture/12-tech-debt-risks.md) | 152 | Existing debt, accepted new debt, risks, interview Q&A |

### Architecture Decision Records (`docs/architecture/adr/`)

Eight ADRs, each defending one load-bearing "why didn't you use X" choice:

| ADR | Decision |
|---|---|
| [0001](docs/architecture/adr/0001-modular-monolith-over-microservices.md) | Modular monolith, not microservices |
| [0002](docs/architecture/adr/0002-in-process-event-bus.md) | In-process bus + Redis fanout, not Kafka |
| [0003](docs/architecture/adr/0003-custom-workflow-engine.md) | Custom workflow engine, not Temporal/Camunda |
| [0004](docs/architecture/adr/0004-app-layer-rbac-no-rls.md) | Application-layer RBAC, not Postgres RLS |
| [0005](docs/architecture/adr/0005-single-postgres-no-cqrs.md) | Single Postgres with materialized aggregates, not CQRS+separate read DB |
| [0006](docs/architecture/adr/0006-whatsapp-as-primary-ui.md) | WhatsApp as primary UI, not a notification channel |
| [0007](docs/architecture/adr/0007-rules-first-llm-fallback.md) | Rule-first intents; LLM only as fallback for fuzzy text |
| [0008](docs/architecture/adr/0008-tenant-id-everywhere.md) | Tenant-aware schema today; tenant onboarding deferred |

## 3. Platform shape

```
INTERFACE LAYER         Web Dashboard      WhatsApp Conversation     Email Inbound
                              │                    │                       │
                              ▼                    ▼                       ▼
BUSINESS MODULES        Accounts   Operations   Inventory   Customer Service   Founder Intelligence
                              │           │          │             │                   │
                              └───────────┴──────────┴─────────────┴───────────────────┘
                                                       │
                                                       ▼
CORE LAYER              Identity • RBAC • Audit • Events • Workflows • Tasks
                        Notifications • Conversation Runtime • Integrations • Tenants
                                                       │
                                                       ▼
INFRASTRUCTURE          PostgreSQL  •  Redis  •  RQ Workers
```

### Module roster

| Module | Code | Purpose | State |
|---|---|---|---|
| **Accounts** | `acc` | Invoice OCR · reconciliation · Tally push · vendors | **Built** (under old layout); needs reorg into `app/modules/accounts/` |
| **Operations** | `ops` | Orders (Shopify/Amazon/Flipkart) · dispatches · logistics · returns | Designed; not built |
| **Inventory** | `inv` | SKUs · warehouses · stock levels · transfers · reorder | Designed; not built |
| **Customer Service** | `cs` | Tickets · SLAs · escalations · templates · customer history | Designed; not built |
| **Founder Intelligence** | `fi` | Cross-module aggregates · daily snapshot · alerts | Designed; not built |

### Core capabilities (every module consumes these)

Identity & Tenants · RBAC (`can(user, action, resource, *, tenant_id)`) · Audit Log (subscribes to every event) · Event Bus (two-tier: in-proc sync + Redis async, durable `events` table, replayable) · Workflow Engine (YAML defs, runs identically from web/event/WhatsApp/schedule) · Task System · Notifications (in-app + WhatsApp + email) · Conversation Runtime (WhatsApp inbound → principal → intent → workflow; rule-first; LLM only for fuzzy fallback) · Integration Framework (Tally, Shopify, Amazon, Flipkart, Gmail, Outlook, Sheets, WhatsApp, webhooks)

## 4. Code state right now

### What runs today
- The finance/invoice pipeline (will become the Accounts module): upload → SHA-256 dedup → OCR → reconciliation → audit, all behind JWT auth with a coarse `admin/accountant/viewer` role enum.
- structlog logging, slowapi-rate-limited login, `/health` checking Postgres + Redis.
- Alembic baseline migration; Docker Compose dev stack (db + redis + api + worker + rq-dashboard + frontend).
- Frontend: Next.js 15 App Router scaffold with `(auth)` + `(dashboard)` route groups, TanStack Query hooks, Zustand auth store, axios JWT interceptor. Several dashboard pages are scaffolded; the Overview page still mixes API data with a static `ACTIVITY` array (acknowledged in code).

### What is designed but not yet coded
- **Core layer:** tenants, new RBAC, event bus + persisted `events` table, workflow engine, task system, conversation runtime, integration framework.
- **Modules:** Operations, Inventory, Customer Service, Founder Intelligence (only the Accounts module exists in code).
- **Integrations:** Tally connector under the new framework with XML-mapping dry-run; WhatsApp Cloud API connector; Shopify pull connector.
- **CI workflow, `.env.example`, expanded test coverage.**

## 5. Recent commits (last 5)

```
516cbb1  docs(arch): reposition Nyx as a Modular Business Operations Platform
7676e48  fix: correct title and link rel attribute in LedgerFlow.html
35655e4  refactor: simplify enum type creation in initial schema and update related columns
3656e1a  Refactor code structure for improved readability and maintainability
4fa1535  refactor: rename LedgerFlow to Nyx across the codebase and update related configurations
```

## 6. 8-week roadmap (full plan in [`11-roadmap.md`](docs/architecture/11-roadmap.md))

| Week | Goal | Exit criterion |
|---|---|---|
| **1** | Platform foundations: tenants, RBAC, events, audit | Existing endpoints work under new RBAC; every state change writes an event row |
| **2** | Workflow engine + Tasks | Invoice lifecycle runs as a declarative workflow, not chained service calls |
| **3** | Module reorg + Accounts cleanup + Tally dry-run | All Accounts code under `app/modules/accounts/`; Tally XML viewable on a human-verify screen |
| **4** | Conversational layer (WhatsApp) | Founder approves an invoice via WhatsApp; rule-based intents end-to-end |
| **5** | Operations module (orders + dispatches) | Shopify order → dispatch task → warehouse `DONE` on WhatsApp → inventory decrement |
| **6** | Inventory module + Customer Service skeleton | Stock transfer end-to-end via WhatsApp; ticket lifecycle exists |
| **7** | Founder Intelligence | Snapshot page reads only from aggregates; WhatsApp daily summary fires |
| **8** | Hardening, observability, demo polish | `import-linter` passes; canonical flow tests green; 12-min demo script captured |

### MVP demo (Week 8 target)

1. Login → operator dashboard with module-grouped nav
2. Invoice upload → OCR → human verify → reconcile → Tally XML generated
3. Founder-approval workflow firing on threshold, approved via WhatsApp
4. WhatsApp `DONE` on a stock-transfer task → completes workflow → updates inventory
5. Founder Snapshot page fed by event subscribers
6. Audit log showing every event with actor + matched permission

### What gets cut first if we slip

1. Outlook integration (Gmail covers the demo)
2. Returns & RTO flow in Operations
3. CSAT capture in CS
4. Approval-chain UI editor (keep chains in YAML for the demo)
5. Founder alerts UI editor (alerts seeded in code only)

What does **not** get cut: RBAC parity across web+WhatsApp · events table + audit subscriber · at least one end-to-end WhatsApp workflow · Tally connector with dry-run · Founder snapshot reading only from aggregates.

## 7. Explicit non-goals (won't build, even on request)

No HRMS, payroll, attendance. No CRM (lead capture, sales pipeline, marketing). No form builder. No autonomous AI agents. No ChatGPT-in-a-textbox. No mobile app (WhatsApp is the mobile interface). No multi-region deployment. No realtime collaborative editing. No plugin marketplace.

Each is a credible feature for an ERP and each is how the project dies if we say yes. See [`00-vision.md` § Non-goals](docs/architecture/00-vision.md).

## 8. Known technical debt (full list in [`12-tech-debt-risks.md`](docs/architecture/12-tech-debt-risks.md))

| # | Debt | Plan |
|---|---|---|
| TD-1 | Three-value role enum is too coarse | Replaced Week 1 by full RBAC |
| TD-2 | Static activity feed on dashboard | Replaced by FI subscribers Week 7 |
| TD-3 | Regex-based OCR | Mitigated by human-verify screen Week 3 |
| TD-4 | Missing `.env.example` | Add Week 1 |
| TD-5 | No CI workflow | Add Week 1 |
| TD-6 | Legacy `frontend/LedgerFlow.html` | Delete Week 1 |
| TD-7 | Sparse test coverage | Tests per new module + integration suite Week 8 |
| TD-8 | Auth hardening (verification / reset / revocation) | v2 |
| TD-9 | S3 path unverified against live bucket | MinIO test in CI Week 8 |

## 9. Risks (top 5 — full matrix in [`12-tech-debt-risks.md`](docs/architecture/12-tech-debt-risks.md))

| Risk | Mitigation |
|---|---|
| Modular monolith rots into a ball of mud | `import-linter` in CI Week 8; module-boundary checklist in PR template |
| Custom workflow engine becomes a kitchen sink | Action registry is the only extensibility point; conditions are restricted DSL (no function calls) |
| WhatsApp templates rejected by Meta block a demo | Seed generic templates two weeks before demo; web fallback for every workflow |
| Tally connector breaks for non-standard configs | Dry-run mode; per-tenant XML mapping config; explicit error surface |
| OCR accuracy disappoints in a demo | Always go through human-verify; never auto-push at low confidence; curated demo invoice |

## 10. Placement-interview value (rehearsed Q&A)

The architecture is shaped so these conversations come naturally:

- **"How do you keep two modules from coupling?"** — events; the rules in `02-modules.md`; no cross-module model imports; `import-linter` enforces it.
- **"How does the same authorization work for web and WhatsApp?"** — one `can()` function; both interfaces call it; both write the same audit row with the matched role.
- **"What happens if Tally is down for two hours?"** — workflow step retries with backoff, instance parks, audit shows it, resumes when Tally recovers; we never block the verification flow on Tally.
- **"Why a custom workflow engine and not Temporal?"** — ADR 0003: right-sized, embedded, owned, replaceable behind a thin facade.
- **"Walk me through what happens when a CS rep replies `ESCALATE` on WhatsApp."** — full trace in `09-conversational.md`: webhook → principal → pending-prompt match → RBAC → service → `cs.ticket.escalated` event → workflow creates approval task → FI subscriber increments → notification fires.
- **"What's the riskiest part?"** — the workflow engine. Mitigations: small surface, heavy tests, parked-instance alerting, replaceable behind a facade.

## 11. Immediate next action

**Begin Week 1 of the roadmap** — platform foundations under `app/core/`:

1. Alembic migration: `tenants`, `rbac_roles`, `rbac_permissions`, `rbac_role_permissions`, `rbac_user_roles`, `rbac_approval_chains`, `rbac_approval_steps`, `events`, `audit_log` (rename existing if needed).
2. Seed: default tenant, system roles, full permission catalogue.
3. Build `core/rbac/` — `can()`, `require()` dependency, decision-returning check.
4. Build `core/events/` — in-process bus, durable `events` table writer, subscriber registry.
5. Audit log becomes a subscriber to `*`.
6. Backfill existing `user.role` rows into `rbac_user_roles`.
7. Replace existing `require_admin`/`require_accountant` deps with `require("...")`.
8. Add `.env.example` and a minimal CI workflow (lint + type-check + pytest).

**Exit criterion:** every existing endpoint still works, now gated by the new RBAC; every state change in the existing invoice flow emits an event that appears in both `events` and `audit_log`.

## 12. How a reviewer should read this repo

1. `STATUS.md` (this file) — orientation.
2. [`docs/architecture/00-vision.md`](docs/architecture/00-vision.md) — framing.
3. [`docs/architecture/01-platform-overview.md`](docs/architecture/01-platform-overview.md) — layer diagram.
4. [`docs/architecture/02-modules.md`](docs/architecture/02-modules.md) — what each module owns.
5. Any ADR matching a question you have.
6. The code, by module folder (currently still in the old layout).

---

*This is the orientation document. The architecture in `docs/architecture/` is authoritative. Update this file every time the state of play changes materially.*
