# 03 — Folder Structure

This is the target layout. The current finance-centric layout migrates into it incrementally; we do not big-bang rewrite. Migration mapping is at the bottom.

## Backend target layout

```
backend/
├── alembic/
│   ├── env.py
│   └── versions/
│       ├── 0001_initial_schema.py       # existing — kept
│       ├── 0002_platform_core.py        # NEW: tenants, rbac_*, events, workflow_*, tasks, notifications
│       ├── 0003_module_prefix_rename.py # NEW: invoices → acc_invoices, etc.
│       ├── 0004_module_ops.py           # NEW: ops_* tables
│       ├── 0005_module_inventory.py
│       ├── 0006_module_cs.py
│       └── 0007_module_fi.py
│
├── app/
│   ├── main.py                          # FastAPI entry, lifespan, mounts core + modules
│   ├── config.py                        # global settings (existing, mostly unchanged)
│   ├── database.py                      # engine, SessionLocal (existing)
│   │
│   ├── core/                            # THE PLATFORM. No business logic. No module imports.
│   │   ├── __init__.py
│   │   ├── tenants/                     # tenant model, context middleware, scoping helpers
│   │   ├── identity/                    # user, session, JWT, WhatsApp principal mapping
│   │   ├── rbac/                        # roles, permissions, scopes, approval chains
│   │   │   ├── models.py                #   rbac_roles, rbac_permissions, rbac_role_permissions,
│   │   │   │                             #   rbac_user_roles, rbac_approval_chains
│   │   │   ├── service.py               #   can(user, action, resource, scope)
│   │   │   ├── dependencies.py          #   FastAPI deps: require_permission(...)
│   │   │   └── seed.py                  #   default role + permission seed per tenant
│   │   ├── events/                      # the event bus
│   │   │   ├── bus.py                   #   publish(), subscribe(), in-proc + Redis fanout
│   │   │   ├── models.py                #   events table (persisted log)
│   │   │   ├── registry.py              #   declared event types + schemas
│   │   │   └── replay.py                #   replay events to a single subscriber
│   │   ├── audit/                       # the audit log subscriber
│   │   │   ├── models.py                #   audit_log
│   │   │   ├── service.py
│   │   │   └── subscriber.py            #   wired in main.py: subscribes to '*'
│   │   ├── tasks/                       # generic Task entity (created by any module)
│   │   │   ├── models.py                #   tasks, task_assignments, task_prompts
│   │   │   ├── service.py
│   │   │   └── routes.py                #   /api/v1/tasks
│   │   ├── workflows/                   # the workflow engine
│   │   │   ├── models.py                #   workflow_definitions, workflow_instances, workflow_steps
│   │   │   ├── dsl.py                   #   parse YAML/python defs
│   │   │   ├── runner.py                #   advance(instance, event)
│   │   │   ├── conditions.py            #   safe expression evaluator
│   │   │   ├── actions.py               #   action registry (emit_event, create_task, send_notification, ...)
│   │   │   └── routes.py                #   /api/v1/workflows
│   │   ├── notifications/
│   │   │   ├── models.py                #   notifications, notification_preferences
│   │   │   ├── service.py
│   │   │   ├── channels/                #   in_app.py, whatsapp.py, email.py
│   │   │   └── templates.py
│   │   ├── conversation/                # WhatsApp / email inbound runtime
│   │   │   ├── models.py                #   conversations, conv_messages, conv_pending_prompts
│   │   │   ├── webhook.py               #   POST /webhook/whatsapp
│   │   │   ├── intent.py                #   rule-based parser (DONE / APPROVE / etc.)
│   │   │   ├── classifier.py            #   LLM-based free-text classifier (optional)
│   │   │   ├── runtime.py               #   ties webhook → intent → workflow runner
│   │   │   └── outbound.py              #   templated outbound + delivery
│   │   ├── integrations/                # connector framework + registry
│   │   │   ├── base.py                  #   Connector ABC, ConnectorConfig
│   │   │   ├── registry.py
│   │   │   ├── tally/
│   │   │   ├── shopify/
│   │   │   ├── gmail/
│   │   │   ├── outlook/
│   │   │   ├── whatsapp/                #   meta cloud api client (used by conversation.outbound)
│   │   │   ├── sheets/
│   │   │   └── webhook/                 #   generic inbound webhook adapter
│   │   ├── scheduler/                   # time-based triggers (rq-scheduler wrapper)
│   │   ├── config_store/                # per-tenant config (k/v with JSONB)
│   │   ├── security.py                  # password hashing, JWT utils (existing)
│   │   ├── exceptions.py                # platform-wide exception types
│   │   ├── logging.py                   # structlog config (existing)
│   │   ├── limiter.py                   # slowapi (existing)
│   │   └── middleware.py                # request logging + tenant context (existing extended)
│   │
│   ├── modules/                         # THE BUSINESS. One folder per bounded context.
│   │   ├── __init__.py
│   │   ├── accounts/
│   │   │   ├── __init__.py              # public service interface
│   │   │   ├── models.py                # acc_invoices, acc_vendors, acc_reconciliation_records, ...
│   │   │   ├── schemas.py
│   │   │   ├── repositories.py
│   │   │   ├── services.py              # invoice_service, recon_service, tally_service
│   │   │   ├── ocr.py                   # the OCR pipeline (was services/ocr_service.py)
│   │   │   ├── routes.py                # /api/v1/accounts/*
│   │   │   ├── workers.py               # RQ jobs (OCR, reconcile, tally push)
│   │   │   ├── events.py                # publish + subscribe wiring
│   │   │   ├── workflows/               # YAML defs: invoice_lifecycle.yaml, founder_approval.yaml
│   │   │   └── tests/
│   │   ├── operations/
│   │   │   ├── __init__.py
│   │   │   ├── models.py                # ops_orders, ops_dispatches, ...
│   │   │   ├── schemas.py
│   │   │   ├── repositories.py
│   │   │   ├── services.py
│   │   │   ├── routes.py
│   │   │   ├── workers.py
│   │   │   ├── events.py
│   │   │   ├── workflows/
│   │   │   └── tests/
│   │   ├── inventory/
│   │   ├── customer_service/
│   │   └── founder_intelligence/
│   │       ├── models.py                # fi_daily_snapshot, fi_kpi_*
│   │       ├── subscribers.py           # one handler per upstream event
│   │       ├── services.py              # read APIs only
│   │       ├── routes.py
│   │       └── snapshot_job.py          # nightly job
│   │
│   └── api/
│       └── v1/
│           └── router.py                # composes core + module routers
│
├── docker/
│   ├── Dockerfile
│   └── Dockerfile.worker
├── docker-compose.yml
├── docker-compose.prod.yml
├── tests/                               # cross-cutting integration tests
├── pytest.ini
├── requirements.txt
└── README.md
```

