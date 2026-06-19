# 05 — Event Bus

The event bus is the single most important piece of platform infrastructure in Nyx. If RBAC is what protects the system, and workflows are what drive it, events are what *connect* it. Get this layer wrong and the modular monolith collapses into a tangle of cross-imports inside six months.

This document specifies what an event is, how it is published, how it is delivered, how it is persisted, and the constraints under which subscribers operate.

## 1. Why an event bus, not direct calls

A naive modular monolith lets modules call each other's services directly. `acc.invoice_service.reconcile()` finishes and calls `fi.snapshot_service.bump_recon_count()` and `audit.log()` and `notifications.send()`. This works for two modules. By the fourth module it produces a dependency graph where Accounts imports from FI, FI imports from Operations, Operations imports from Accounts to look up invoices for an order — and the modular monolith has rotted into a ball of mud.

The event bus exists to **invert the dependency**. Instead of a publisher knowing its consumers, consumers know what they care about. Accounts emits `acc.invoice.reconciled` and walks away. It does not know — and **must not know** — that:

- The audit log writes a row.
- Founder Intelligence increments today's `recon_success` counter.
- The workflow engine advances any instance whose current step waits on this event.
- Notifications fire a "reconciled" message to the AP clerk.
- Operations marks the linked PO as paid.

Five subscribers, zero changes to Accounts. Adding a sixth subscriber tomorrow — say, an external webhook to push to the customer's BI tool — is a one-file change in `core/integrations/webhook/` plus a subscription registration. Accounts does not learn about it.

Two consumers are architecturally privileged and informed by this design:

- **Audit Log** subscribes to `*`. Every event in the system writes one audit row. This is what makes Nyx a system of record rather than a glorified CRUD UI. Audit is a synchronous in-transaction subscriber (see §4) so that a domain event and its audit row commit or rollback together.
- **Founder Intelligence** subscribes to nearly everything, but asynchronously. Its aggregates are eventually consistent — by design — so a slow FI handler must never block the transaction that emitted the event. FI is the canonical example of why we need a two-tier delivery model.

The bus also gives us *replayability* (§8) and *traceability* (§10), both of which are impossible if modules call each other directly.

## 2. Event naming convention

All event types follow:

```
<module>.<entity>.<verb_past_tense>
```

- `<module>` is the three-letter module code from `02-modules.md` (`acc`, `ops`, `inv`, `cs`, `fi`) or a reserved core namespace (see below).
- `<entity>` is the noun the event is about, lowercase, singular. `invoice`, `dispatch`, `ticket`, `stock`.
- `<verb_past_tense>` is what happened. Past tense, always. `reconciled`, `handed_over`, `escalated`, `below_threshold`. Never `reconcile`, never `reconciling`. The event is the record of a thing that already happened.

Examples:

- `acc.invoice.reconciled`
- `acc.invoice.tally_push_failed`
- `ops.dispatch.handed_over`
- `inv.stock.below_threshold`
- `cs.ticket.escalated`
- `fi.alert.raised`

### Reserved namespaces

Three top-level namespaces are reserved for the platform itself and **must not** be used by modules:

| Namespace | Owned by | Purpose |
|---|---|---|
| `core.*` | `app/core/` | Platform lifecycle: `core.user.created`, `core.tenant.provisioned`, `core.session.started`. |
| `workflow.*` | `app/core/workflows/` | Workflow runtime: `workflow.instance.started`, `workflow.step.completed`, `workflow.approval.granted`, `workflow.instance.failed`. |
| `fi.*` | `app/modules/founder_intelligence/` | FI-emitted alerts and snapshots. Modules subscribe; modules do not emit. |

A module emitting into a reserved namespace is a review-blocking error. The lint config (future) will flag string literals matching these prefixes outside their owning folder.

### Versioning in names — no

We do **not** put versions in event names (`acc.invoice.reconciled.v2`). Version lives in the `version` integer field on the event. Subscribers branch on `event.version` if they must. This keeps subscription tables sane and avoids the "what happened to v1 subscribers" question.

## 3. Event schema

