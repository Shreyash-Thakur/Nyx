# 04 — Database

This document is the single source of truth for the Nyx database design. It is opinionated and prescriptive: contributors do not invent new conventions, they follow these.

The target engine is **PostgreSQL 15+**, deployed as a single database, single schema (`public`), accessed through SQLAlchemy 2.x and migrated by Alembic. Redis is in the stack but is not a database in the persistence sense — it is the broker for RQ and the fanout transport for the event bus. Anything that needs to survive a Redis flush lives in Postgres.

---

## 1. Naming convention

The schema is large enough that naming is load-bearing. A reviewer scanning `\dt` should be able to tell from the table name which module owns it, without opening any code.

### 1.1 Table prefixes

| Layer       | Prefix      | Examples                                                      |
|-------------|-------------|---------------------------------------------------------------|
| Core        | *(none)*    | `tenants`, `users`, `events`, `tasks`, `audit_log`            |
| Accounts    | `acc_`      | `acc_invoices`, `acc_vendors`, `acc_reconciliation_records`   |
| Operations  | `ops_`      | `ops_orders`, `ops_dispatches`, `ops_channels`                |
| Inventory   | `inv_`      | `inv_skus`, `inv_stock_levels`, `inv_transfers`               |
| Customer Service | `cs_`  | `cs_tickets`, `cs_ticket_messages`, `cs_sla_policies`         |
| Founder Intelligence | `fi_` | `fi_daily_snapshot`, `fi_kpi_dispatch_cycle_time`         |

Rules:

1. **Core tables are unprefixed.** They are platform primitives. Every module reads/writes them through core services. Prefixing them would imply ownership where there is none.
2. **Every business-data table carries a module prefix.** No exceptions. If a table is hard to prefix because it spans modules, the table is wrong — split it or hoist it to core.
3. **Prefixes are three letters + underscore.** Short, predictable, scriptable.
4. **Pluralize the noun**: `acc_invoices`, not `acc_invoice`. Join tables pluralize both sides: `rbac_role_permissions`.
5. **Audit log is singular** (`audit_log`) because it is conceptually a single append-only log, not a collection of distinct rows the application treats as entities.

### 1.2 Column naming

| Rule | Example |
|---|---|
| `snake_case`, ASCII, lowercase. | `total_amount`, `created_at` |
| Booleans named as predicates. | `is_active`, `is_locked`, `is_system_role` |
| Timestamps end in `_at`. | `created_at`, `verified_at`, `tally_pushed_at` |
| Dates (no time) end in `_date`. | `invoice_date`, `due_date` |
| FK columns are `<referenced_singular>_id`. | `tenant_id`, `vendor_id`, `uploaded_by` (exception: actor refs use the role word) |
| JSONB blobs end in `_data`, `_payload`, or `_config`. | `extra_data`, `event_payload`, `tally_config` |
| Money columns are `NUMERIC(14, 2)`, never `FLOAT`. | `total_amount`, `discrepancy_amount` |
| Enum-typed columns reuse the enum name. | `status invoice_status NOT NULL` |
| Avoid abbreviations. `description`, not `desc`. `quantity`, not `qty` *(except column names that mirror an external API field name)*. | |

### 1.3 Foreign key naming

Constraint names are explicit, never auto-generated. The convention is:

```
fk_<table>__<column>__<referenced_table>
```

Examples:

```
fk_acc_invoices__tenant_id__tenants
fk_acc_invoices__vendor_id__acc_vendors
fk_acc_invoices__uploaded_by__users
fk_rbac_user_roles__role_id__rbac_roles
```

Index names follow:

```
ix_<table>__<col1>[_<col2>...]      -- regular index
ux_<table>__<col1>[_<col2>...]      -- unique index
```

Check constraint names:

```
ck_<table>__<short_predicate>
```

This naming makes Alembic diffs readable and prevents the `ix_invoices_invoice_status_8a3f` autogen sludge from accumulating.

### 1.4 Enum types

Postgres enum types are named `<module>_<concept>` for module-owned enums and just `<concept>` for core enums:

| Enum type                          | Owner    |
|------------------------------------|----------|
| `invoice_status`                   | acc      |
| `payment_status`                   | acc      |
| `reconciliation_status`            | acc      |
| `dispatch_status`                  | ops      |
| `ticket_status`                    | cs       |
| `task_status`, `task_priority`     | core     |
| `event_delivery_status`            | core     |
| `notification_channel`             | core     |

Enums are created with `create_type=False` at the SQLAlchemy level — the canonical create lives in the Alembic migration. This avoids the "type already exists" race during test setup and matches what `0001_initial_schema.py` already does.

---

## 2. Tenant strategy

Nyx is single-tenant in deployment today and multi-tenant in schema. We pick the strategy that makes that transition cheap.

### 2.1 Decision: shared DB, shared schema, `tenant_id` column

We use a **single Postgres database, single schema, with a mandatory `tenant_id UUID NOT NULL` column on every business-data table**, scoped at the service/repository layer.

Rejected alternatives:

| Alternative              | Why rejected                                                                                                                                       |
|--------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------|
| Schema-per-tenant        | Migrations multiply by N. Cross-tenant analytics become DDL gymnastics. We are not selling to regulated industries that demand schema isolation.   |
| Database-per-tenant      | Operationally painful at 20 tenants, suicidal at 200. No tenant in our target market justifies it.                                                  |
| Postgres Row-Level Security (RLS) | See below — we reject it explicitly.                                                                                                       |

### 2.2 Why not Postgres RLS

Postgres RLS is technically attractive: enforce `tenant_id = current_setting('app.tenant_id')` once, at the database, and never worry about a service forgetting a `WHERE` clause.

We do not use it because:

1. **Connection pooling complicates session-state.** PgBouncer in transaction mode (which we want for FastAPI workloads) does not pin a backend per app-connection. `SET LOCAL app.tenant_id` works inside one transaction, but the pattern is fragile and easy to get wrong, especially with RQ workers that do not own a clean per-request scope.
2. **Service-layer enforcement is testable.** A `TenantScopedRepository.list()` that injects `tenant_id` is unit-testable. An RLS policy violation surfaces as an empty resultset, which is the worst failure mode — it looks like correct behavior.
3. **Migrations and ad-hoc admin queries get harder.** RLS bypass requires `BYPASSRLS` roles. Every operational query becomes a question of "which role am I connected as?"
4. **We have an audit log subscribed to every event.** A bug that leaks tenant data is recoverable and observable; the audit log will show whose tenant context wrote it. The damage radius of an RLS bypass mistake is bounded.
5. **We will revisit RLS only when we have multi-tenant production traffic and a security audit asks for defense-in-depth.** Until then, it is one more thing to misconfigure.

### 2.3 How scoping actually works

- Every authenticated request resolves a `TenantContext` in middleware (`app/core/middleware.py`), populated from the JWT's `tenant_id` claim.
- The `BaseRepository` accepts a `tenant_id` and injects it into every read and write. There is no `Repository.unsafe_list_all()`.
- Workers receive `tenant_id` as part of the job payload and rehydrate context before running.
- A code-review rule (eventually a lint check) forbids constructing a `Session.query(Model)` outside a tenant-scoped repository, with the exception of the `tenants`, `users`, and `audit_log` tables, which have intentional cross-tenant paths (login, super-admin, forensics).