## Frontend target layout

```
frontend/
├── app/
│   ├── (auth)/login/
│   ├── (dashboard)/
│   │   ├── layout.tsx                   # Sidebar with module-grouped nav
│   │   ├── page.tsx                     # Founder snapshot
│   │   ├── accounts/                    # invoices, vendors, reconciliation, tally config
│   │   ├── operations/                  # orders, dispatches, channels
│   │   ├── inventory/                   # stock, transfers, warehouses
│   │   ├── customer-service/            # tickets, customers, templates
│   │   ├── workflows/                   # workflow defs, instances, approvals queue
│   │   ├── approvals/                   # approval inbox across modules
│   │   ├── analytics/                   # founder intelligence detail views
│   │   └── settings/                    # users, roles, integrations, config
│   ├── layout.tsx
│   ├── providers.tsx
│   └── globals.css
│
├── components/
│   ├── shell/                           # Sidebar, Topbar, ModuleSwitcher
│   ├── ui/                              # primitives
│   ├── charts/
│   ├── tasks/                           # TaskCard, TaskList, TaskInbox
│   ├── workflows/                       # WorkflowDefinitionEditor, WorkflowInstanceTrace
│   ├── approvals/                       # ApprovalRow, ApprovalDecisionPanel
│   └── modules/
│       ├── accounts/
│       ├── operations/
│       ├── inventory/
│       ├── customer-service/
│       └── founder-intelligence/
│
├── services/                            # axios clients, one per module + per core capability
│   ├── core/
│   │   ├── auth.service.ts
│   │   ├── rbac.service.ts
│   │   ├── tasks.service.ts
│   │   ├── workflows.service.ts
│   │   ├── notifications.service.ts
│   │   └── integrations.service.ts
│   └── modules/
│       ├── accounts.service.ts
│       ├── operations.service.ts
│       ├── inventory.service.ts
│       ├── customer-service.service.ts
│       └── founder-intelligence.service.ts
│
├── hooks/                               # mirrors services/
├── store/                               # zustand: auth, ui (sidebar collapsed, theme), tenant
├── lib/                                 # api.ts, utils.ts
├── types/api.ts                         # generated from OpenAPI (future: codegen)
└── middleware.ts                        # route guard + tenant header
```