Every event — sync or async, persisted or not — conforms to the same shape.

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | UUID v7 | yes | Unique per event. UUIDv7 so the id is time-sortable, which simplifies replay and debugging. |
| `type` | str | yes | The `module.entity.verb` name. |
| `tenant_id` | UUID | yes | Owning tenant. Every event is tenant-scoped; cross-tenant events are forbidden. |
| `occurred_at` | datetime (UTC) | yes | When the business event happened, set by the publisher. **Not** the time of persistence. |
| `actor_id` | UUID \| str | yes | The user who caused the event, OR a literal sentinel like `"system:scheduler"`, `"system:workflow_runner"`, `"system:integration:shopify"`. Never null. |
| `subject_id` | UUID | yes | The id of the primary entity the event is about (the invoice id, the dispatch id, the ticket id). Used for per-subject ordering (§9). |
| `correlation_id` | UUID | yes | Groups all events stemming from one user action / one root cause. Propagates across module boundaries. See §10. |
| `causation_id` | UUID \| null | yes | The id of the event that directly caused this one. Null only for root events (the event triggered by direct user action). |
| `payload` | JSONB | yes | The event-specific data. Snake_case keys. Should contain enough for any subscriber to act without re-querying — but never sensitive data we can re-fetch. |
| `version` | int | yes | Schema version of this event type. Starts at 1. Bumped only on a breaking payload change. |

### Pydantic sketch

```python
# app/core/events/registry.py
from datetime import datetime
from typing import Any, Literal
from uuid import UUID
from pydantic import BaseModel, Field

ActorId = UUID | Literal[
    "system:scheduler",
    "system:workflow_runner",
    "system:integration",
    "system:replay",
]

class Event(BaseModel):
    id: UUID
    type: str                      # 'acc.invoice.reconciled'
    tenant_id: UUID
    occurred_at: datetime
    actor_id: ActorId
    subject_id: UUID
    correlation_id: UUID
    causation_id: UUID | None
    payload: dict[str, Any]
    version: int = 1

    model_config = {"frozen": True}  # events are immutable values
```

Module-specific event classes are thin typed wrappers that constrain `type` and `payload`:

```python
# app/modules/accounts/events.py
class InvoiceReconciledPayload(BaseModel):
    invoice_id: UUID
    vendor_id: UUID
    amount: Decimal
    matched_po_id: UUID | None
    reconciliation_record_id: UUID

class InvoiceReconciled(Event):
    type: Literal["acc.invoice.reconciled"] = "acc.invoice.reconciled"
    payload: InvoiceReconciledPayload
```

Subscribers receive these typed subclasses, not raw dicts.

## 4. Two-tier delivery

Nyx runs **two delivery tiers**, in this order, for every published event:

```
                ┌────────────────────────────────────┐
                │   publisher (inside a DB tx)       │
                └────────────────┬───────────────────┘
                                 │
                                 ▼
                ┌────────────────────────────────────┐
                │   Tier 1: in-process synchronous   │
                │   (same DB tx, same request)       │
                │                                    │
                │   - audit log writer               │
                │   - workflow runner advancement    │
                │   - intra-module reactions         │
                └────────────────┬───────────────────┘
                                 │
                          tx commits
                                 │
                                 ▼
                ┌────────────────────────────────────┐
                │   Tier 2: Redis-backed async       │
                │   (RQ job per subscriber)          │
                │                                    │
                │   - FI aggregate updaters          │
                │   - notification dispatch          │
                │   - external webhooks              │
                │   - cross-module reactions         │
                └────────────────────────────────────┘
```

### Tier 1 — synchronous, in-process, in-transaction

Tier 1 handlers run inside the same DB transaction as the publisher. They receive the same `Session`. If they raise, the transaction rolls back and the event is never published. Use Tier 1 only when:

1. The handler's work **must** be atomic with the publisher's work. Audit log entries are the canonical example: if the invoice reconciliation rolls back, the "InvoiceReconciled" audit row must not exist.
2. The handler is fast (microseconds to low milliseconds). Network calls, LLM calls, external API calls are forbidden in Tier 1.
3. The handler logically *belongs* to the same request. Workflow advancement is a good example: when a step's completing event fires, the workflow runner picks the next step in the same transaction so that the state machine is always consistent on read.

