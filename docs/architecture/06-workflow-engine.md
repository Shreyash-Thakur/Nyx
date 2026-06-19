# 06 — Workflow Engine

The Workflow Engine is the most load-bearing piece of the Nyx platform. Every module — Accounts, Operations, Inventory, Customer Service, Founder Intelligence — drives its multi-step processes through it. Approval chains, SLA timers, dispatch lifecycles, invoice routing, escalations: all are workflows, not bespoke service code.

This document specifies what the engine is, why it looks the way it does, the data model behind it, and the runtime that advances it. It is opinionated and complete. There is no "phase 2" workflow engine planned — this one is the one we ship.

---

## 1. Why we build our own

A reasonable interviewer will immediately ask: *why not Temporal? Why not Camunda? Why not Airflow?* The answer is short, and we own it.

### Temporal

Temporal is brilliant if your problem is **durable distributed execution of long-running code**. Its model is "workflows are deterministic Python/Go functions; the framework replays them across worker crashes." Two problems for Nyx:

1. **Workflows in Temporal are code, not data.** Editing a workflow means editing a Python file and redeploying a worker. Our entire premise (principle P4, P9) is that a workflow definition is a database row a non-engineer admin edits through a UI. Temporal cannot give us that without us essentially building our own DSL on top — at which point Temporal is overhead, not leverage.
2. **Temporal is a service.** It is a sidecar cluster, a separate database, a separate operational surface. For a single-deployable modular monolith aimed at Indian SMEs running on a single VPS, adding a Temporal cluster is the entire infrastructure footprint of the rest of the system, doubled, for one feature.

### Camunda

Camunda is a BPMN engine — XML, a visual designer, a Java-heritage runtime. The mental model is right; the artifact is wrong. BPMN is overkill for the eight to twelve canonical shapes our workflows take. The visual designer is impressive in demos and useless in practice — admins who can edit YAML can be trained in an afternoon; admins who can't will not author BPMN either. And the Camunda Java/Spring stack does not graft naturally onto a FastAPI codebase.

### Airflow / Prefect / Dagster

These are **data pipeline orchestrators**. They are batch-shaped, DAG-shaped, scheduler-first. They expect a step to run, finish, and produce data for the next step. Our workflows are event-shaped: a step waits for a human approval, or a WhatsApp `DONE`, or an inbound webhook from a courier. Forcing event-driven business processes into a batch DAG engine is the canonical wrong tool.

### Custom, embedded, replaceable

So we build a small engine, in-process, backed by Postgres and Redis, with these properties:

- **Embedded.** No extra process. The runner is a function called by event handlers and RQ workers we already run.
- **Declarative.** Definitions are YAML rows in the database. Editing one is a `PUT` request.
- **Owned.** Every line of it is in our repo. When something is wrong we read our own code, not a third-party changelog.
- **Replaceable.** The contract surface is small: `WorkflowDefinition`, `WorkflowInstance`, `Action`, `Condition`. If in two years we outgrow this, the surface migrates cleanly to Temporal — but we will not have paid Temporal's operational cost during the years we did not need it.

The engine is ~1,500 lines of Python. That is the right size for the problem.

---

## 2. The mental model

A **Workflow Definition** is a directed graph of **Steps**. Each Step has:

- **Trigger** — what causes the step to be considered for execution. For the *first* step, this is the workflow's entry trigger. For subsequent steps, the trigger is usually "the previous step completed," but it can also be "an event of kind X arrives matching this instance" (a wait-step) or "a timer fires."
- **Conditions** — zero or more boolean gates. The step's actions run only if all conditions evaluate true against the current context. If any condition is false, the step is skipped and the engine moves to the step's `else` edge (or terminates if absent).
- **Actions** — an ordered list of side effects (registered functions). Each action receives the workflow context, executes, and appends its output back to context.
- **Edges** — `next` (default), `on_success`, `on_failure`, `else`. Cycles are syntactically possible but discouraged; a definition that cycles must declare a `max_iterations` guard.

A **Workflow Instance** is one in-flight execution of a definition. It carries:

- The definition version it pinned at creation,
- A JSONB **context** (the accumulated state: trigger payload + every step's output),
- A **current_step** pointer,
- A **status** (`pending`, `running`, `waiting`, `completed`, `failed`, `parked`),
- The trigger event that created it.

The engine's only job is to advance instances. Everything else — persistence, retries, alerts, audit — is bookkeeping around that one verb.

A picture:

```
                 ┌──────────────┐
   event ───────▶│  Trigger     │
   schedule ────▶│  matched?    │
   WA intent ───▶│              │
                 └──────┬───────┘
                        │
                        ▼
                ┌───────────────┐
                │ instantiate   │  ← new row in workflow_instances
                │ (pin version) │     context = trigger payload
                └───────┬───────┘
                        │
                        ▼
            ┌──────────────────────┐
            │ runner.advance(inst) │◀──── re-entrant; called on every event
            └──────────┬───────────┘       that matches a waiting instance
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
   evaluate       execute        wait for
   conditions     actions        event/timer
        │              │              │
        ▼              ▼              ▼
   next step      append to       park in DB
                  context         (status=waiting)
```

---

## 3. Triggers

A trigger is what causes a new instance to be created (entry trigger) or what wakes a parked step (wait trigger). There are four kinds, and only four.

### 3.1 `event.<name>` — a published platform event

The most common trigger. A workflow definition says:

```yaml
trigger:
  type: event
  name: acc.invoice.requires_founder_approval
  filter:
    amount: "> 100000"
```

When the event bus publishes an event named `acc.invoice.requires_founder_approval`, the engine looks up all definitions whose entry trigger matches the event name, evaluates the filter against the event payload, and instantiates a workflow per match.

Filters use the same restricted condition language (Section 4). They are evaluated against the event's `payload` field — `event.payload.amount` and `payload.amount` and bare `amount` all resolve to the same value inside the trigger filter.

### 3.2 `schedule.<cron>` — time-based

```yaml
trigger:
  type: schedule
  cron: "0 9 * * *"   # every day at 09:00 IST
  payload:
    purpose: "daily reconciliation sweep"
```

The Scheduler (RQ-scheduler wrapper, `app/core/scheduler/`) emits a synthetic event `core.schedule.tick` carrying the definition id; the engine treats this identically to any event trigger. We do not run a separate cron loop inside the engine — the platform already has a scheduler, we reuse it.

### 3.3 `manual` — API or UI

```yaml
trigger:
  type: manual
```

A `POST /api/v1/workflows/{def_id}/instances` with a JSON payload creates an instance directly. Used for one-off operations: "run this reconciliation for invoice X right now," "start the onboarding workflow for vendor Y." RBAC gates the endpoint at `workflow.instance.create` × scope.

### 3.4 `whatsapp.intent.<verb>` — inbound message intent

```yaml
trigger:
  type: whatsapp.intent
  verb: ESCALATE
  filter:
    user.role: "customer_service_agent"
```

The Conversation Runtime resolves an inbound WhatsApp message to a verb (`DONE`, `APPROVE`, `REJECT`, `HELP`, `ESCALATE`, ...) and publishes an event `core.whatsapp.intent` with the verb, the principal, and any contextual references (task id, ticket id). The engine treats this as a regular event trigger; the `whatsapp.intent.X` form is sugar.

This is the principle **P5** payoff: WhatsApp messages and HTTP requests reach the engine through the same door.

### Triggers we do not support

- **Polling triggers.** We do not poll. If an external system needs to notify us, it does so via webhook (Integration Framework) which then publishes an event.
- **Composite triggers** ("fire when A *and* B happen"). Implemented as a wait-step pattern (Section 11), not a trigger.
- **Stream / Kafka triggers.** We do not run Kafka. See `adr/`.

---

## 4. Conditions

A condition is a boolean expression evaluated against the workflow context. We deliberately do **not** allow arbitrary Python. We define a restricted expression language and parse it with Python's `ast` module, walking the tree and rejecting any node type not in the allowlist.

### 4.1 What is allowed

| Construct | Examples |
|---|---|
| Comparisons | `amount > 100000`, `status == "open"`, `priority in ["high", "urgent"]` |
| Boolean ops | `amount > 100000 and vendor.is_new`, `not is_duplicate` |
| Arithmetic | `total - discount > 5000`, `qty * price` |
| Attribute access | `event.payload.amount`, `context.invoice.vendor_id` |
| Index access | `items[0].sku`, `config["tally_voucher_type"]` |
| Tenant config refs | `tenant_config.approval_threshold_inr` |
| Literals | numbers, strings, booleans, lists, None |

### 4.2 What is disallowed

| Construct | Why |
|---|---|
| Function calls | Removes the entire "what code runs" question. No `os.system("rm -rf")` possible. |
| Imports | Same reason. |
| Lambdas, comprehensions, generators | Not needed; complexity invites abuse. |
| Dunder attribute access (`__class__`, `__globals__`, ...) | The classic Python sandbox escape. Hard-rejected. |
| Walrus, decorators, async | Not needed. |
| String formatting at evaluation | Templating is a separate concern; we don't conflate. |

### 4.3 Why not just allow Python?

Because the moment we allow `eval()` on admin-edited strings, we have a remote code execution vulnerability accessible to anyone who can reach the workflow admin UI. The cost of writing a 200-line AST validator is enormously less than the cost of one breach. And the loss in expressive power is theoretical: in two years of running similar engines, the condition expressivity required by real business processes has not exceeded what this grammar provides.

### 4.4 The evaluator

```python
# app/core/workflows/conditions.py (sketch)

import ast
from typing import Any

_ALLOWED_NODES = {
    ast.Expression, ast.BoolOp, ast.BinOp, ast.UnaryOp, ast.Compare,
    ast.Name, ast.Load, ast.Attribute, ast.Subscript, ast.Index,
    ast.Constant, ast.List, ast.Tuple, ast.Dict,
    ast.And, ast.Or, ast.Not,
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In, ast.NotIn,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod,
}
_FORBIDDEN_NAME_PREFIX = "__"


class UnsafeExpression(Exception):
    pass


def validate(expr: str) -> ast.AST:
    tree = ast.parse(expr, mode="eval")
    for node in ast.walk(tree):
        if type(node) not in _ALLOWED_NODES:
            raise UnsafeExpression(f"disallowed node: {type(node).__name__}")
        if isinstance(node, ast.Attribute) and node.attr.startswith(_FORBIDDEN_NAME_PREFIX):
            raise UnsafeExpression(f"dunder access forbidden: {node.attr}")
        if isinstance(node, ast.Name) and node.id.startswith(_FORBIDDEN_NAME_PREFIX):
            raise UnsafeExpression(f"dunder name forbidden: {node.id}")
    return tree


def evaluate(expr: str, context: dict[str, Any]) -> Any:
    tree = validate(expr)
    # context is the only namespace; no builtins exposed
    return eval(  # noqa: S307 — validated above
        compile(tree, "<workflow-condition>", "eval"),
        {"__builtins__": {}},
        context,
    )
```

Definitions store conditions as strings. The engine validates every condition at definition save time (so authoring errors surface immediately) and re-validates at runtime as a defense-in-depth check.

---

## 5. Actions

An action is a side effect — the thing that actually *does* something. Actions are the only place a workflow modifies the world.

### 5.1 The registry

Actions live in a central registry. Each module registers its actions in its `__init__.py` so the engine discovers them at import time.

```python
# app/core/workflows/actions.py (sketch)

from typing import Callable, TypedDict, Protocol
from dataclasses import dataclass


class ActionContext(TypedDict):
    tenant_id: str
    instance_id: str
    step_name: str
    workflow_context: dict
    idempotency_key: str


@dataclass
class ActionSpec:
    name: str                          # e.g. "core.tasks.create"
    handler: Callable[[ActionContext, dict], dict]
    input_schema: dict                 # JSON Schema for params
    output_schema: dict                # JSON Schema for return
    idempotent: bool                   # safe to retry?
    retry_policy: "RetryPolicy"


@dataclass
class RetryPolicy:
    max_attempts: int = 5
    backoff_seconds: tuple[int, ...] = (5, 15, 60, 300, 900)
    retry_on: tuple[type[Exception], ...] = (TransientError,)


_REGISTRY: dict[str, ActionSpec] = {}


def register(spec: ActionSpec) -> None:
    if spec.name in _REGISTRY:
        raise ValueError(f"action {spec.name!r} already registered")
    _REGISTRY[spec.name] = spec


def get(name: str) -> ActionSpec:
    if name not in _REGISTRY:
        raise KeyError(f"unknown action: {name}")
    return _REGISTRY[name]
```

### 5.2 The standard catalogue

The core layer ships these actions; every module gets them for free:

| Action | Effect | Idempotent |
|---|---|---|
| `core.tasks.create` | Creates a task assigned to a user / role / queue | Yes (via idempotency_key) |
| `core.tasks.complete` | Marks a task complete (used by approval chains) | Yes |
| `core.notifications.send` | Sends a notification via the channel selector (in-app/WhatsApp/email) | Yes |
| `core.events.publish` | Publishes a domain event | Yes (event id derived from instance+step) |
| `core.context.set` | Writes a value into workflow context | Yes |
| `core.workflow.wait_for_event` | Parks the instance waiting for an event matching a filter | Yes (it's the wait primitive) |
| `core.workflow.wait_for_duration` | Parks the instance for N seconds (SLA timers) | Yes |
| `core.workflow.abort` | Terminates the instance with `status=failed` and an error reason | Yes |
| `core.integrations.call` | Invokes a registered connector method | Module-dependent |

Modules register their own actions on top:

| Action | Owning module |
|---|---|
| `acc.tally.push` | Accounts |
| `acc.invoice.reconcile` | Accounts |
| `ops.dispatch.mark_handed_over` | Operations |
| `ops.dispatch.create` | Operations |
| `inv.stock.reserve` | Inventory |
| `inv.stock.adjust` | Inventory |
| `cs.ticket.escalate` | Customer Service |
| `cs.ticket.assign` | Customer Service |

### 5.3 Action contract

Every action is a function that takes an `ActionContext` and a `params` dict, returns a JSON-serializable dict.

```python
# app/modules/accounts/__init__.py (sketch)

from app.core.workflows.actions import register, ActionSpec, RetryPolicy
from app.modules.accounts.services import tally_service


def _tally_push(ctx, params):
    invoice_id = params["invoice_id"]
    push_id = tally_service.push(
        tenant_id=ctx["tenant_id"],
        invoice_id=invoice_id,
        idempotency_key=ctx["idempotency_key"],
    )
    return {"push_id": push_id, "invoice_id": invoice_id}


register(ActionSpec(
    name="acc.tally.push",
    handler=_tally_push,
    input_schema={
        "type": "object",
        "required": ["invoice_id"],
        "properties": {"invoice_id": {"type": "string", "format": "uuid"}},
    },
    output_schema={
        "type": "object",
        "required": ["push_id", "invoice_id"],
        "properties": {
            "push_id": {"type": "string"},
            "invoice_id": {"type": "string", "format": "uuid"},
        },
    },
    idempotent=True,
    retry_policy=RetryPolicy(max_attempts=5, backoff_seconds=(10, 60, 300, 900, 3600)),
))
```

Three properties matter for every action:

1. **Signature** — the JSON Schema for `params` and output. Validated on every call. Misshaped params fail the step with a permanent error (no retry).
2. **Idempotency contract** — the engine passes an `idempotency_key` derived from `(instance_id, step_name, attempt_group)`. If `idempotent=True`, the action handler must use this key to deduplicate at its system of record (Tally has its own deduplication, our `tasks` table has a unique constraint on `(tenant_id, idempotency_key)`, etc.).
3. **Retry policy** — per-action. `acc.tally.push` retries on `TallyConnectionError` with long backoff (Tally goes down for minutes). `core.notifications.send` retries with short backoff. `core.workflow.abort` does not retry.

### 5.4 Action parameter interpolation

Action params can reference the workflow context using `${...}` syntax. Interpolation runs through the same condition evaluator (validate + safe eval) before the action is called:

```yaml
- action: core.tasks.create
  params:
    title: "Approve invoice ${context.invoice.invoice_number}"
    assigned_to_role: "founder"
    related_entity:
      type: "invoice"
      id: "${context.invoice.id}"
```

---

## 6. Workflow definition format

YAML, because every admin we will ever hire can edit it and every reviewer can read it. The same definition is convertible to JSON for the API; YAML is the *canonical* storage format because it survives diffs and comments.

### 6.1 Grammar

```yaml
name: string                  # human-readable; unique per tenant
version: int                  # monotonically increasing
description: string           # optional

trigger:
  type: event | schedule | manual | whatsapp.intent
  # event:
  name: string                # event name to match
  filter: string              # condition expression evaluated on event.payload
  # schedule:
  cron: string
  # whatsapp.intent:
  verb: string

context_init: dict            # optional initial context overlay

steps:
  - name: string              # step id, unique within definition
    description: string       # optional
    when: string              # optional condition; step skipped if false
    actions:                  # ordered list
      - action: string        # registered action name
        params: dict          # action params; supports ${...} interpolation
        store_as: string      # optional; key under which to store action output
    on_success: string        # next step name (defaults to next in list)
    on_failure: string        # step to jump to if any action fails permanently
    wait:                     # optional; if present, after actions, park here
      type: event | duration
      # event:
      event_name: string
      match: string           # condition on event.payload
      timeout_seconds: int    # optional
      on_timeout: string      # step name to jump to on timeout
      # duration:
      seconds: int

terminal_steps:               # optional; explicit terminal markers
  - name: string
    status: completed | failed
```

### 6.2 Worked example — Accounts founder approval

The scenario: an invoice over INR 1,00,000 requires founder approval. On approval, we publish `acc.invoice.verified`. On rejection, `acc.invoice.rejected`. The whole thing is one workflow.

```yaml
name: accounts.founder_approval
version: 3
description: |
  Route high-value invoices through a founder approval gate.
  Triggered by acc.invoice.requires_founder_approval.

trigger:
  type: event
  name: acc.invoice.requires_founder_approval
  filter: "event.payload.amount > tenant_config.founder_approval_threshold_inr"

context_init:
  invoice: "${event.payload}"

steps:

  - name: gate_amount_threshold
    when: "context.invoice.amount > 100000"
    actions: []
    on_success: create_approval_task
    on_failure: abort_below_threshold

  - name: create_approval_task
    actions:
      - action: core.tasks.create
        params:
          title: "Approve invoice ${context.invoice.invoice_number} (INR ${context.invoice.amount})"
          description: "Vendor: ${context.invoice.vendor_name}. Amount above threshold."
          assigned_to_role: "founder"
          related_entity:
            type: "invoice"
            id: "${context.invoice.id}"
          due_in_hours: 48
        store_as: approval_task
    wait:
      type: event
      event_name: core.task.completed
      match: "event.payload.task_id == context.approval_task.id"
      timeout_seconds: 172800   # 48h
      on_timeout: notify_timeout
    on_success: route_on_decision

  - name: route_on_decision
    when: "context.event.payload.outcome == 'approved'"
    actions:
      - action: core.events.publish
        params:
          name: acc.invoice.verified
          payload:
            invoice_id: "${context.invoice.id}"
            approved_by: "${context.event.payload.completed_by}"
            approved_at: "${context.event.payload.completed_at}"
    on_success: end_approved
    on_failure: emit_rejected

  - name: emit_rejected
    actions:
      - action: core.events.publish
        params:
          name: acc.invoice.rejected
          payload:
            invoice_id: "${context.invoice.id}"
            rejected_by: "${context.event.payload.completed_by}"
            reason: "${context.event.payload.rejection_reason}"
    on_success: end_rejected

  - name: notify_timeout
    actions:
      - action: core.notifications.send
        params:
          to_role: "finance_head"
          channel: ["whatsapp", "in_app"]
          template: "founder_approval_timeout"
          template_params:
            invoice_number: "${context.invoice.invoice_number}"
            amount: "${context.invoice.amount}"
      - action: core.events.publish
        params:
          name: acc.invoice.approval_timed_out
          payload:
            invoice_id: "${context.invoice.id}"
    on_success: end_timed_out

  - name: abort_below_threshold
    actions:
      - action: core.workflow.abort
        params:
          reason: "Amount below founder threshold; should not have triggered."

terminal_steps:
  - name: end_approved
    status: completed
  - name: end_rejected
    status: completed
  - name: end_timed_out
    status: completed
```

Read this top-to-bottom and the entire business policy is legible. No Python, no service code, no `if amount > 100000` buried in `invoice_service.py`. If the founder wants to change the threshold to INR 2,00,000, an admin edits `tenant_config.founder_approval_threshold_inr`. If the chain becomes `accountant → finance_head → founder`, an admin adds two more wait-for-task steps. No deploy.

---

## 7. Persistence model

Three tables, in `app/core/workflows/models.py`. All carry `tenant_id`. All migrations in `alembic/versions/0002_platform_core.py`.

### 7.1 `workflow_definitions`

```sql
CREATE TABLE workflow_definitions (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id         UUID NOT NULL REFERENCES tenants(id),
    name              TEXT NOT NULL,                  -- e.g. accounts.founder_approval
    version           INT  NOT NULL,
    yaml              TEXT NOT NULL,                  -- canonical storage
    parsed            JSONB NOT NULL,                 -- normalized form for fast lookup
    trigger_kind      TEXT NOT NULL,                  -- event | schedule | manual | whatsapp.intent
    trigger_key       TEXT NOT NULL,                  -- event name | cron | verb
    status            TEXT NOT NULL DEFAULT 'active', -- active | retired | draft
    created_by        UUID NOT NULL REFERENCES users(id),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, name, version)
);

CREATE INDEX ix_wfdef_trigger
    ON workflow_definitions (tenant_id, trigger_kind, trigger_key, status);
```

**Versioning.** New versions coexist. When a new version is published, the previous version stays in `active` until explicitly `retired`, at which point new instances cannot be created against it — but running instances continue using their pinned version. We never edit a definition in place. Edits create a new version.

### 7.2 `workflow_instances`

```sql
CREATE TABLE workflow_instances (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES tenants(id),
    definition_id       UUID NOT NULL REFERENCES workflow_definitions(id),
    trigger_event_id    UUID,                          -- nullable for manual/schedule
    status              TEXT NOT NULL,                 -- pending | running | waiting | completed | failed | parked
    current_step        TEXT,                          -- step name; null until first step entered
    context             JSONB NOT NULL DEFAULT '{}'::jsonb,
    wait_descriptor     JSONB,                         -- if waiting: {event_name, match, expires_at}
    started_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at        TIMESTAMPTZ,
    error               JSONB,                         -- {step, action, message, traceback}
    attempt_seq         INT NOT NULL DEFAULT 0         -- monotonic step attempt counter
);

CREATE INDEX ix_wfinst_status      ON workflow_instances (tenant_id, status);
CREATE INDEX ix_wfinst_waiting_evt ON workflow_instances (tenant_id, status)
    WHERE status = 'waiting';
CREATE INDEX ix_wfinst_definition  ON workflow_instances (definition_id);
```

The partial index on `status = 'waiting'` is what makes wakeup cheap: when an event arrives, we filter to waiting instances and probe their `wait_descriptor`.

### 7.3 `workflow_step_runs`

```sql
CREATE TABLE workflow_step_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    instance_id     UUID NOT NULL REFERENCES workflow_instances(id) ON DELETE CASCADE,
    step_name       TEXT NOT NULL,
    attempt         INT  NOT NULL,                  -- 1-indexed; retries increment
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at    TIMESTAMPTZ,
    status          TEXT NOT NULL,                  -- running | succeeded | failed | retrying | skipped
    actions_log     JSONB,                          -- [{action, params_hash, output, duration_ms, error}]
    output          JSONB,                          -- merged action outputs (the delta into context)
    error           JSONB
);

CREATE INDEX ix_wfsteprun_instance ON workflow_step_runs (instance_id, started_at);
```

Every step run, every attempt, is one row. This is the audit trail for debugging "why did this invoice not get approved?" — a tester opens the instance, sees the linear sequence of `workflow_step_runs`, sees exactly which condition was false or which action raised.

### 7.4 What we deliberately do *not* persist

- **The DAG graph as separate rows.** It lives in `parsed` JSONB. Querying which steps exist is a JSON path. Adding a separate `workflow_steps` table is normalization for normalization's sake; we never query individual step *definitions* across instances.
- **The full context history.** Context is overwritten as it grows. The `actions_log` per step run gives us delta-level reconstructability, which is what we actually need.

---

## 8. The runner

The runner is a single function: `advance(instance_id, trigger_event=None)`. Everything else feeds into it.

### 8.1 Entry points

```python
# app/core/workflows/runner.py (sketch)

def on_event_published(event: Event) -> None:
    """Called by the event bus for every event."""
    # 1. New instances: find definitions whose entry trigger matches.
    for definition in _find_matching_entry_definitions(event):
        if _evaluate_trigger_filter(definition, event):
            instance = _instantiate(definition, event)
            advance(instance.id)

    # 2. Waiting instances: find ones whose wait_descriptor matches.
    for instance in _find_waiting_instances(event):
        if _matches_wait(instance.wait_descriptor, event):
            advance(instance.id, trigger_event=event)


def advance(instance_id: UUID, trigger_event: Event | None = None) -> None:
    with transactional_session() as session:
        instance = session.get(WorkflowInstance, instance_id, with_for_update=True)
        if instance.status in {"completed", "failed"}:
            return
        if trigger_event is not None:
            instance.context["event"] = trigger_event.to_dict()
            instance.wait_descriptor = None
            instance.status = "running"

        definition = session.get(WorkflowDefinition, instance.definition_id)
        step = _resolve_current_step(instance, definition)

        while step is not None:
            outcome = _execute_step(instance, definition, step, session)
            if outcome.kind == "advance":
                step = _next_step(definition, step, outcome)
            elif outcome.kind == "wait":
                instance.status = "waiting"
                instance.wait_descriptor = outcome.wait_descriptor
                instance.current_step = step.name
                return
            elif outcome.kind == "terminal":
                instance.status = outcome.terminal_status
                instance.completed_at = now()
                return
            elif outcome.kind == "park":
                instance.status = "parked"
                instance.error = outcome.error
                _alert_parked(instance)
                return
```

### 8.2 Step execution

```python
def _execute_step(instance, definition, step, session):
    # Skip via 'when'
    if step.when and not evaluate(step.when, _eval_context(instance)):
        _log_step_run(session, instance, step, status="skipped")
        return Outcome.advance(via="when_false")

    step_run = _start_step_run(session, instance, step)

    try:
        for action_call in step.actions:
            spec = action_registry.get(action_call.action)
            params = _interpolate(action_call.params, instance.context)
            _validate_params(spec, params)
            idempotency_key = _idempotency_key(instance, step, action_call)

            output = _invoke_with_retry(
                spec,
                ActionContext(
                    tenant_id=instance.tenant_id,
                    instance_id=instance.id,
                    step_name=step.name,
                    workflow_context=instance.context,
                    idempotency_key=idempotency_key,
                ),
                params,
            )

            _validate_output(spec, output)
            if action_call.store_as:
                instance.context[action_call.store_as] = output
            step_run.actions_log.append(_log_entry(action_call, params, output))
            session.flush()  # persist incrementally

    except PermanentActionError as e:
        _fail_step_run(session, step_run, error=e)
        if step.on_failure:
            return Outcome.advance(via="on_failure", to=step.on_failure)
        return Outcome.park(error=e)

    _complete_step_run(session, step_run)

    if step.wait:
        return Outcome.wait(wait_descriptor=_compile_wait(step.wait, instance.context))
    if step.name in _terminal_step_names(definition):
        return Outcome.terminal(status=_terminal_status(definition, step))
    return Outcome.advance()
```

### 8.3 Retries and backoff

`_invoke_with_retry` honors the action's `RetryPolicy`. Retries happen **inline** for short backoffs (< 60s) and **off-thread** via RQ for longer ones — the runner enqueues a `workflow.resume` RQ job at `next_attempt_at`, marks the instance `waiting` with a duration descriptor, and returns. When the RQ job fires, it calls `advance(instance_id)` again. This is the same mechanism that powers `core.workflow.wait_for_duration`.

We distinguish two error classes:

- `TransientActionError` — retry per policy. Examples: network timeouts, 503 from Tally, RQ Redis blip.
- `PermanentActionError` — do not retry. Examples: schema validation failure, RBAC denial, business rule violation. Goes to `on_failure` or parks.

Action handlers must raise the right class. Defaulting to `TransientActionError` is a bug because it masks permanent failures behind retry storms.

### 8.4 Poison failures

If an action exhausts its retry policy with `TransientActionError`, the step is failed permanently, the instance is parked (`status='parked'`), and an alert fires (`fi.alert.raised` event, plus an in-app notification to the workflow ops queue). Parked instances are never auto-retried. An admin must either:

1. Resolve the upstream cause and click "resume" (which calls `advance` again), or
2. Click "abort" (which sets `status='failed'` and publishes `core.workflow.failed`).

This is deliberate. Auto-retry of parked workflows is how you get a hospital bill for `tally.push` running 40,000 times against a corrupted invoice.

---

## 9. State and resumability

The workflow context is the source of truth for an instance. Every action's output is appended via `store_as`, and the engine flushes the SQLAlchemy session after each action. Concretely:

- If the worker crashes between action 2 and action 3 of a 5-action step, on recovery the runner sees `step_run.status='running'`, attempt N, with actions 1 and 2 logged. It re-enters the same step at attempt N+1.
- Idempotent actions (the default and the strongly preferred design) are safely re-invoked because their handlers use the deterministic `idempotency_key`.
- Non-idempotent actions (rare — we discourage them) must declare `idempotent=False`. The runner then refuses to retry them and parks the instance on any failure.

This is the property Temporal sells: **workflows survive process death.** We get it not by replaying deterministic code (Temporal's model) but by persisting the context and the step-run cursor after every action. The trade-off: we cannot trivially "replay" a workflow against a new definition version (Temporal can, sometimes). Given our actual use cases, that is the right trade.

### 9.1 Context schema

The `context` JSONB is loosely structured by convention:

```json
{
  "event": { ... },              // the most recent triggering event (overwritten on each wake)
  "invoice": { ... },            // domain entity, set by context_init or actions
  "approval_task": { ... },      // output of an earlier action, store_as: approval_task
  "_meta": {
    "instance_id": "...",
    "definition_name": "...",
    "definition_version": 3
  }
}
```

We do not enforce a schema on the context. Each workflow definition is the schema. We *do* enforce that every action's output conforms to its declared `output_schema` — so context contents are auditable downstream.

---

## 10. Approval chains as workflows

There is **no separate approval engine** in Nyx. An approval chain — `accountant → finance_head → founder` — is just a workflow with N wait-for-task steps. This is the single biggest reason the workflow engine pays for itself.

Sketch:

```yaml
name: accounts.invoice.three_tier_approval
version: 1

trigger:
  type: event
  name: acc.invoice.extracted
  filter: "event.payload.amount > 50000"

context_init:
  invoice: "${event.payload}"

steps:
  - name: tier_accountant
    actions:
      - action: core.tasks.create
        params:
          title: "Verify invoice ${context.invoice.invoice_number}"
          assigned_to_role: "accountant"
          related_entity: { type: invoice, id: "${context.invoice.id}" }
        store_as: tier1_task
    wait:
      type: event
      event_name: core.task.completed
      match: "event.payload.task_id == context.tier1_task.id"
    on_success: gate_tier_accountant

  - name: gate_tier_accountant
    when: "context.event.payload.outcome == 'approved'"
    actions: []
    on_success: tier_finance_head
    on_failure: emit_rejected_at_tier1

  - name: tier_finance_head
    when: "context.invoice.amount > 100000"
    actions:
      - action: core.tasks.create
        params:
          title: "Approve invoice ${context.invoice.invoice_number}"
          assigned_to_role: "finance_head"
          related_entity: { type: invoice, id: "${context.invoice.id}" }
        store_as: tier2_task
    wait:
      type: event
      event_name: core.task.completed
      match: "event.payload.task_id == context.tier2_task.id"
    on_success: gate_tier_finance_head

  # ... and so on for founder tier

  - name: emit_final_verified
    actions:
      - action: core.events.publish
        params:
          name: acc.invoice.verified
          payload: { invoice_id: "${context.invoice.id}" }
```

The same pattern handles every approval chain in the system: stock transfer approval, ticket escalation, vendor onboarding, customer refund. The `core.tasks` module supplies the human-in-the-loop primitive; the workflow engine supplies the orchestration. No bespoke approval service exists or needs to exist.

---

## 11. Waiting / async steps

A wait step parks the instance in the database. No worker thread sleeps. No connection holds open. The instance's row has `status='waiting'` and a `wait_descriptor`:

```json
{
  "kind": "event",
  "event_name": "core.task.completed",
  "match": "event.payload.task_id == 'a3f...'",
  "expires_at": "2026-06-21T09:00:00Z"
}
```

### 11.1 Wake on event

When the event bus publishes any event, it calls `on_event_published`, which performs:

```sql
SELECT id
FROM workflow_instances
WHERE tenant_id = :tenant
  AND status = 'waiting'
  AND wait_descriptor->>'kind' = 'event'
  AND wait_descriptor->>'event_name' = :event_name;
```

The partial index on `(tenant_id, status) WHERE status = 'waiting'` makes this O(waiting instances) which is small in practice (~hundreds, not millions, for SME workloads). For each row returned, we evaluate the `match` expression against the event payload; matching rows have their `advance()` called.

If the wait carries `timeout_seconds`, the runner also enqueues an RQ job at `expires_at` that, on firing, will jump to `on_timeout` if the instance is still waiting.

### 11.2 Wake on duration

A duration wait is implemented as an RQ-scheduled job that calls `advance(instance_id)` at the target time. No event match, no condition — just resume.

### 11.3 Why not a poller

A naive design would have a poller scan `workflow_instances` every second looking for things to do. We do not. Events drive wakeups. Timers drive duration wakeups. The DB is queried only when something happens. This keeps idle CPU near zero and scales linearly with throughput, not with instance count.

The one polling job we *do* run is a daily "find waiting instances that should have timed out but didn't" sweep, as a defense-in-depth backstop against missed RQ jobs. It is not the primary mechanism.

---

## 12. Editing without redeploying

Workflow definitions are rows in `workflow_definitions`. Admins edit them in the `/workflows` section of the dashboard.

### 12.1 The edit flow

1. Admin opens a definition. UI fetches the YAML.
2. Admin edits in a monaco editor with the workflow YAML schema providing validation hints.
3. Admin clicks "Save as v(N+1)". Backend:
   - Parses YAML
   - Validates every condition expression
   - Validates every action reference (must exist in the registry)
   - Validates the JSON Schema of every action's `params` against the action's `input_schema`
   - Inserts a new row with `version = N+1`, `status='draft'`
4. Admin clicks "Publish". `status='active'`. The previous version stays `active` (both can match the same trigger; the engine picks the *highest active version*).
5. Admin can click "Retire" on the previous version once they're satisfied.

### 12.2 Cache and reload

The engine caches `parsed` JSONB in-process keyed by `(definition_id, version)`. On any write to `workflow_definitions`, the cache is invalidated via Redis pub/sub (so multi-worker setups stay coherent). New instances created after the invalidation pick up the new definition; in-flight instances keep their pinned version.

### 12.3 Why YAML editing instead of a drag-drop builder

A drag-drop visual builder is the most-requested, least-useful workflow feature. Reasons we do not build one in v1:

- Admins who can author a workflow can author YAML. Admins who can't author YAML cannot author a correct workflow visually either — they just produce broken graphs with prettier graphics.
- The YAML *is* the schema. A visual builder has to round-trip to YAML anyway. The translation layer is more code than it's worth.
- A diff in git or in the audit log of a YAML change is human-readable. A diff of a visual graph state is not.

A read-only graphical *visualizer* of a workflow definition (rendering the YAML as a flowchart) is welcome and is in scope. The visualizer renders; the editor edits YAML. This is the same trade-off Kubernetes made and it is correct.

---

## 13. Testing workflows

The engine ships a test harness in `app/core/workflows/testing.py` for unit-testing definitions without spinning up a worker.

### 13.1 The harness API

```python
# example test
from app.core.workflows.testing import WorkflowTestRunner

def test_founder_approval_high_amount_approved():
    runner = WorkflowTestRunner.from_yaml_file(
        "app/modules/accounts/workflows/founder_approval.yaml"
    )

    instance = runner.start(
        trigger_event={
            "name": "acc.invoice.requires_founder_approval",
            "payload": {
                "id": "inv-1",
                "invoice_number": "INV-001",
                "amount": 250000,
                "vendor_name": "Acme Co",
            },
        },
        tenant_config={"founder_approval_threshold_inr": 100000},
    )

    # Assert: the workflow created an approval task
    task = runner.last_action_call("core.tasks.create")
    assert task.params["assigned_to_role"] == "founder"

    # Simulate: founder approves
    runner.send_event({
        "name": "core.task.completed",
        "payload": {
            "task_id": task.output["task_id"],
            "outcome": "approved",
            "completed_by": "user-founder",
            "completed_at": "2026-06-19T10:00:00Z",
        },
    })

    # Assert: the workflow emitted the verified event and terminated
    assert runner.event_was_published("acc.invoice.verified")
    assert instance.status == "completed"
    assert instance.current_step == "end_approved"


def test_founder_approval_timeout():
    runner = WorkflowTestRunner.from_yaml_file("...founder_approval.yaml")
    instance = runner.start(trigger_event={...})

    # Advance virtual time past the 48h wait
    runner.advance_time(hours=49)

    assert runner.event_was_published("acc.invoice.approval_timed_out")
    assert instance.current_step == "end_timed_out"


def test_rejection_path():
    runner = WorkflowTestRunner.from_yaml_file("...founder_approval.yaml")
    instance = runner.start(trigger_event={...})
    task = runner.last_action_call("core.tasks.create")
    runner.send_event({
        "name": "core.task.completed",
        "payload": {
            "task_id": task.output["task_id"],
            "outcome": "rejected",
            "rejection_reason": "duplicate",
        },
    })
    assert runner.event_was_published("acc.invoice.rejected")
```

### 13.2 What the harness does

- Loads the YAML, parses, validates against the same schema the production engine uses.
- Stubs the action registry: every action becomes a recorder that captures `(name, params)` and returns a configurable canned output.
- Runs the engine with an in-memory event bus and a virtual clock.
- Exposes assertion helpers: `last_action_call`, `all_action_calls`, `event_was_published`, `terminal_status`.

This is the only way to keep workflow logic correct over time. Without it, a workflow YAML edit ships untested into production and an invoice silently routes to the wrong queue for two weeks before anyone notices.

---

## 14. Anti-goals

These are explicit choices we are not making. Each is a credible feature that would dilute the engine.

### 14.1 No Turing-complete workflow language

The workflow DSL has steps, conditions, actions, edges, waits. It does not have loops, recursion, function definitions, modules, or generic computation. If a workflow requires a loop, the right answer is: emit an event N times from an action that runs once, or model the iteration as recurring schedule. Workflows that need to compute belong in an action, not in the workflow language.

### 14.2 No embedded scripting beyond conditions

We will not add an `eval:` step type, a `python:` step type, a `lua:` step type, or any other in-line scripting. Every side effect is a registered action. Adding a new action is a 30-line code change; it is intentionally just slightly more work than would tempt someone to embed a script.

### 14.3 No UI-only no-code drag-drop builder

YAML editor with schema validation in v1. Read-only graph visualizer in v1. Visual editor: deferred indefinitely, and only revisited if we have a strict accessibility case from a real customer who cannot author YAML and whose workflow needs are simple enough to express visually.

### 14.4 No cross-tenant workflow templates in v1

Every definition belongs to one tenant. We do not ship a "marketplace" or a "template library" that lets tenant A clone tenant B's workflow. The data model supports it (definitions are tenant-scoped rows; copying is trivial) but the product surface does not, because shared templates create cross-tenant coupling pressure on action signatures and event schemas that we are not yet equipped to manage.

### 14.5 No "AI agent" steps

We will not add a `llm.decide` action or an `agent.run` action that lets an LLM choose the next step. The principle (P6) is explicit: deterministic actions are rule-based; AI is for fuzzy inputs only. A workflow that branches on LLM output is a workflow that is non-reproducible, non-auditable, and non-debuggable. If an LLM classifies a free-text WhatsApp message into a verb, that happens in the Conversation Runtime *before* the workflow is triggered — the workflow sees a deterministic verb, never a probability.

### 14.6 No sub-workflow / "call-another-workflow" primitive in v1

A step cannot "call" another workflow synchronously. If workflow A needs to trigger workflow B, A emits an event, B's trigger picks it up. This is verbose for some patterns but keeps the engine's mental model flat: one workflow, one instance, one current step. Sub-workflows can come later if real use cases demand them; in two years of similar systems they have not been needed.

### 14.7 No automatic compensation / saga semantics

If an action fails midway through a multi-action step, the engine does not "undo" the prior actions. The workflow author is responsible for designing compensating actions if rollback is required (e.g., explicitly `on_failure: release_reservation`). Sagas are seductive and almost always wrong: they imply business semantics that the engine does not actually have visibility into. We surface failures cleanly; we do not pretend to fix them.

---

## Appendix A — File layout for the engine

```
app/core/workflows/
├── __init__.py             # exports: register_action, get_action, runner.advance
├── models.py               # SQLAlchemy: WorkflowDefinition, WorkflowInstance, WorkflowStepRun
├── schemas.py              # Pydantic: definition CRUD, instance views
├── dsl.py                  # YAML parse + schema validate + condition pre-validation
├── conditions.py           # safe expression validator + evaluator
├── interpolation.py        # ${...} param interpolation (uses conditions evaluator)
├── actions.py              # ActionSpec, RetryPolicy, registry, register/get
├── runner.py               # advance(), on_event_published(), step execution
├── waits.py                # wait_descriptor compile + match + timeout scheduling
├── cache.py                # parsed-definition cache + Redis invalidation
├── testing.py              # WorkflowTestRunner (in-memory bus, virtual clock, action stubs)
├── routes.py               # /api/v1/workflows: list/get/create/publish/retire/instances
└── tests/
    ├── test_conditions.py
    ├── test_runner.py
    ├── test_waits.py
    ├── test_retries.py
    └── test_definitions_e2e.py
```

## Appendix B — Action signature checklist

For every action a module registers, the author must answer:

1. What does it do — one sentence.
2. What are its `params` — JSON Schema.
3. What does it return — JSON Schema.
4. Is it idempotent — yes/no, and if yes, what key is the dedup based on.
5. What errors does it raise — list of `TransientActionError` and `PermanentActionError` cases.
6. What is its retry policy — max attempts, backoff schedule.
7. What is the worst case if it runs twice — explicitly stated.

If any of these is unanswered, the action does not get merged.

## Appendix C — Operational SLOs for the engine

- **Time from event publish to first matching workflow step entered:** p95 < 200ms in-process.
- **Time from action completion to next action start:** p95 < 50ms (in-process, no queue hop).
- **Time from wait-event-arrival to instance wake:** p95 < 500ms.
- **Parked-instance alert latency:** < 60s from park to founder alert.
- **Definition reload after edit:** < 5s across all workers (Redis pub/sub invalidation).

If we miss these, we tune. We do not switch to Temporal.