## Migration from current layout

The existing repo is organized by **technical layer** (`models/`, `services/`, `repositories/`, `api/v1/`). We migrate to **organized by module** without big-bang rewrites.

### Move-map

| Current path | Destination |
|---|---|
| `app/models/invoice.py`, `invoice_item.py`, `vendor.py`, `reconciliation.py`, `processing_job.py` | `app/modules/accounts/models.py` |
| `app/models/user.py` | `app/core/identity/models.py` |
| `app/models/audit_log.py` | `app/core/audit/models.py` |
| `app/services/invoice_service.py`, `reconciliation_service.py`, `vendor_service.py`, `ocr_service.py`, `storage_service.py` | `app/modules/accounts/services.py` (+ `ocr.py`) |
| `app/services/auth_service.py` | `app/core/identity/service.py` |
| `app/services/dashboard_service.py` | `app/modules/founder_intelligence/services.py` |
| `app/repositories/*` | move into respective `modules/*/repositories.py` or `core/*/repositories.py` |
| `app/api/v1/auth.py` | `app/core/identity/routes.py` |
| `app/api/v1/invoices.py`, `vendors.py`, `reconciliation.py` | `app/modules/accounts/routes.py` |
| `app/api/v1/audit.py` | `app/core/audit/routes.py` |
| `app/api/v1/dashboard.py` | `app/modules/founder_intelligence/routes.py` |
| `app/workers/invoice_processor.py`, `reconciliation_worker.py`, `queue.py` | `queue.py` → `app/core/events/` (sort of) + workers → `app/modules/accounts/workers.py` |
| `app/core/{security, exceptions, logging, middleware, limiter}.py` | stays in `app/core/` (already correct) |

### Migration order (one Alembic migration per step, no skipping)

1. **0002 — Platform core tables.** Create `tenants`, `rbac_*`, `events`, `workflow_*`, `tasks`, `notifications`, `conversations`, `integrations_config`. No existing tables touched.
2. **0003 — Module prefix rename.** Rename `invoices` → `acc_invoices`, `vendors` → `acc_vendors`, etc., via `RENAME TABLE`. Update model `__tablename__`. Audit and user tables stay unprefixed (they're core).
3. **0004+ — New module tables** for Operations, Inventory, CS, FI as those modules come online.

The code reorganization happens at the same time as 0003 — it's the natural moment to move files. We don't change SQL data, only renames.

### Backward compatibility

The existing API surface stays. `POST /api/v1/invoices` continues to work, now served from `app/modules/accounts/routes.py`. We do not break clients. Adding `/api/v1/accounts/invoices` as a new canonical path is acceptable; the old paths get redirected via FastAPI route aliases.

## What a reviewer should be able to do with this layout

- Open `app/modules/<anything>/` and read it top-to-bottom in one sitting and understand that module.
- Open `app/core/` and find every piece of infrastructure in a named subdirectory.
- Grep for `from app.modules.X import` from outside `app/modules/X/` and find zero hits except in `app/api/v1/router.py`.
- Add a new module by copying any existing module folder, editing names, registering the router. No surgery elsewhere.

If any of those becomes impossible, the structure has rotted and we fix it before adding features.