Tier 1 handlers are registered as regular Python callables and invoked in publication order from `bus.publish()`.

### Tier 2 — asynchronous, Redis-backed, eventually consistent

After the publishing transaction commits, the event is fanned out via Redis to one RQ job per registered Tier 2 subscriber. Each subscriber runs in its own job, its own DB session, its own transaction. Failure of one subscriber does not affect another.

Use Tier 2 for:

- Aggregate updates (FI): a slow group-by query updating `fi_kpi_*` should not block invoice reconciliation.
- Notifications: WhatsApp / email / in-app sends are network-bound and slow.
- External webhooks: a customer's BI ingester is unpredictable.
- Cross-module reactions where eventual consistency is acceptable. (Almost all of them.)

### Choosing a tier

A handler goes in Tier 1 if and only if **all** of the following are true:

- The work mutates a table in the same database as the publisher.
- The work must succeed or fail with the publisher's transaction.
- The work completes in under ~5ms.
- The work makes no I/O outside Postgres.

Everything else is Tier 2. When in doubt, Tier 2.

## 5. The `events` table

Every event is persisted to a single append-only `events` table at publish time, inside the publisher's transaction. This is the canonical log.

```sql
CREATE TABLE events (
    id              UUID         PRIMARY KEY,
    type            TEXT         NOT NULL,
    tenant_id       UUID         NOT NULL,
    occurred_at     TIMESTAMPTZ  NOT NULL,
    actor_id        TEXT         NOT NULL,    -- UUID or 'system:...' sentinel
    subject_id      UUID         NOT NULL,
    correlation_id  UUID         NOT NULL,
    causation_id    UUID         NULL,
    payload         JSONB        NOT NULL,
    version         INTEGER      NOT NULL DEFAULT 1,
    published_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    delivered_to    JSONB        NOT NULL DEFAULT '{}'::jsonb
                                  -- { "fi.aggregator": "2026-06-19T10:11:12Z",
                                  --   "audit.writer":  "2026-06-19T10:11:12Z" }
);

CREATE INDEX idx_events_tenant_type_time
    ON events (tenant_id, type, occurred_at DESC);

CREATE INDEX idx_events_correlation
    ON events (correlation_id);

CREATE INDEX idx_events_subject
    ON events (tenant_id, subject_id, occurred_at);
```

Notes:

- **Append-only.** No `UPDATE` of `id`/`type`/`payload`. `delivered_to` is the **only** mutable column, written by subscribers (or by an ack worker) on successful delivery.
- **Persisted in the same transaction as the business write.** This guarantees: if the invoice was reconciled, the event exists; if the event exists, the invoice was reconciled. No outbox-vs-handler race.
- **No deletion.** Events are retained indefinitely in v1. A retention policy (archive to cold storage after N months) is a future ADR, not v1 work.
- **`delivered_to`** is a per-subscriber timestamp map. A subscriber that needs at-most-once semantics consults it before processing. Mostly it's a debugging aid: "did the FI aggregator receive event X?"

The `events` table is **not** the source of truth for entity state. The invoice row in `acc_invoices` is. The event table records what happened; the entity table records the current state. See §11.

## 6. Subscriber registration

Each module declares its subscriptions in `<module>/events.py`. Two registration styles are supported and equivalent:

### Decorator style

```python
# app/modules/founder_intelligence/events.py
from app.core.events import subscribe, Tier
from app.modules.accounts.events import InvoiceReconciled

@subscribe("acc.invoice.reconciled", tier=Tier.ASYNC)
def on_invoice_reconciled(event: InvoiceReconciled, db: Session) -> None:
    aggregator = FIAggregator(db)
    aggregator.bump_recon_success(
        tenant_id=event.tenant_id,
        amount=event.payload.amount,
        occurred_at=event.occurred_at,
    )
```

### Registry call (for dynamic subscriptions, e.g. webhooks per tenant)

