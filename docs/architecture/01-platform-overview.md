# 01 — Platform Overview

## The three layers

Nyx is organized into three horizontal layers. Every line of code lives in exactly one of them.

```
┌─────────────────────────────────────────────────────────────────────┐
│                          INTERFACE LAYER                            │
│  Web Dashboard (Next.js)   WhatsApp Conversation   Email Inbound    │
│  REST/JSON                  Webhook → Intent       IMAP/Webhook     │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         BUSINESS MODULES                            │
│                                                                     │
│   Accounts     Operations    Inventory    Customer    Founder       │
│   (invoices,   (sales,       (stock,      Service     Intelligence  │
│    Tally,      logistics,    transfers,   (tickets,   (KPIs,        │
│    recon)      dispatch)     reorder)     SLAs)       snapshot)     │
│                                                                     │
│   Each module owns its tables, services, routes, workers, events.   │
│   Modules communicate via the event bus or explicit service APIs.   │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                            CORE LAYER                               │
│                                                                     │
│   Identity        RBAC          Audit Log        Notifications      │
│   Workflow Engine  Event Bus     Task System     Approval Chains    │
│   Conversation Runtime           Integration Framework              │
│   Tenant Context  Config Store   Scheduler                          │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│              INFRASTRUCTURE (Postgres, Redis, Worker Pool)          │
└─────────────────────────────────────────────────────────────────────┘
```

## Why this shape

**Interface Layer** is intentionally thin. A web request, a WhatsApp message, and an inbound email all converge on the same internal command surface. We never duplicate business logic per interface.

**Business Modules** are the only place where domain-specific code lives. A module is a bounded context: it owns its tables (prefixed `acc_*`, `ops_*`, `inv_*`, `cs_*`), its services, its workflows, its events. A module **must not** import another module's models or services directly. It either emits an event the other module subscribes to, or it calls a documented service interface exposed by the other module's `__init__.py`.

**Core Layer** is the platform itself. Modules consume it; it does not depend on any module. If the core layer disappears, no module functions. If any single module disappears, the rest keep running.

This separation is what makes the codebase navigable. A reviewer looking at a single module folder can answer: "what does Accounts do, what does it own, what does it depend on?" without holding the whole repo in their head.

## Inter-module communication — the rules

Three rules, no exceptions:

1. **Modules emit events**. When something happens — `InvoiceApproved`, `OrderDispatched`, `TicketEscalated` — the owning module publishes a domain event to the event bus. The module does not know or care who consumes it.

2. **Modules may call other modules' service interfaces** if and only if they need a synchronous, query-style answer. Example: Operations may call `inventory.check_availability(sku, qty)` because dispatch needs to know now. These calls go through a registered service interface, not a raw repository import.

3. **Modules may not read another module's tables**. Ever. This is enforced by code review and is the single biggest discipline that keeps the modular monolith from rotting into a ball of mud.

## What the Core Layer provides

| Service | What it does | Used by |
|---|---|---|
| **Identity** | Users, sessions, JWT, WhatsApp principal mapping | All modules |
| **RBAC** | `can(user, action, resource, scope)` checks; approval chains | All modules; interface guards |
| **Audit Log** | Append-only event journal; subscribed to every domain event | All modules |
| **Event Bus** | Publish/subscribe; in-process for sync, Redis-backed for async | All modules |
| **Workflow Engine** | Loads workflow defs, instantiates instances on events, advances state | All modules |
| **Task System** | Generic `Task` entity any module can create; assigned to a user/role/queue | Operations, Accounts, CS heavily |
| **Notifications** | Sends via web (in-app), WhatsApp, email; respects user preferences | All modules |
| **Conversation Runtime** | Receives WhatsApp messages, resolves intent, routes to workflows | All modules (indirectly) |
| **Integration Framework** | Connector registry (Tally, Shopify, Gmail, Sheets, webhooks) | All modules |
| **Config Store** | Per-tenant configuration: Tally maps, SLA thresholds, templates | All modules |
| **Scheduler** | Time-based triggers; RQ-scheduler for recurring/delayed jobs | Workflow engine, Founder Intel |

## What the Business Modules own

Each module is a self-contained slice:

```
app/modules/<module_name>/
├── __init__.py        # public service interface (what other modules may call)
├── models.py          # SQLAlchemy models, all tables prefixed
├── schemas.py         # Pydantic DTOs
├── repositories.py    # data access
├── services.py        # business logic, the only place that mutates state
├── routes.py          # FastAPI routes, mounted at /api/v1/<module>
├── workers.py         # RQ job handlers
├── events.py          # event types this module emits + handlers it subscribes to
├── workflows/         # YAML/Python workflow definitions
└── config.py          # module-level settings (rarely needed)
```

The module's `__init__.py` exports the **only** symbols other modules may use. Everything else is private.

## The Founder Intelligence module is special

Founder Intelligence is a module by convention but architecturally privileged: it subscribes to **every** event in the system and writes aggregates into its own materialized tables (`fi_daily_snapshot`, `fi_kpi_*`). Its dashboards read only from those aggregates — never directly from other modules' tables. This keeps cross-module read traffic from polluting transactional paths and keeps the read model independently optimisable.

## Request lifecycle (example)

A warehouse picker on WhatsApp replies `DONE` to task #451.

```
1. WhatsApp Cloud API → POST /webhook/whatsapp
2. Conversation Runtime resolves principal from phone number → user_id
3. Intent parser matches "DONE" against open prompts for that user → task_id=451
4. RBAC check: can this user complete this task? (yes)
5. Operations module: task_service.complete(task_id=451, by=user_id)
6. Operations emits TaskCompleted event
7. Workflow Engine: any workflow waiting on TaskCompleted for this task? (yes — stock_transfer)
   → advances workflow to next step (update inventory)
8. Inventory module subscribes to TaskCompleted-for-stock-transfer
   → updates inv_stock_levels
9. Inventory emits StockTransferred
10. Audit Log writes one row per event (TaskCompleted, StockTransferred, WorkflowAdvanced)
11. Notifications: per workflow def, notify operations head → in-app notification
12. Conversation Runtime → outbound WhatsApp: "Task #451 complete. Stock updated."
13. Founder Intelligence subscribes to StockTransferred → increments daily transfer count
```

Notice: the Operations module didn't touch Inventory. Inventory didn't touch Operations. They communicated only through events. Founder Intel didn't poll anything; it was pushed.

This is the architecture working as intended.

## What is explicitly out of scope at this layer

- **No service mesh, no sidecars, no API gateway as a separate process.** FastAPI's own routing is the gateway.
- **No separate read database.** Aggregates live in the same Postgres, in dedicated tables maintained by event handlers.
- **No external workflow engine** (Temporal, Camunda, Airflow). Ours is small and embedded; replacing it later is feasible if we outgrow it.
- **No cross-cutting "framework" code that wraps SQLAlchemy or FastAPI in custom abstractions.** Use the libraries directly.

## How to extend the platform

Adding a new module — say, a `Vendors` module — is intentionally a recipe:

1. Create `app/modules/vendors/` with the standard layout.
2. Define tables with `vnd_*` prefix in `models.py`. Add Alembic migration.
3. Register routes in the v1 router.
4. Declare events in `events.py`. Subscribe to events from other modules if needed.
5. Add workflow definitions for vendor-related flows.
6. Add RBAC permissions to the seed.
7. Done. No other module's code changes.

If adding a module ever requires editing files outside that module's folder + a single line in the router registration, the platform layer has failed and needs to be fixed first.