### 2.4 Index strategy for `tenant_id`

- Every business-data table has `tenant_id` as the **leading column** of its primary access-pattern index. For most tables this is `(tenant_id, status)` or `(tenant_id, created_at DESC)`.
- We do **not** index `tenant_id` alone; the cardinality is too low at 1 tenant and even at 50 tenants the planner will prefer the composite.
- FK indexes from `tenant_id` to `tenants(id)` are declared but the column is never queried by FK lookup at scale — the index exists for referential-integrity scans during deletes.

---

## 3. Primary key and timestamp convention

### 3.1 Primary keys

**UUID v4, generated client-side** (Python `uuid.uuid4()` via the `UUIDMixin` in `app/core/models/base.py`).

Rationale:

- No integer-leakage in URLs. `/api/v1/accounts/invoices/8a3f...` does not expose row counts.
- IDs are generatable before insert, which simplifies the event payload pattern (we emit `InvoiceUploaded` containing the invoice ID, then insert — or vice versa with the same value).
- Multi-tenant data merges across deployments stay collision-free.
- The 16-byte storage cost is irrelevant at our scale and the index-locality argument against UUIDs is a red herring for OLTP workloads with <100M rows per table.

We do **not** use UUIDv7 today. We will switch when SQLAlchemy + asyncpg + alembic all support it without a custom type, which as of this writing they do not cleanly.

### 3.2 Timestamps

Every table has:

```sql
created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
```

- Always `TIMESTAMPTZ`. Postgres stores it as UTC; the timezone metadata is for the driver. Application code converts to user-local at display time only.
- `updated_at` is maintained by a Postgres trigger, not by application code. This is non-negotiable because RQ workers, raw `UPDATE` migrations, and admin SQL all need to bump it correctly.

The trigger is installed once in migration `0002`:

```sql
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

Every table gets an `AFTER ... BEFORE UPDATE` trigger attached in its create migration. The Alembic helper `op.execute("CREATE TRIGGER ...")` is wrapped in a Python function so all tables call `attach_updated_at_trigger(table_name)`.

### 3.3 Event timestamps

Domain-specific timestamps (`tally_pushed_at`, `verified_at`, `resolved_at`) are explicit columns. We do **not** stuff lifecycle timestamps into JSONB. They get indexed; they get queried; they earn their column.

---

## 4. Core tables

These tables live in the unprefixed core namespace. Every column is annotated. `id` (UUID PK) and `created_at` / `updated_at` (TIMESTAMPTZ) are implicit on every table and not repeated below unless they are notable.

### 4.1 `tenants`

| Column                | Type           | Notes                                                          |
|-----------------------|----------------|----------------------------------------------------------------|
| `slug`                | `VARCHAR(64)`  | URL-safe handle, unique. Used in subdomain routing later.      |
| `display_name`        | `VARCHAR(200)` |                                                                |
| `legal_name`          | `VARCHAR(300)` | For invoices, Tally master.                                    |
| `gstin`               | `VARCHAR(15)`  | Nullable — non-GST tenants exist.                              |
| `pan`                 | `VARCHAR(10)`  |                                                                |
| `country_code`        | `CHAR(2)`      | ISO-3166-1 alpha-2. `IN` for now.                              |
| `default_currency`    | `CHAR(3)`      | `INR`.                                                          |
| `default_timezone`    | `VARCHAR(64)`  | `Asia/Kolkata`.                                                |
| `plan_tier`           | `VARCHAR(32)`  | `internal` / `starter` / `growth`. Used by feature flags.      |
| `is_active`           | `BOOLEAN`      | Default `TRUE`. Soft-delete signal.                            |
| `deactivated_at`      | `TIMESTAMPTZ`  | NULL when active.                                              |
| `settings`            | `JSONB`        | Free-form per-tenant settings — limited use; prefer `config_store`. |

Indexes: `ux_tenants__slug`.

### 4.2 `users`

| Column            | Type           | Notes                                                              |
|-------------------|----------------|--------------------------------------------------------------------|
| `tenant_id`       | `UUID`         | FK → `tenants(id)`. NOT NULL.                                       |
| `email`           | `VARCHAR(255)` | Unique per tenant (`ux_users__tenant_id__email`).                  |
| `phone_e164`      | `VARCHAR(20)`  | Mandatory for WhatsApp principal mapping. Unique per tenant.       |
| `full_name`       | `VARCHAR(200)` |                                                                    |
| `password_hash`   | `VARCHAR(255)` | bcrypt.                                                            |
| `is_active`       | `BOOLEAN`      | Default `TRUE`.                                                    |
| `deactivated_at`  | `TIMESTAMPTZ`  | Soft-delete marker. See §8.                                        |
| `last_login_at`   | `TIMESTAMPTZ`  |                                                                    |
| `failed_login_count` | `INTEGER`   | Default 0; reset on success.                                       |
| `locked_until`    | `TIMESTAMPTZ`  | NULL unless locked.                                                |
| `preferences`     | `JSONB`        | UI prefs only. Notification prefs live in `notification_preferences`. |

Indexes: `ux_users__tenant_id__email`, `ux_users__tenant_id__phone_e164`, `ix_users__tenant_id`.

### 4.3 `rbac_roles`

| Column            | Type           | Notes                                                                  |
|-------------------|----------------|------------------------------------------------------------------------|
| `tenant_id`       | `UUID`         | NULL means a global / system role (e.g. `super_admin`).                |
| `code`            | `VARCHAR(64)`  | `founder`, `accounts_head`, `warehouse_picker`. Unique per tenant.     |
| `display_name`    | `VARCHAR(200)` |                                                                        |
| `description`     | `TEXT`         |                                                                        |
| `is_system_role`  | `BOOLEAN`      | TRUE for roles seeded by the platform; not editable in UI.             |

Indexes: `ux_rbac_roles__tenant_id__code`.

### 4.4 `rbac_permissions`

| Column          | Type           | Notes                                                                                                            |
|-----------------|----------------|------------------------------------------------------------------------------------------------------------------|
| `code`          | `VARCHAR(128)` | Globally unique: `accounts.invoice.approve`, `inventory.stock.adjust`, `core.user.create`.                       |
| `module`        | `VARCHAR(32)`  | `accounts`, `operations`, `inventory`, `customer_service`, `founder_intelligence`, `core`.                       |
| `resource`      | `VARCHAR(64)`  | `invoice`, `stock`, `user`.                                                                                      |
| `action`        | `VARCHAR(32)`  | `create`, `read`, `update`, `delete`, `approve`, `push`.                                                          |
| `description`   | `TEXT`         |                                                                                                                  |

Permissions are global (no `tenant_id`) because the *catalogue* of what is grantable is platform-wide. **Grants** are tenant-scoped via `rbac_user_roles`.

Indexes: `ux_rbac_permissions__code`, `ix_rbac_permissions__module`.

### 4.5 `rbac_role_permissions`

| Column          | Type    | Notes                                                              |
|-----------------|---------|--------------------------------------------------------------------|
| `role_id`       | `UUID`  | FK → `rbac_roles(id)` ON DELETE CASCADE.                           |
| `permission_id` | `UUID`  | FK → `rbac_permissions(id)` ON DELETE CASCADE.                     |
| `scope`         | `JSONB` | Optional scope predicate, e.g. `{"warehouse_id": "..."}`. NULL = unscoped (role-wide). |

PK is `(role_id, permission_id, COALESCE(scope, '{}'::jsonb))`. Practically, we use a surrogate UUID PK and a `ux_rbac_role_permissions__role_id__permission_id` partial unique index for the NULL-scope case.

### 4.6 `rbac_user_roles`

| Column         | Type    | Notes                                                                  |
|----------------|---------|------------------------------------------------------------------------|
| `user_id`      | `UUID`  | FK → `users(id)` ON DELETE CASCADE.                                    |
| `role_id`      | `UUID`  | FK → `rbac_roles(id)` ON DELETE CASCADE.                               |
| `scope`        | `JSONB` | Per-grant scope override. Composes with role-permission scope.         |
| `granted_by`   | `UUID`  | FK → `users(id)`. Audit-trail metadata.                                 |
| `granted_at`   | `TIMESTAMPTZ` |                                                                  |
| `expires_at`   | `TIMESTAMPTZ` | NULL = permanent.                                                |

Indexes: `ux_rbac_user_roles__user_id__role_id` (partial, where `expires_at IS NULL OR expires_at > now()` — enforced at insert time, not as a DB partial index, because partial-with-`now()` is non-immutable).

### 4.7 `rbac_approval_chains`

| Column         | Type           | Notes                                                                            |
|----------------|----------------|----------------------------------------------------------------------------------|
| `tenant_id`    | `UUID`         | NOT NULL.                                                                        |
| `code`         | `VARCHAR(64)`  | `invoice_above_50k`, `stock_writeoff`. Unique per tenant.                        |
| `display_name` | `VARCHAR(200)` |                                                                                  |
| `trigger`      | `JSONB`        | Declarative trigger: `{"event": "acc.invoice.verified", "where": {"total_amount.gte": 50000}}` |
| `is_active`    | `BOOLEAN`      |                                                                                  |

### 4.8 `rbac_approval_steps`

| Column                 | Type           | Notes                                                                |
|------------------------|----------------|----------------------------------------------------------------------|
| `chain_id`             | `UUID`         | FK → `rbac_approval_chains(id)` ON DELETE CASCADE.                   |
| `step_order`           | `SMALLINT`     | 1, 2, 3, ...                                                         |
| `approver_role_id`     | `UUID`         | FK → `rbac_roles(id)`. Either role OR user must be set.              |
| `approver_user_id`     | `UUID`         | FK → `users(id)`. Direct assignment for a specific approver.         |
| `is_mandatory`         | `BOOLEAN`      | If FALSE, step is informational (notified, not blocking).            |
| `timeout_hours`        | `INTEGER`      | Auto-escalate or auto-approve after N hours. NULL = no timeout.      |
| `on_timeout`           | `VARCHAR(16)`  | `escalate` / `approve` / `reject`.                                   |

### 4.9 `events`

The persisted event log. Every domain event the system emits is written here before any subscriber runs.

| Column               | Type           | Notes                                                                          |
|----------------------|----------------|--------------------------------------------------------------------------------|
| `tenant_id`          | `UUID`         | NOT NULL. NULL events are platform-internal and use a sentinel system tenant.  |
| `event_type`         | `VARCHAR(128)` | Dotted: `acc.invoice.verified`, `ops.dispatch.delayed`.                        |
| `event_version`      | `SMALLINT`     | Default 1. Allows payload schema evolution.                                    |
| `aggregate_type`     | `VARCHAR(64)`  | `invoice`, `dispatch`, `ticket`.                                               |
| `aggregate_id`       | `UUID`         | The entity the event is about.                                                 |
| `correlation_id`     | `UUID`         | Joins related events (e.g. a workflow run).                                    |
| `causation_id`       | `UUID`         | FK to the event ID that caused this one. NULL for root events.                 |
| `actor_user_id`      | `UUID`         | NULL for system-emitted events.                                                |
| `actor_kind`         | `VARCHAR(16)`  | `user` / `system` / `integration` / `whatsapp`.                                |
| `payload`            | `JSONB`        | Event body. Schema enforced at registry level (`app/core/events/registry.py`). |
| `occurred_at`        | `TIMESTAMPTZ`  | Event time, may precede `created_at` for replayed events.                      |
| `delivery_status`    | `event_delivery_status` | `pending` / `delivered` / `partial` / `failed`. Updated by bus.        |
| `delivered_at`       | `TIMESTAMPTZ`  |                                                                                |

Indexes:
- `ix_events__tenant_id__occurred_at` (the bread-and-butter query).
- `ix_events__event_type__occurred_at` (replay by type).
- `ix_events__aggregate_type__aggregate_id` (per-entity history).
- `ix_events__correlation_id`.

Retention: hot in Postgres for 90 days, archived to cold storage thereafter (see §10 — out of scope for v1 schema).

### 4.10 `workflow_definitions`

| Column              | Type           | Notes                                                                            |
|---------------------|----------------|----------------------------------------------------------------------------------|
| `tenant_id`         | `UUID`         | NOT NULL. NULL allowed only for platform-seeded templates.                       |
| `code`              | `VARCHAR(128)` | `invoice_lifecycle`, `stock_transfer_v2`. Unique per (tenant, version).          |
| `version`           | `INTEGER`      | Definitions are immutable; new versions are new rows.                            |
| `display_name`      | `VARCHAR(200)` |                                                                                  |
| `description`       | `TEXT`         |                                                                                  |
| `trigger_event_type`| `VARCHAR(128)` | The single event that instantiates this workflow.                                |
| `trigger_filter`    | `JSONB`        | Optional predicate evaluated against the event payload.                          |
| `definition`        | `JSONB`        | The full step DSL: steps, actions, transitions, timeouts.                        |
| `is_active`         | `BOOLEAN`      | Only one version per code is active per tenant.                                  |
| `published_by`      | `UUID`         | FK → `users(id)`.                                                                |
| `published_at`      | `TIMESTAMPTZ`  |                                                                                  |

Indexes: `ux_workflow_definitions__tenant_id__code__version`, `ix_workflow_definitions__trigger_event_type` (where `is_active`).

### 4.11 `workflow_instances`

| Column                 | Type           | Notes                                                                |
|------------------------|----------------|----------------------------------------------------------------------|
| `tenant_id`            | `UUID`         |                                                                      |
| `definition_id`        | `UUID`         | FK → `workflow_definitions(id)`.                                     |
| `triggering_event_id`  | `UUID`         | FK → `events(id)`. The event that spawned this instance.             |
| `aggregate_type`       | `VARCHAR(64)`  | Mirrors the triggering event.                                        |
| `aggregate_id`         | `UUID`         |                                                                      |
| `status`               | `workflow_instance_status` | `running` / `waiting` / `completed` / `failed` / `cancelled`. |
| `current_step_code`    | `VARCHAR(128)` | The step the instance is waiting on (when `status = waiting`).       |
| `context`              | `JSONB`        | The instance's working memory: variables set by previous steps.      |
| `started_at`           | `TIMESTAMPTZ`  |                                                                      |
| `completed_at`         | `TIMESTAMPTZ`  |                                                                      |
| `failed_at`            | `TIMESTAMPTZ`  |                                                                      |
| `failure_reason`       | `TEXT`         |                                                                      |

Indexes: `ix_workflow_instances__tenant_id__status`, `ix_workflow_instances__aggregate_type__aggregate_id`.

### 4.12 `workflow_step_runs`

| Column            | Type           | Notes                                                                |
|-------------------|----------------|----------------------------------------------------------------------|
| `instance_id`     | `UUID`         | FK → `workflow_instances(id)` ON DELETE CASCADE.                     |
| `step_code`       | `VARCHAR(128)` | From the definition.                                                 |
| `step_order`      | `INTEGER`      | Monotonic per instance.                                              |
| `action_type`     | `VARCHAR(64)`  | `emit_event` / `create_task` / `send_notification` / `wait_for_event` / `evaluate_condition`. |
| `status`          | `workflow_step_status` | `pending` / `running` / `succeeded` / `failed` / `skipped`.  |
| `input`           | `JSONB`        | What was passed to the action.                                       |
| `output`          | `JSONB`        | What the action returned (e.g. created task ID).                     |
| `error`           | `TEXT`         |                                                                      |
| `started_at`      | `TIMESTAMPTZ`  |                                                                      |
| `completed_at`    | `TIMESTAMPTZ`  |                                                                      |

Indexes: `ix_workflow_step_runs__instance_id__step_order`.

### 4.13 `tasks`

The generic Task entity, created by any module and routed through the same UI/WhatsApp surface.

| Column              | Type           | Notes                                                                  |
|---------------------|----------------|------------------------------------------------------------------------|
| `tenant_id`         | `UUID`         |                                                                        |
| `code`              | `VARCHAR(32)`  | Human-friendly counter: `T-451`. Unique per tenant.                    |
| `created_by_module` | `VARCHAR(32)`  | Source module of the task.                                             |
| `source_event_id`   | `UUID`         | FK → `events(id)`. NULL for manually created tasks.                    |
| `workflow_instance_id` | `UUID`      | FK → `workflow_instances(id)`. NULL for ad-hoc tasks.                  |
| `title`             | `VARCHAR(255)` |                                                                        |
| `description`       | `TEXT`         |                                                                        |
| `priority`          | `task_priority`| `low` / `normal` / `high` / `urgent`.                                  |
| `status`            | `task_status`  | `open` / `in_progress` / `blocked` / `done` / `cancelled`.             |
| `due_at`            | `TIMESTAMPTZ`  |                                                                        |
| `started_at`        | `TIMESTAMPTZ`  |                                                                        |
| `completed_at`      | `TIMESTAMPTZ`  |                                                                        |
| `completed_by`      | `UUID`         | FK → `users(id)`.                                                       |
| `context`           | `JSONB`        | Module-specific payload: invoice_id, dispatch_id, ticket_id.            |

Indexes: `ix_tasks__tenant_id__status__due_at`, `ix_tasks__tenant_id__completed_by__completed_at`, `ux_tasks__tenant_id__code`.

### 4.14 `task_assignments`

| Column           | Type           | Notes                                                              |
|------------------|----------------|--------------------------------------------------------------------|
| `task_id`        | `UUID`         | FK → `tasks(id)` ON DELETE CASCADE.                                |
| `assignee_user_id` | `UUID`       | FK → `users(id)`. One of user/role/queue must be set.              |
| `assignee_role_id` | `UUID`       | FK → `rbac_roles(id)`. Pool assignment.                            |
| `queue_code`     | `VARCHAR(64)`  | e.g. `warehouse_north`. Free-form queue.                           |
| `assigned_at`    | `TIMESTAMPTZ`  |                                                                    |
| `assigned_by`    | `UUID`         | FK → `users(id)`. NULL for system-assigned.                        |
| `is_active`      | `BOOLEAN`      | Reassignment deactivates prior rows rather than deleting.          |

Indexes: `ix_task_assignments__assignee_user_id__is_active`, `ix_task_assignments__task_id__is_active`.

### 4.15 `task_prompts`

The bridge between tasks and the WhatsApp conversation runtime. A prompt is "the open question we are waiting for the assignee to answer for this task."

| Column               | Type           | Notes                                                              |
|----------------------|----------------|--------------------------------------------------------------------|
| `task_id`            | `UUID`         | FK → `tasks(id)` ON DELETE CASCADE.                                |
| `assignee_user_id`   | `UUID`         | FK → `users(id)`.                                                  |
| `prompt_kind`        | `VARCHAR(32)`  | `confirm_done` / `approve_reject` / `free_text_reason`.            |
| `accepted_intents`   | `JSONB`        | `["DONE", "✓", "completed"]` — what counts as an answer.           |
| `sent_at`            | `TIMESTAMPTZ`  | When the WhatsApp message was sent.                                |
| `answered_at`        | `TIMESTAMPTZ`  |                                                                    |
| `answer_intent`      | `VARCHAR(32)`  | The matched intent code.                                           |
| `answer_message_id`  | `UUID`         | FK → `conversation_messages(id)`.                                  |
| `expires_at`         | `TIMESTAMPTZ`  | Prompt becomes inactive after this; configurable.                  |

Indexes: `ix_task_prompts__assignee_user_id__answered_at`, partial `ix_task_prompts__open` on `assignee_user_id` where `answered_at IS NULL`.

### 4.16 `notifications`

| Column            | Type           | Notes                                                              |
|-------------------|----------------|--------------------------------------------------------------------|
| `tenant_id`       | `UUID`         |                                                                    |
| `recipient_user_id` | `UUID`       | FK → `users(id)`.                                                  |
| `channel`         | `notification_channel` | `in_app` / `whatsapp` / `email`.                            |
| `category`        | `VARCHAR(64)`  | `task.assigned`, `approval.requested`, `invoice.failed`.           |
| `title`           | `VARCHAR(255)` |                                                                    |
| `body`            | `TEXT`         | Rendered final body.                                               |
| `payload`         | `JSONB`        | Channel-specific extras (template ID, deeplink URL, message ID).   |
| `delivery_status` | `VARCHAR(16)`  | `pending` / `sent` / `delivered` / `read` / `failed`.              |
| `sent_at`         | `TIMESTAMPTZ`  |                                                                    |
| `read_at`         | `TIMESTAMPTZ`  | In-app channel only.                                               |
| `error`           | `TEXT`         |                                                                    |
| `source_event_id` | `UUID`         | FK → `events(id)`. Provenance.                                     |

Indexes: `ix_notifications__recipient_user_id__delivery_status__created_at`.

### 4.17 `notification_preferences`

| Column             | Type           | Notes                                                            |
|--------------------|----------------|------------------------------------------------------------------|
| `user_id`          | `UUID`         | FK → `users(id)` ON DELETE CASCADE.                              |
| `category`         | `VARCHAR(64)`  | Mirrors `notifications.category`.                                |
| `channel`          | `notification_channel` |                                                          |
| `is_enabled`       | `BOOLEAN`      |                                                                  |
| `quiet_hours_start`| `TIME`         | NULL = always-on.                                                |
| `quiet_hours_end`  | `TIME`         |                                                                  |

PK: `(user_id, category, channel)`.

### 4.18 `conversations`

A conversation is a thread between the system and a principal on a single channel.

| Column            | Type           | Notes                                                              |
|-------------------|----------------|--------------------------------------------------------------------|
| `tenant_id`       | `UUID`         |                                                                    |
| `user_id`         | `UUID`         | FK → `users(id)`. NULL if principal not yet linked.                |
| `channel`         | `VARCHAR(16)`  | `whatsapp` / `email`.                                              |
| `external_id`     | `VARCHAR(128)` | WhatsApp wa_id, email thread Message-Id root.                      |
| `state`           | `VARCHAR(32)`  | `active` / `closed`.                                               |
| `last_message_at` | `TIMESTAMPTZ`  |                                                                    |

Indexes: `ux_conversations__tenant_id__channel__external_id`.

### 4.19 `conversation_messages`

| Column              | Type           | Notes                                                              |
|---------------------|----------------|--------------------------------------------------------------------|
| `conversation_id`   | `UUID`         | FK → `conversations(id)` ON DELETE CASCADE.                        |
| `direction`         | `VARCHAR(8)`   | `inbound` / `outbound`.                                            |
| `external_id`       | `VARCHAR(128)` | WhatsApp message ID. Unique per conversation.                      |
| `content_type`      | `VARCHAR(32)`  | `text` / `image` / `template` / `interactive`.                     |
| `body`              | `TEXT`         |                                                                    |
| `raw_payload`       | `JSONB`        | The full webhook payload (inbound) or send response (outbound).    |
| `resolved_intent`   | `VARCHAR(32)`  | What the intent parser matched, if any.                            |
| `resolved_task_id`  | `UUID`         | FK → `tasks(id)`. The task this message resolved an open prompt on.|
| `sent_at`           | `TIMESTAMPTZ`  |                                                                    |
| `delivered_at`      | `TIMESTAMPTZ`  |                                                                    |
| `read_at`           | `TIMESTAMPTZ`  |                                                                    |
| `error`             | `TEXT`         |                                                                    |

Indexes: `ix_conversation_messages__conversation_id__sent_at`, `ux_conversation_messages__conversation_id__external_id`.

### 4.20 `pending_prompts`

A small "expected reply" registry the intent parser consults on every inbound message. Distinct from `task_prompts` because it generalizes — workflow steps and approval chains also use it.

| Column                  | Type           | Notes                                                              |
|-------------------------|----------------|--------------------------------------------------------------------|
| `tenant_id`             | `UUID`         |                                                                    |
| `user_id`               | `UUID`         | The expected responder.                                            |
| `channel`               | `VARCHAR(16)`  | Which channel the reply must come from.                            |
| `subject_kind`          | `VARCHAR(32)`  | `task` / `approval` / `free_form`.                                 |
| `subject_id`            | `UUID`         | Polymorphic — task ID or approval-instance ID.                     |
| `accepted_intents`      | `JSONB`        | `["DONE", "✓"]`.                                                   |
| `expires_at`            | `TIMESTAMPTZ`  |                                                                    |
| `resolved_at`           | `TIMESTAMPTZ`  | NULL while open.                                                   |
| `resolved_by_message_id`| `UUID`         | FK → `conversation_messages(id)`.                                  |

Indexes: partial `ix_pending_prompts__open` on `(tenant_id, user_id, channel)` where `resolved_at IS NULL`.

### 4.21 `integration_configs`

| Column            | Type           | Notes                                                              |
|-------------------|----------------|--------------------------------------------------------------------|
| `tenant_id`       | `UUID`         |                                                                    |
| `connector_code`  | `VARCHAR(64)`  | `tally`, `shopify`, `gmail`, `whatsapp`, `sheets`, `webhook`.      |
| `instance_code`   | `VARCHAR(64)`  | A tenant may have two Shopify stores. Differentiator.              |
| `display_name`    | `VARCHAR(200)` |                                                                    |
| `config`          | `JSONB`        | Non-secret connector config: URLs, mapping rules, store IDs.       |
| `is_active`       | `BOOLEAN`      |                                                                    |
| `last_synced_at`  | `TIMESTAMPTZ`  |                                                                    |
| `last_sync_status`| `VARCHAR(32)`  | `success` / `partial` / `failure`.                                 |
| `last_sync_error` | `TEXT`         |                                                                    |

Indexes: `ux_integration_configs__tenant_id__connector_code__instance_code`.

### 4.22 `integration_credentials`

Split from `integration_configs` because secrets follow a different lifecycle and ACL.

| Column               | Type           | Notes                                                              |
|----------------------|----------------|--------------------------------------------------------------------|
| `integration_config_id` | `UUID`      | FK → `integration_configs(id)` ON DELETE CASCADE.                  |
| `credential_kind`    | `VARCHAR(32)` | `oauth2` / `api_key` / `basic_auth` / `signed_secret`.             |
| `encrypted_payload`  | `BYTEA`       | Application-layer envelope encryption. KEK in env, DEK rotated.    |
| `key_version`        | `INTEGER`     | For rotation.                                                       |
| `expires_at`         | `TIMESTAMPTZ` | OAuth refresh deadline.                                            |
| `last_refreshed_at`  | `TIMESTAMPTZ` |                                                                    |

Indexes: `ix_integration_credentials__integration_config_id`.

### 4.23 `audit_log`

This is the **rename and generalization** of the existing `audit_logs` table. It is a passive subscriber to the event bus — every event written to `events` also writes a row here, in a denormalized, human-readable form.

| Column           | Type           | Notes                                                                |
|------------------|----------------|----------------------------------------------------------------------|
| `tenant_id`      | `UUID`         |                                                                      |
| `event_id`       | `UUID`         | FK → `events(id)`. The canonical event.                              |
| `event_type`     | `VARCHAR(128)` | Denormalized for query speed.                                        |
| `actor_user_id`  | `UUID`         | FK → `users(id)`.                                                    |
| `actor_kind`     | `VARCHAR(16)`  | `user` / `system` / `integration` / `whatsapp`.                      |
| `aggregate_type` | `VARCHAR(64)`  |                                                                      |
| `aggregate_id`   | `UUID`         |                                                                      |
| `description`    | `TEXT`         | Human-readable: "Invoice INV-2304 approved by Priya".                |
| `extra_data`     | `JSONB`        | Free-form context (kept consistent with current `audit_logs.extra_data` shape).|
| `ip_address`     | `VARCHAR(45)`  |                                                                      |
| `user_agent`     | `VARCHAR(500)` |                                                                      |

Indexes: `ix_audit_log__tenant_id__created_at`, `ix_audit_log__aggregate_type__aggregate_id`, `ix_audit_log__actor_user_id__created_at`.

`audit_log` is **append-only**. No `UPDATE`, no `DELETE`. Enforced by a `BEFORE UPDATE OR DELETE` trigger that raises an exception.

### 4.24 `config_store`

The generic per-tenant k/v store. Used for Tally mappings, SLA thresholds, notification templates, channel-specific behavior — anything we want editable from the UI without code changes.

| Column        | Type           | Notes                                                                  |
|---------------|----------------|------------------------------------------------------------------------|
| `tenant_id`   | `UUID`         |                                                                        |
| `namespace`   | `VARCHAR(64)`  | `acc.tally`, `cs.sla`, `ops.dispatch.thresholds`.                      |
| `key`         | `VARCHAR(128)` | Within the namespace.                                                  |
| `value`       | `JSONB`        |                                                                        |
| `schema_version` | `INTEGER`   | Allows the consumer to handle older shapes.                            |
| `updated_by`  | `UUID`         | FK → `users(id)`.                                                       |

Indexes: `ux_config_store__tenant_id__namespace__key`.

---

## 5. Module table migration

The current schema is finance-only. The platform reorg requires renames, additions, and some splits. Below: what we change for `acc_*` (which already has tables) and the planned shape for the other modules.

### 5.1 Accounts (`acc_*`) — rename of existing tables

| Current name              | New name                          | Structural changes                                                                                                                                                                  |
|---------------------------|-----------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `invoices`                | `acc_invoices`                    | Add `tenant_id UUID NOT NULL`. Add `verified_at`, `verified_by`, `tally_pushed_at` (already-implicit lifecycle becomes explicit). `uploaded_by` FK retargets to `users` (unchanged). |
| `invoice_items`           | `acc_invoice_items`               | Add `tenant_id`. `invoice_id` FK retargets to `acc_invoices`.                                                                                                                       |
| `vendors`                 | `acc_vendors`                     | Add `tenant_id`. Unique `(tenant_id, gstin)` and `(tenant_id, name)`.                                                                                                               |
| `reconciliation_records`  | `acc_reconciliation_records`      | Add `tenant_id`. `invoice_id` FK retargets to `acc_invoices`.                                                                                                                       |
| `processing_jobs`         | `acc_processing_jobs`             | Add `tenant_id`. Kept Accounts-internal — generic job tracking happens in RQ, this table is the OCR-pipeline audit specifically.                                                    |
| `audit_logs`              | `audit_log` (core, see §4.23)     | Renamed and generalized. `invoice_id` column dropped in favor of `aggregate_type` + `aggregate_id`. Backfill step migrates existing rows.                                           |

Enum renames: `invoice_status`, `payment_status`, `reconciliation_status`, `discrepancy_type` — kept as-is (already underscore-named, no module prefix needed because the enum type's name is sufficient and `acc_invoice_status` is uglier than `invoice_status` for no benefit).

The OCR confidence score, raw OCR text, and extraction notes stay on `acc_invoices`. They are queried in the verification UI and don't belong in JSONB.

### 5.2 Operations (`ops_*`) — planned

| Table                   | Notable columns                                                                                                                                                                                                                                                                                                                                                          |
|-------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `ops_channels`          | `tenant_id`, `code` (`shopify`, `amazon`, `flipkart`, `manual`), `display_name`, `integration_config_id`, `is_active`.                                                                                                                                                                                                                                                  |
| `ops_orders`            | `tenant_id`, `channel_id`, `external_order_id`, `external_order_number`, `customer_external_id`, `placed_at`, `currency`, `subtotal NUMERIC(14,2)`, `tax_amount`, `shipping_amount`, `discount_amount`, `total_amount`, `status` (`received`/`processing`/`shipped`/`delivered`/`cancelled`/`returned`), `shipping_address JSONB`, `billing_address JSONB`, `raw_payload JSONB`. |
| `ops_order_items`       | `tenant_id`, `order_id`, `sku_id` (FK → `inv_skus`, nullable for unmatched), `external_sku`, `quantity`, `unit_price`, `tax_amount`, `total_amount`.                                                                                                                                                                                                                     |
| `ops_dispatches`        | `tenant_id`, `order_id`, `warehouse_id` (FK → `inv_warehouses`), `courier_id`, `tracking_number`, `status` (`packing`/`packed`/`handed_over`/`in_transit`/`delivered`/`failed`), `expected_delivery_at`, `delivered_at`, `assigned_picker_user_id`.                                                                                                                       |
| `ops_couriers`          | `tenant_id`, `code`, `display_name`, `tracking_url_template`.                                                                                                                                                                                                                                                                                                            |
| `ops_returns`           | `tenant_id`, `order_id`, `reason_code`, `status` (`requested`/`in_transit`/`received`/`restocked`/`rejected`), `received_at`.                                                                                                                                                                                                                                            |
| `ops_sales_daily`       | Pre-aggregated; `tenant_id`, `channel_id`, `sku_id`, `business_date`, `units`, `gross_revenue`, `discounts`, `net_revenue`. Maintained by event subscriber.                                                                                                                                                                                                              |

Indexes (selected): `ux_ops_orders__channel_id__external_order_id`, `ix_ops_orders__tenant_id__status__placed_at`, `ix_ops_dispatches__tenant_id__status__expected_delivery_at`.

### 5.3 Inventory (`inv_*`) — planned

| Table                  | Notable columns                                                                                                                                                                                                                                                                                                                              |
|------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `inv_warehouses`       | `tenant_id`, `code`, `display_name`, `address JSONB`, `is_active`.                                                                                                                                                                                                                                                                          |
| `inv_skus`             | `tenant_id`, `code` (SKU), `display_name`, `category`, `unit_of_measure`, `default_cost NUMERIC(14,2)`, `is_active`. Unique `(tenant_id, code)`.                                                                                                                                                                                            |
| `inv_stock_levels`     | `tenant_id`, `sku_id`, `warehouse_id`, `quantity_on_hand`, `quantity_reserved`, `last_movement_at`. Unique `(tenant_id, sku_id, warehouse_id)`. **All quantity changes go through events, not direct UPDATE** — the column is the materialized current state.                                                                              |
| `inv_stock_movements`  | Append-only ledger of every adjustment: `tenant_id`, `sku_id`, `warehouse_id`, `delta_quantity`, `reason` (`receipt`/`dispatch`/`transfer_in`/`transfer_out`/`adjustment`/`write_off`), `reference_type`, `reference_id`, `actor_user_id`. The stock_levels table is reconstructable from this. |
| `inv_transfers`        | `tenant_id`, `source_warehouse_id`, `destination_warehouse_id`, `status` (`requested`/`in_transit`/`received`/`cancelled`), `requested_by`, `received_by`, `requested_at`, `received_at`.                                                                                                                                                  |
| `inv_transfer_items`   | `tenant_id`, `transfer_id`, `sku_id`, `quantity`.                                                                                                                                                                                                                                                                                           |
| `inv_reservations`     | `tenant_id`, `sku_id`, `warehouse_id`, `quantity`, `reference_type` (`order` typically), `reference_id`, `released_at`. Soft-released (timestamp), not deleted, so we can audit oversell attempts.                                                                                                                                          |
| `inv_reorder_thresholds`| `tenant_id`, `sku_id`, `warehouse_id`, `min_quantity`, `reorder_quantity`, `is_active`.                                                                                                                                                                                                                                                    |

### 5.4 Customer Service (`cs_*`) — planned

| Table                  | Notable columns                                                                                                                                                                                                                                  |
|------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `cs_customers`         | `tenant_id`, `external_id`, `name`, `email`, `phone_e164`, `metadata JSONB`. May be partially populated from order data.                                                                                                                        |
| `cs_tickets`           | `tenant_id`, `code` (`CS-1024`), `customer_id`, `source_channel` (`email`/`whatsapp`/`manual`/`webhook`), `subject`, `status` (`open`/`in_progress`/`waiting_customer`/`resolved`/`closed`), `priority`, `assigned_to`, `sla_policy_id`, `first_response_at`, `resolved_at`, `escalation_level`. |
| `cs_ticket_messages`   | `tenant_id`, `ticket_id`, `direction`, `author_user_id`, `body`, `attachments JSONB`, `external_id` (provider message ID), `sent_at`.                                                                                                            |
| `cs_templates`         | `tenant_id`, `code`, `channel`, `language`, `subject`, `body`, `variables JSONB`.                                                                                                                                                                |
| `cs_sla_policies`      | `tenant_id`, `code`, `first_response_minutes`, `resolution_minutes`, `business_hours_only`, `business_hours_config JSONB`.                                                                                                                       |

Indexes: `ix_cs_tickets__tenant_id__status__priority`, `ix_cs_tickets__tenant_id__assigned_to__status`, `ux_cs_tickets__tenant_id__code`.

### 5.5 Founder Intelligence (`fi_*`) — planned

`fi_*` tables are write-mostly-from-subscribers, read-only from the dashboard. They are intentionally denormalized.

| Table                          | Notable columns                                                                                                                            |
|--------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------|
| `fi_daily_snapshot`            | `tenant_id`, `business_date`, `metrics JSONB`. One row per tenant per day. JSONB is acceptable here — see §7.                              |
| `fi_kpi_dispatch_cycle_time`   | `tenant_id`, `business_date`, `channel_id`, `avg_hours`, `p50_hours`, `p90_hours`, `sample_count`.                                         |
| `fi_kpi_reconciliation_rate`   | `tenant_id`, `business_date`, `invoices_total`, `invoices_reconciled`, `invoices_with_discrepancy`.                                        |
| `fi_kpi_csat`                  | `tenant_id`, `business_date`, `tickets_resolved`, `avg_resolution_minutes`, `sla_breach_count`.                                            |
| `fi_alert_definitions`         | `tenant_id`, `code`, `description`, `predicate JSONB`, `severity`, `notify_role_ids JSONB`, `is_active`.                                   |
| `fi_alert_instances`           | `tenant_id`, `definition_id`, `triggered_at`, `resolved_at`, `metric_snapshot JSONB`.                                                       |

---

## 6. Index strategy

The rules of thumb, in priority order:

1. **Every business-data table has `(tenant_id, ...)` as the leading index column** on its primary access pattern. Most queries filter by tenant first; the planner never benefits from an index that lacks it.
2. **Every FK column has an index** unless we can prove (with EXPLAIN) the table is too small to matter. The cost of an index that's never used is bounded; the cost of a sequential scan on a parent delete is unbounded.
3. **Status columns are indexed when they participate in hot queries** — `(tenant_id, status, created_at DESC)` is the canonical "show me the inbox" index.
4. **Timestamp indexes are `DESC` when ordering by recency**. Postgres uses them both ways but the BRIN/B-tree shape is friendlier for reverse-time scans.
5. **The event log and audit log get BRIN indexes on `(occurred_at)` and `(created_at)` respectively** *in addition to* the B-tree on `(tenant_id, occurred_at)`. BRIN is roughly free in storage and accelerates wide time-range scans for the audit UI and replay job.
6. **Partial indexes for "open" sets.** `WHERE answered_at IS NULL`, `WHERE deactivated_at IS NULL`, `WHERE delivery_status = 'pending'`. These keep the workload-hot index small.
7. **No composite indexes longer than 3 columns** unless we can show a query that uses all of them. The maintenance cost compounds; the benefit doesn't.
8. **GIN indexes on JSONB columns only when we actually query them by key.** `events.payload` is GIN-indexed (used by ad-hoc forensic queries); `audit_log.extra_data` is not (we filter by `aggregate_type`/`aggregate_id` instead).

---

## 7. JSONB usage policy

JSONB is a tool, not a default. It exists for shapes we cannot or will not promote to columns.

### 7.1 Where JSONB is correct

- **Event payloads** (`events.payload`) — by definition heterogeneous; schema is versioned per event type.
- **Per-tenant configuration** (`config_store.value`, `tenants.settings`) — schema differs per namespace.
- **Audit metadata** (`audit_log.extra_data`) — append-only forensic context; never filtered on at scale.
- **OCR raw output and provider responses** (`acc_invoices.raw_ocr_text` is `TEXT`, but the structured raw response stays in `acc_processing_jobs.result_payload JSONB`). Lossless capture is the goal.
- **Connector raw payloads** (`ops_orders.raw_payload`, `cs_ticket_messages.attachments`, `conversation_messages.raw_payload`) — we keep the original so we can rebuild internal representation as our model evolves.
- **Address blocks** (`ops_orders.shipping_address`, `inv_warehouses.address`) — we do not query orders by city; if we ever do, we lift fields out.
- **Snapshot/aggregate payloads** (`fi_daily_snapshot.metrics`) — small, written once per day, read by one screen.

### 7.2 Where JSONB is wrong

- **Anything we filter on at scale.** Status, dates, foreign keys, money amounts. They become columns or they become a tax.
- **Anything we sort or paginate by.** JSONB ordering is slower and the indexes are larger.
- **Anything participating in foreign-key integrity.** FKs into JSONB are not a thing.
- **State machine flags.** They are enums with check constraints. Always.
- **Anything used by joins.** A `vendor_id` in JSONB is a bug, not a shortcut.

### 7.3 Practical test

Before adding a JSONB column, ask:
1. Will any query include this in a `WHERE` other than `IS NULL`/`IS NOT NULL`?
2. Will the UI sort or paginate by it?
3. Does it have a fixed shape known at design time?

If yes to 1 or 2, or yes to 3 with high stability — make it a column. Otherwise JSONB.

---

## 8. Soft delete policy

**Default: hard delete. Soft delete only where business policy requires recoverability.**

| Table         | Strategy   | Reason                                                                                                       |
|---------------|------------|--------------------------------------------------------------------------------------------------------------|
| `tenants`     | Soft       | `deactivated_at`. A deleted tenant takes the entire dataset with it; we want a recovery window.              |
| `users`       | Soft       | `deactivated_at`. Foreign keys reference users from audit log, tasks, events, etc. Hard delete cascades poorly. Deactivation preserves history while preventing login. |
| Everything else (`acc_*`, `ops_*`, `inv_*`, `cs_*`, `fi_*`, `events`, `audit_log`, `tasks`, ...) | Hard | We do not want `WHERE deleted_at IS NULL` polluting every query. The audit log preserves what happened; the row itself can go. |

Justification for hard delete on transactional tables:

1. **Soft delete is a permission, not a behavior.** "Can this user delete an invoice?" is an RBAC question. Granting it implies we trust them to delete it. Adding a recoverable layer creates a false sense of safety.
2. **The audit log already records every state change**, including deletion. Recovery is via replay or backup restore, not via row resurrection.
3. **Soft delete corrupts uniqueness constraints.** A unique `(tenant_id, gstin)` becomes a unique `(tenant_id, gstin) WHERE deleted_at IS NULL` partial index, which is a foot-gun.
4. **Soft delete corrupts joins.** Every query has to remember to filter. The day someone forgets, deleted vendors show up on a report.

The `events` and `audit_log` tables are append-only — neither hard nor soft delete is allowed in the application. Operationally, they are retention-managed (drop rows older than X days from cold storage, never the live table) via a scheduled job that runs explicit `DELETE`. That job is the only writer of `DELETE` against those tables.

---

## 9. Migration strategy

### 9.1 Tool and structure

Alembic, autogenerate off by default. Every migration is hand-written, reviewed, and reversible. The chain is **linear** — we do not branch. If two PRs both generate migrations, one rebases.

```
backend/alembic/versions/
├── 0001_initial_schema.py        # existing — finance tables
├── 0002_platform_core.py         # tenants, rbac_*, events, workflows_*, tasks, notifications, conversations, audit_log
├── 0003_module_prefix_rename.py  # invoices→acc_invoices, etc. + tenant_id backfill
├── 0004_module_ops.py            # ops_* tables
├── 0005_module_inventory.py      # inv_* tables
├── 0006_module_cs.py             # cs_* tables
├── 0007_module_fi.py             # fi_* tables + subscribers wired in code
└── ...
```

### 9.2 Rules

1. **Every migration has an explicit `downgrade()`.** No `pass`. If the migration genuinely cannot be reversed (e.g. data destruction), the downgrade raises with a documented reason — but data-destroying migrations are themselves prohibited (see #3).
2. **No destructive rename without a paired backfill step.** Renaming `invoices` to `acc_invoices` is `ALTER TABLE RENAME` — non-destructive. Dropping a column requires a prior migration that stopped writing it.
3. **Schema-only migrations and data migrations are separate revisions.** Mixing them makes downgrade impossible and makes rollback windows confusing in production.
4. **Add nullable, backfill, set NOT NULL** — for any new required column, this is three migrations, not one. The codebase pays the cost; production stays online.
5. **Enums are added via the existing pattern.** `Enum(..., name="...", create_type=False)` in models; `op.execute("CREATE TYPE ...")` and `op.execute("DROP TYPE ...")` in the migration. The pattern is already established in `0001_initial_schema.py`.
6. **Triggers are created in migrations, not in models.** The `updated_at` and `audit_log_no_modify` triggers are installed in `0002` and referenced thereafter via a helper.
7. **No `op.execute("ALTER TABLE ...")` when a structured `op.alter_column` exists.** Keep the migration introspectable.

### 9.3 The `invoices → acc_invoices` migration (illustrative)

Migration `0003_module_prefix_rename.py` performs only renames and tenant-id backfill. The shape is:

1. Insert a single "default" tenant row into `tenants` (only on environments that came from the legacy schema — guarded by `if not tenant_exists()` in the migration script).
2. For each table getting `tenant_id`:
   - `ALTER TABLE ... ADD COLUMN tenant_id UUID NULL`.
   - `UPDATE ... SET tenant_id = '<default-tenant-uuid>'`.
   - `ALTER TABLE ... ALTER COLUMN tenant_id SET NOT NULL`.
   - `ALTER TABLE ... ADD CONSTRAINT fk_<table>__tenant_id__tenants FOREIGN KEY (tenant_id) REFERENCES tenants(id)`.
3. Rename tables: `ALTER TABLE invoices RENAME TO acc_invoices`, etc.
4. Rename indexes and constraints to the new naming convention (`fk_acc_invoices__vendor_id__acc_vendors`, etc.).
5. Update enum-bound columns are unchanged because the enum *type* name does not need to move.
6. Rename `audit_logs` → `audit_log`, then in a **separate following migration**, restructure its columns (drop `invoice_id`, add `aggregate_type`/`aggregate_id`, backfill from old `invoice_id` where present). Two revisions because the data migration is destructive and we want a clean rollback point.

`downgrade()` for `0003` reverses the renames and drops the FKs but does **not** delete the default tenant — that is left to a manual operator action with a `WARNING` printed at downgrade time. Documented in the migration's docstring.

### 9.4 Testing migrations

- `alembic upgrade head` runs in CI against a clean Postgres.
- `alembic downgrade base` then `upgrade head` runs as a separate CI job to verify reversibility.
- A "real data" job restores a sanitized prod snapshot and runs `upgrade head` against it. This is the migration that has caught every multi-tenant column-add issue we have ever had.

---

## 10. What we deliberately don't do

This section exists so reviewers do not have to guess.

| Not doing | Why |
|---|---|
| **Event sourcing as the primary store.** | Events are persisted (`events` table) and are the connective tissue, but the **system of record is the relational model**. We do not rebuild aggregate state by replaying events on every read. Aggregate tables are authoritative; events are the log. Event sourcing as a primary pattern is an order of magnitude more complex and we do not need its benefits (temporal queries, projection rebuilds for arbitrary read models) at this scope. |
| **Schema-per-tenant.** | Discussed in §2.1. Multiplies migration cost by N; gains us nothing the `tenant_id` column doesn't already give us. |
| **Postgres Row-Level Security.** | Discussed in §2.2. Service-layer scoping is testable; RLS plus a connection pooler is a footgun. |
| **NoSQL (Mongo / Dynamo / etc.).** | Our data is relational. The "flexibility" of NoSQL is a euphemism for "you write the joins in application code." We have invoices with line items, orders with items, tickets with messages — classic relational shapes. Postgres handles every JSONB use case we have. |
| **A separate read database / CQRS.** | Founder Intelligence runs on aggregate tables in the same Postgres, written by event subscribers. We do not stream to a second store. When and if read load justifies it, we add a Postgres read replica; we do not bolt on Elastic / Mongo / Clickhouse before the workload demands it. |
| **A graph database.** | We have no graph problems. Approval chains and workflow steps are sequences, not graphs in the database sense. |
| **A time-series database.** | The metrics tables (`fi_kpi_*`, `ops_sales_daily`) are pre-aggregated daily rollups. We will not ingest raw second-by-second telemetry; if we ever did, that would be a separate concern (Prometheus), not a primary store. |
| **Kafka or any external broker as the event bus.** | The bus is in-process for synchronous handlers and Redis Pub/Sub for async fanout. Both are sufficient at our scale. Kafka pulls in ZooKeeper / KRaft, partitioning decisions, consumer-group management — costs that buy nothing for a single-node FastAPI deployment. |
| **Database-level audit/CDC tooling (Debezium, pgaudit).** | Application-level audit via the event bus gives us business-level events ("Priya approved invoice INV-2304"), not row-level diffs. Row-level audit is reconstructable from `events` + `audit_log` when needed. |
| **Cross-tenant joins as a query pattern.** | They are an admin/support tool only, executed through a dedicated `super_admin` path that bypasses the tenant-scoped repository explicitly. Application queries that touch >1 tenant in the normal path are bugs. |
| **Sharding.** | We have a single tenant in production. We will revisit when one tenant's data outgrows a single Postgres instance. By then we will know which shape (tenant-id-sharding vs. table-sharding) is right. Premature sharding is the second most expensive premature optimization in this stack. |

The first most expensive premature optimization is microservices, which we have already declined elsewhere.