```python
# app/core/integrations/webhook/registration.py
from app.core.events import bus, Tier

def register_tenant_webhook(tenant_id: UUID, event_type: str, target_url: str):
    bus.subscribe(
        event_type=event_type,
        tier=Tier.ASYNC,
        handler=lambda ev, db: WebhookConnector.deliver(target_url, ev),
        name=f"webhook:{tenant_id}:{event_type}:{target_url}",
        tenant_scope=tenant_id,
    )
```

### Wildcards

`subscribe("*")` is permitted **only** in `app/core/audit/subscriber.py` and `app/modules/founder_intelligence/subscribers.py`. Anywhere else, a wildcard subscription must be justified in a code review and is almost always wrong. Modules should subscribe to the specific event types they care about, by name.

### Handler contract

A handler is `Callable[[Event, Session], None]`:

- Receives a typed event subclass when the event type is declared in a `registry.py`; otherwise receives a base `Event`.
- Receives a `Session`. Tier 1 handlers get the publisher's session; Tier 2 handlers get a fresh session bound to a fresh transaction.
- Returns `None`. To trigger downstream effects, the handler publishes its own events (with `causation_id = event.id`). It does not call other modules' services directly except through documented service interfaces (per `02-modules.md`).
- Must be idempotent. See §7.

### Wiring at startup

`app/main.py`'s lifespan hook imports each module's `events` submodule, which executes the decorator registrations. There is no magic auto-discovery; the import list is explicit and reviewable:

```python
# app/main.py (lifespan)
from app.core.audit import subscriber as _audit_sub                  # noqa: F401
from app.core.workflows import runner as _workflow_runner            # noqa: F401
from app.modules.accounts import events as _acc_events               # noqa: F401
from app.modules.operations import events as _ops_events             # noqa: F401
from app.modules.inventory import events as _inv_events              # noqa: F401
from app.modules.customer_service import events as _cs_events        # noqa: F401
from app.modules.founder_intelligence import subscribers as _fi_subs # noqa: F401
```

## 7. Delivery guarantees

| Tier | Guarantee | Mechanism |
|---|---|---|
| Tier 1 (sync) | **Exactly once, in the publishing transaction.** | Handlers run in the same tx; either both commit or both roll back. |
| Tier 2 (async) | **At least once.** | RQ retries failed jobs; idempotency is the handler's responsibility. |

### Idempotency requirements

Every Tier 2 handler **must** be idempotent. There are no exceptions. Two acceptable strategies:

1. **Natural idempotency** — the handler's effect is the same regardless of how many times it runs. Setting a row's `state = 'reconciled'` is naturally idempotent.
2. **Idempotency key** — the handler records `(event.id, handler_name)` in a dedup table on success, and skips events already recorded.

```python
@subscribe("acc.invoice.reconciled", tier=Tier.ASYNC)
def on_invoice_reconciled(event, db):
    if already_processed(db, event.id, "fi.aggregator"):
        return
    bump_recon_success(db, event)
    mark_processed(db, event.id, "fi.aggregator")
```

The `delivered_to` JSONB column on `events` is **not** sufficient as an idempotency mechanism on its own, because a retry can re-deliver before `delivered_to` is updated. The handler's local dedup is authoritative.

### Failure handling

- **Tier 1 handler raises.** The publisher's transaction rolls back. The business event did not happen. The HTTP request returns 500. This is the desired behavior — if the audit log can't write, the action shouldn't succeed.
- **Tier 2 handler raises.** RQ retries with exponential backoff (3 attempts: 30s, 5m, 30m). After exhaustion the job lands in the RQ `failed` queue, **and** an `events_dlq` row is written:

  ```sql
  CREATE TABLE events_dlq (
      event_id        UUID         NOT NULL REFERENCES events(id),
      handler_name    TEXT         NOT NULL,
      failed_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
      attempt_count   INTEGER      NOT NULL,
      error           TEXT         NOT NULL,
      traceback       TEXT         NOT NULL,
      resolved_at     TIMESTAMPTZ  NULL,
      PRIMARY KEY (event_id, handler_name)
  );
  ```

  Operators can inspect, fix the root cause, and replay (§8) the affected events to that handler. A simple `/admin/events/dlq` view in the dashboard surfaces this.

