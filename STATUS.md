# Nyx — Project Status Document

**Date:** 2026-06-19
**Repository:** `C:\Users\shrey\Desktop\Dump\Nyx`
**Branch:** `main`
**Owner:** Shreyash Thakur (admin@nashermiles.com)

> **This is a repositioning checkpoint.** Nyx is no longer a "Finance Operations & Invoice Reconciliation Platform." It is becoming a **Modular Internal Business Operations Platform** for Indian SMEs (20–500 employees). The existing finance/invoice work becomes one module (`Accounts`) within a five-module platform.
>
> **The architecture is documented in full at [`docs/architecture/`](docs/architecture/).** Read [00-vision.md](docs/architecture/00-vision.md) first.

---

## 1. What Nyx is now

A **Modular Internal Business Operations Platform** — a configurable ERP-like operating system for SMEs where each department manages workflows through a shared platform. Think Odoo + Monday + Airtable, sized and priced for an Indian SME of 20–500 people, opinionated for D2C/eCommerce operations, **WhatsApp-native** because that's how Indian operations teams actually work.

Not competing with SAP / Odoo Enterprise / NetSuite. Winning by being smaller, opinionated, WhatsApp-native, and Tally-friendly.

## 2. Platform shape (three layers)

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

## 3. Modules

| Module | Code | Purpose | Status |
|---|---|---|---|
| **Accounts** | `acc` | Invoice OCR, reconciliation, Tally push, vendor master | **Largely built**; needs reorg into `app/modules/accounts/` and renaming of tables |
| **Operations** | `ops` | Orders (Shopify/Amazon/Flipkart), dispatches, logistics, returns | Designed; not yet built |
| **Inventory** | `inv` | SKUs, warehouses, stock levels, transfers, reservations, reorder | Designed; not yet built |
| **Customer Service** | `cs` | Tickets, SLAs, escalations, templates, customer history | Designed; not yet built |
| **Founder Intelligence** | `fi` | Cross-module aggregates, daily snapshot, alerts | Designed; not yet built |

## 4. Core platform capabilities (what every module consumes)

| Capability | What it does | Design doc |
|---|---|---|
| Identity & Tenants | Users, sessions, JWT, phone-claim for WhatsApp principals | [00, 08-ADR](docs/architecture/adr/0008-tenant-id-everywhere.md) |
| RBAC | `can(user, action, resource, *, tenant_id)` — same check for web + WhatsApp + workers; approval chains | [07-rbac.md](docs/architecture/07-rbac.md) |
| Audit Log | Append-only event journal; subscribes to every domain event | [05-event-bus.md](docs/architecture/05-event-bus.md) |
| Event Bus | Two-tier: in-process sync + Redis async; durable `events` table; replayable | [05-event-bus.md](docs/architecture/05-event-bus.md) |
| Workflow Engine | YAML-defined, trigger/condition/action; runs identically from web/event/WhatsApp/schedule | [06-workflow-engine.md](docs/architecture/06-workflow-engine.md) |
| Task System | Generic `Task` entity any module creates; assignable; surfaced via web or WhatsApp | covered in 02, 06 |
| Notifications | In-app, WhatsApp, email; preference-aware | covered in 09 |
| Conversation Runtime | WhatsApp inbound → principal → intent → workflow; **rule-first, LLM only as fallback** | [09-conversational.md](docs/architecture/09-conversational.md), [07-ADR](docs/architecture/adr/0007-rules-first-llm-fallback.md) |
| Integration Framework | Connector ABC; Tally, Shopify, Amazon, Flipkart, Gmail, Outlook, Sheets, WhatsApp, webhooks | [08-integrations.md](docs/architecture/08-integrations.md) |

## 5. Key architectural decisions (one-liners)