- **Poison events.** An event that fails every subscriber every time is logged at ERROR with the full event, alerted on after the 3rd attempt across all handlers, and parked in the DLQ. We **do not** drop or "skip" poison events automatically. A human decides.

## 8. Replay

Replay is the ability to feed events from the `events` table back to a single subscriber (or all of them) as if they had just been published. We need it for three reasons:

1. **Adding a new aggregate.** When FI gets a new KPI ("returns_by_channel_30d"), we add the handler and replay the relevant event types from the last 30 days through it. The aggregate is built without touching transactional code.
2. **Recovering from a handler bug.** The notification handler had a bug for 2 hours; we fix it, then replay the missed events through it.
3. **Onboarding a new tenant's historical data.** Bulk-import old invoices as `acc.invoice.imported`-typed events, replay through FI to seed dashboards.

### CLI sketch

```bash
# Replay every acc.invoice.* event from the last 7 days through the FI aggregator,
# for tenant T, in dry-run mode (does not commit).
python -m app.core.events.replay \
    --tenant <tenant_uuid> \
    --type 'acc.invoice.*' \
    --since '7d' \
    --to-handler fi.aggregator \
    --dry-run

# Replay a single event through one handler (after fixing a bug).
python -m app.core.events.replay --event-id <event_uuid> --to-handler notifications.send

# Replay DLQ entries.
python -m app.core.events.replay --from-dlq --handler notifications.send
```

Replay reuses the normal subscriber wiring. It runs handlers in Tier 2 mode (RQ jobs) regardless of the original tier — replaying into a synchronous in-transaction handler doesn't make sense, because the original transaction is long gone.

Crucially, replay relies on **handler idempotency** (§7). A replay that re-fires an event a handler already processed must be a no-op.

## 9. Ordering

Nyx provides **per-subject ordering** and **no global ordering**.

- **Per-subject:** events with the same `subject_id` are processed by Tier 2 handlers in the order they were published (i.e., in `occurred_at` order, with `id` as tiebreaker since UUIDv7 is time-sortable).
- **Global:** no ordering guarantee across different `subject_id`s. Event A on invoice X and event B on invoice Y may be processed in any order.

Implementation: Tier 2 fanout uses one RQ queue per `(tenant_id, subject_id)` bucket, with a configurable bucket count. Events with the same subject hash to the same queue, where RQ workers process FIFO. Different subjects can be processed in parallel by different workers.

Why this trade-off:

- **Global ordering** in a distributed worker pool requires a single-threaded consumer per tenant, which kills throughput. We refuse to pay that price.
- **No ordering at all** breaks state machines: an `InvoiceReconciled` arriving before `InvoiceVerified` for the same invoice would make FI's per-invoice timeline incoherent.
- **Per-subject** is the sweet spot: it's enough to keep an entity's history consistent and admits horizontal parallelism across entities.

Tier 1 handlers run synchronously in the publisher's process, so per-subject ordering for Tier 1 is automatic (and de facto global per-request, since handlers are called in registration order).

## 10. Correlation & causation in practice

`correlation_id` is the *thread*; `causation_id` is each link in the *chain*. Together they let an operator trace one user action through every downstream effect.

### Rules

1. A **root event** (caused by direct user action — a button click, a WhatsApp `DONE`, a scheduled trigger firing) gets a fresh `correlation_id = uuid7()` and `causation_id = None`.
2. A **derived event** (emitted by a subscriber in response to another event) **inherits** the upstream event's `correlation_id` and sets `causation_id = upstream_event.id`.
3. **Workflow-engine-emitted events** propagate the correlation of the event that advanced the workflow.

### Worked example

A warehouse staffer replies `DONE` on WhatsApp for task #451 (a stock-transfer sub-task). The chain:

| # | Event | correlation_id | causation_id | actor | subject |
|---|---|---|---|---|---|
| 1 | `core.conversation.message_received` | C1 | `null` | user U | conv msg id |
| 2 | `core.task.completed` (task #451) | C1 | event 1's id | user U | task 451 |
| 3 | `workflow.step.completed` (stock_transfer step 3) | C1 | event 2's id | `system:workflow_runner` | wf_instance W |
| 4 | `inv.stock.adjusted` (warehouse A -10) | C1 | event 3's id | `system:workflow_runner` | sku S |
| 5 | `inv.transfer.completed` | C1 | event 3's id | `system:workflow_runner` | transfer T |
| 6 | `core.notification.sent` (ops head, in-app) | C1 | event 5's id | `system:notifications` | notif N |

Querying `events WHERE correlation_id = 'C1' ORDER BY occurred_at` returns the full timeline. A causal tree can be drawn by walking `causation_id` pointers — event 5 leads back to 3 leads back to 2 leads back to 1.

This is what makes incident investigation tractable. "Why did the ops head get pinged at 3am?" → query by notification id → fetch event 6 → walk back to the originating WhatsApp message → done. Without correlation/causation, this query is impossible without log-grepping across services.

### Propagation in code

The bus enforces propagation. A handler that publishes a new event without providing `correlation_id` and `causation_id` gets them auto-filled from the currently-processing event via a contextvar:

```python
# app/core/events/bus.py (sketch)
_current_event: ContextVar[Event | None] = ContextVar("_current_event", default=None)

def publish(event_kwargs: dict) -> Event:
    upstream = _current_event.get()
    if upstream is not None:
        event_kwargs.setdefault("correlation_id", upstream.correlation_id)
        event_kwargs.setdefault("causation_id", upstream.id)
    event = Event(**event_kwargs)
    _persist(event)
    _dispatch(event)
    return event
```

Root publishers (HTTP handlers, conversation runtime, scheduler) explicitly pass `correlation_id=uuid7(), causation_id=None`. Everyone else gets it for free.

## 11. Anti-goals

What the event bus is **not**:

- **Not Kafka.** Redis Streams or pub/sub is sufficient for our throughput (target: 100s of events/sec/tenant, not 100k). Kafka brings a ZooKeeper/KRaft footprint, partition planning, schema registry, and ops burden we will not pay for at our scale. We will revisit when we genuinely outgrow Redis, not before.
- **Not a separate event store.** Events live in the same Postgres as everything else. Same backup, same replica, same access control. The `events` table is just another table.
- **Not event sourcing.** Entity state lives in the entity's own table (`acc_invoices`, `ops_dispatches`). Events are an **additive log of things that happened**, not the source of truth for current state. We do not rebuild an invoice's state by folding its event stream. This is a deliberate, important choice: it keeps queries fast, schema readable, and onboarding to the codebase humane. Event-sourcing-as-primary-model is a 10x complexity multiplier we refuse.
- **Not globally ordered.** See §9. No partitioned linearizable log across the system.
- **Not a workflow engine.** Workflows consume events; they are not the bus itself. See `06-workflows.md` (forthcoming).
- **Not a message queue for arbitrary jobs.** RQ is. The event bus is for domain events with semantic meaning. "Run this OCR job" is an RQ job, not an event. "An invoice was uploaded" is an event (which may trigger an OCR job via a subscriber).
- **Not synchronous RPC.** A module that needs an answer *now* calls another module's service interface (per `02-modules.md`). The bus is for fire-and-forget facts, not request/response.

## 12. How a module emits an event

The publishing service does three things: mutates its own entity, builds the event, calls `bus.publish`. The bus handles persistence + dispatch.

```python
# app/modules/accounts/services.py

from app.core.events import bus
from app.modules.accounts.events import InvoiceReconciled, InvoiceReconciledPayload

class ReconService:
    def __init__(self, db: Session):
        self.db = db
        self.invoice_repo = InvoiceRepository(db)

    def reconcile(self, invoice_id: UUID, actor_id: UUID) -> None:
        invoice = self.invoice_repo.get(invoice_id)
        if invoice.state != "verified":
            raise ConflictError("Invoice not in verified state.")

        # 1. mutate state
        invoice.state = "reconciled"
        invoice.reconciled_at = utcnow()
        recon_record = self.invoice_repo.create_reconciliation_record(invoice)

        # 2. emit event (still inside the request's tx)
        bus.publish(
            InvoiceReconciled(
                id=uuid7(),
                tenant_id=invoice.tenant_id,
                occurred_at=utcnow(),
                actor_id=actor_id,
                subject_id=invoice.id,
                # correlation_id / causation_id auto-filled from context
                payload=InvoiceReconciledPayload(
                    invoice_id=invoice.id,
                    vendor_id=invoice.vendor_id,
                    amount=invoice.amount,
                    matched_po_id=invoice.matched_po_id,
                    reconciliation_record_id=recon_record.id,
                ),
            )
        )
        # Tier 1 handlers (audit, workflow runner) have now run.
        # Tier 2 fanout happens after the surrounding tx commits.
```

The service does not import FI, Operations, Notifications, or Audit. It does not know how many subscribers exist. It does not need to.

## 13. Failure modes & ops

### Redis is down

- Tier 1 still works (it's in-process, no Redis involvement). The publishing transaction commits. The `events` row is written.
- Tier 2 fanout fails. The bus catches the Redis connection error and writes the events to a local `events_pending_fanout` table (one row per `(event_id, handler_name)` pair to enqueue). A background reaper job retries fanout every 30s once Redis is back.
- The request **does not fail** if Redis is down. The user-visible action succeeded. Async effects are merely delayed.
- Alerts fire after `events_pending_fanout` depth exceeds a threshold (default 1000) or oldest pending exceeds 5 minutes.

### A subscriber is slow

- Slow Tier 2 handlers back up only their own RQ queue (and their per-subject sub-queue). Other handlers and other subjects are unaffected — that is the entire point of one-job-per-subscriber fanout.
- Worker pool is sized per queue, not per handler. A pathologically slow handler is given a dedicated queue + dedicated worker count via config.
- Monitoring: per-handler P95 processing time exported to logs/metrics. Sustained P95 > 5s for a handler that should be sub-second is alerted.
- A slow Tier 1 handler is a bug, not a runtime concern — it blocks user requests and gets caught in load tests / surfaced by request-latency monitoring.

### A poison event keeps failing

- After 3 retries with backoff, the event lands in `events_dlq` for that handler.
- Other handlers for the same event are unaffected — fanout already split them.
- An ERROR-level log is emitted with the full event + traceback. Sentry (or equivalent) catches it.
- Operator investigates via the DLQ admin view, fixes the underlying bug (the data, the handler, or both), then replays via the CLI (§8). At no point is the event silently discarded.

### The bus itself crashes mid-publish

- If the process dies after the entity write but before `bus.publish` writes the `events` row: the entity write is **also** rolled back, because both happen in the same transaction. No event, no entity change. Consistent.
- If the process dies after the tx commits but before Tier 2 fanout enqueues: the `events_pending_fanout` table will be empty (because we hadn't written it yet) and Tier 2 subscribers miss this event. We protect against this with a **transactional outbox pattern**: the `events_pending_fanout` rows are written inside the same tx as the `events` row, and the fanout worker drains the outbox into Redis post-commit. This is the only way to make async delivery as durable as the event itself.

### Database is down

- Everything fails closed. No events written. No entity changes. The system returns 503. This is the correct behavior; there is nothing intelligent to do with a missing database, and pretending otherwise creates split-brain bugs.

### Schema evolution

- Adding a new optional field to a payload: bump `version`. Subscribers ignore unknown fields by default.
- Removing or renaming a field: forbidden in-place. Introduce a new event type (`acc.invoice.reconciled_v2`-equivalent — but per §2 we encode version in the field, so actually `version=2` of the same name) and migrate subscribers one at a time. Old events stay on `version=1` forever.

---

This is the bus. Everything else in Nyx — workflows, audit, FI, notifications, multi-module choreography — is a consumer of this contract. If this layer is right, the rest of the platform composes. If this layer is wrong, no amount of clever module design rescues it.