- **Modular monolith**, not microservices. One deployable, one DB, boundaries in code. [ADR 0001](docs/architecture/adr/0001-modular-monolith-over-microservices.md)
- **In-process event bus** with Redis fanout for slow handlers. No Kafka. Durable `events` table for replay. [ADR 0002](docs/architecture/adr/0002-in-process-event-bus.md)
- **Custom embedded workflow engine** (YAML defs, ~500 LOC runner). Not Temporal/Camunda. Replaceable behind a facade. [ADR 0003](docs/architecture/adr/0003-custom-workflow-engine.md)
- **Application-layer RBAC**, not Postgres RLS. Multi-dimensional scopes (tenant × department × warehouse × ownership) + observable Decision objects. [ADR 0004](docs/architecture/adr/0004-app-layer-rbac-no-rls.md)
- **Single Postgres** with FI materialized aggregates fed by event subscribers. Not CQRS-with-separate-read-DB; not event-sourcing as primary. [ADR 0005](docs/architecture/adr/0005-single-postgres-no-cqrs.md)
- **WhatsApp is a primary UI**, equivalent in capability to the web. Same RBAC, same audit. [ADR 0006](docs/architecture/adr/0006-whatsapp-as-primary-ui.md)
- **Rule-based intents** for deterministic actions (`DONE/APPROVE/REJECT/...`). LLM only as fallback for fuzzy free-text classification. [ADR 0007](docs/architecture/adr/0007-rules-first-llm-fallback.md)
- **Tenant-aware schema from day one**; tenant onboarding flow deferred to v2. [ADR 0008](docs/architecture/adr/0008-tenant-id-everywhere.md)

## 6. Tech stack (unchanged; choices defended in ADRs)

**Backend:** Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, PostgreSQL 16, Redis 7, RQ, pytesseract+pdf2image, python-jose JWT, passlib+bcrypt, slowapi, structlog, pytest.

**Frontend:** Next.js 15 App Router, React 19, TanStack Query, Zustand, Tailwind, Radix, Recharts, framer-motion, axios.

**Infra:** Docker Compose dev + prod overlay; deploy targets Render / Railway.

## 7. Current code state

### What exists today
- The Accounts module's functionality (under the old `app/services/`, `app/models/`, `app/api/v1/` layout):
  - Invoice upload + SHA-256 dedup, OCR pipeline, reconciliation engine, audit logging, dashboard endpoints, Tally generation in progress.
- JWT auth (access + refresh), 3-value role enum (about to be replaced).
- structlog logging, slowapi rate-limited login, healthcheck endpoint.
- Alembic baseline migration, Docker Compose dev stack with API + worker + RQ Dashboard + frontend.
- Frontend: Next.js scaffold for `(auth)` + `(dashboard)` route groups with module-prep pages (some still empty), TanStack Query hooks, Zustand auth store, axios JWT interceptor.

### What does not exist yet
- The Core layer (tenants, new RBAC, event bus, workflow engine, task system, conversation runtime, integration framework) — all designed in `docs/architecture/`, no code.
- Operations, Inventory, Customer Service, Founder Intelligence modules — only designed.
- WhatsApp connector + conversation runtime.
- Tally connector (XML mapping + push) as a proper connector under the new framework.
- Founder snapshot aggregates and dashboard wired to real events (current dashboard mixes API + static data).
- CI workflow, `.env.example`, broader test coverage, multi-tenant onboarding flow.

## 8. 8-week roadmap (summary; full plan in [11-roadmap.md](docs/architecture/11-roadmap.md))

| Week | Goal | Exit criterion |
|---|---|---|
| 1 | Platform foundations: tenants, RBAC, events, audit | Existing endpoints work under new RBAC; every state change emits an event |
| 2 | Workflow engine + Tasks | Invoice lifecycle runs as a declarative workflow, not chained service calls |
| 3 | Module reorg + Accounts cleanup + Tally dry-run | All Accounts code under `app/modules/accounts/`; Tally XML viewable on a human-verify screen |
| 4 | Conversational layer (WhatsApp) | Founder approves an invoice via WhatsApp; rule-based intents work end-to-end |
| 5 | Operations module (orders + dispatches) | Shopify order → dispatch task → warehouse staff `DONE` on WhatsApp → inventory decrement |
| 6 | Inventory module + Customer Service skeleton | Stock transfer end-to-end via WhatsApp; ticket lifecycle exists |
| 7 | Founder Intelligence | Snapshot page reads only from aggregates; WhatsApp daily summary fires |
| 8 | Hardening, observability, demo polish | `import-linter` passes; all canonical flow tests green; 12-minute demo script captured |

**MVP demo (week 8) shows:**
1. Login + module-grouped navigation
2. Invoice upload → OCR → human verify → reconcile → Tally XML
3. Founder-approval workflow firing on threshold, approved via WhatsApp
4. WhatsApp `DONE` on a stock-transfer task completing the workflow + updating inventory
5. Founder Snapshot page fed by event subscribers
6. Audit log showing every event + matched permission

## 9. What is explicitly out of scope

No HRMS, payroll, attendance. No CRM (lead capture, sales pipeline). No general-purpose form builder. No autonomous AI agents. No mobile app (WhatsApp is the mobile interface). No internal scripting language richer than the workflow DSL. No multi-region deployment. No realtime collaborative editing. No third-party plugin marketplace.

Each of these is a credible feature for an ERP. Each is also how this project dies if we say yes. See [00-vision.md § Non-goals](docs/architecture/00-vision.md).

## 10. Known technical debt (pre-redesign)

Tracked in full at [12-tech-debt-risks.md](docs/architecture/12-tech-debt-risks.md). Highlights:

- **TD-1** Three-value role enum is too coarse → replaced Week 1.
- **TD-2** Static activity feed on dashboard → replaced by FI subscribers Week 7.
- **TD-3** Regex-based OCR → mitigated by human-verify screen Week 3.
- **TD-4** Missing `.env.example` → fixed Week 1.
- **TD-5** No CI workflow → added Week 1.
- **TD-6** Legacy `frontend/LedgerFlow.html` → deleted.
- **TD-7** Sparse test coverage → every new module ships tests; Week 8 integration suite.
- **TD-8** Auth hardening (verification, reset, revocation) — acknowledged, v2.

## 11. How to read this repository

For a reviewer (engineering manager, interviewer, future contributor) the recommended path:

1. This file (`STATUS.md`).
2. [`docs/architecture/00-vision.md`](docs/architecture/00-vision.md) — the framing.
3. [`docs/architecture/01-platform-overview.md`](docs/architecture/01-platform-overview.md) — the layer diagram.
4. [`docs/architecture/02-modules.md`](docs/architecture/02-modules.md) — what each module owns.
5. Any ADR matching a question you have (`docs/architecture/adr/`).
6. The code, by module folder.

## 12. Placement-interview value

The architecture is designed to make these interview conversations natural:

- *"How do you keep two modules from coupling?"* → events; the `02-modules.md` rules; no cross-module model imports.
- *"How does the same authorization work for web and WhatsApp?"* → one `can()` function; both interfaces call it; both write the same audit row.
- *"What happens if Tally is down for two hours?"* → workflow step retries with backoff, instance parks, audit shows it, resumes when Tally recovers.
- *"Why a custom workflow engine and not Temporal?"* → ADR 0003.
- *"Walk me through what happens when a CS rep replies `ESCALATE` on WhatsApp."* → end-to-end trace in [09-conversational.md](docs/architecture/09-conversational.md).
- *"What's the riskiest part?"* → the workflow engine; mitigations documented in [12-tech-debt-risks.md](docs/architecture/12-tech-debt-risks.md).

The architecture is the artefact. Everything below it is implementation.

---

*This document is the orientation for the project as of 2026-06-19. The detailed architecture in `docs/architecture/` is authoritative; this file is the index.*
