# NYX — System Architecture

**Status:** Living document · **Date:** 2026-07-08
**Audience:** Engineers building Nyx; reviewers evaluating it.
**Companions:** [`STATUS.md`](STATUS.md) (ground truth of the code) ·
[`docs/architecture/`](docs/architecture/) (detailed per-subsystem specs) ·
[`DOMAIN_MODEL.md`](DOMAIN_MODEL.md) · [`ARCHITECTURE_REVIEW.md`](ARCHITECTURE_REVIEW.md) ·
[`MVP.md`](MVP.md) · [`IMPLEMENTATION_PLAYBOOK.md`](IMPLEMENTATION_PLAYBOOK.md)

This document is the single top-level map of the Nyx architecture: what exists
today, what the target platform looks like, and the staged path between them.
Detailed specifications live in `docs/architecture/`; this document does not
repeat them — it unifies them, adds the platform-evolution layers (plugin
architecture, automation engine, scaling strategy), and marks every claim as
**[BUILT]** or **[TARGET]** so nobody mistakes design intent for shipped code.

---

## 1. What Nyx is

Nyx is a **modular internal business-operations platform for Indian SMEs
(20–500 employees)**, opinionated for D2C/eCommerce operations: Tally-friendly,
WhatsApp-native, event-driven. It is not a finance product; the Accounts
(invoice OCR + reconciliation) module is simply the first module built on the
platform. See [`docs/architecture/00-vision.md`](docs/architecture/00-vision.md)
for the full vision and the non-goals list.

**Current reality [BUILT]:** the Accounts module runs a complete connected
pipeline end to end — Upload → OCR → Extraction → workflow (verify gate →
approval gate) → Reconciliation → RECONCILED → Tally dry-run export — driven by
the workflow engine and event bus, with tenant isolation, RBAC, audit,
notifications, and 107 backend tests passing.

**Target [TARGET]:** the same platform primitives serving ten domains
(see `DOMAIN_MODEL.md`), with WhatsApp as a peer UI, a connector framework for
integrations, and declarative automation.

## 2. The three-layer shape

Every line of code lives in exactly one layer
(spec: [`01-platform-overview.md`](docs/architecture/01-platform-overview.md)):

```
INTERFACE LAYER      Web dashboard (Next.js) · WhatsApp runtime [TARGET] · Email inbound [TARGET]
        │
BUSINESS MODULES     Accounts [BUILT] · Inventory · Warehouse · Operations · CRM ·
                     Customer Service · Founder Intelligence            [TARGET]
        │
CORE LAYER           Identity/Auth · RBAC · Tenancy · Event Bus · Audit ·
                     Workflow Engine · Notifications                    [BUILT]
                     Tasks · Conversation Runtime · Integration Framework ·
                     Scheduler · Config Store                           [TARGET]
        │
INFRASTRUCTURE       SQLite + inline queue (dev, zero deps)  [BUILT]
                     Postgres + Redis + RQ (production)      [BUILT, config-switched]
```

Rules (non-negotiable, enforced by review today and `import-linter` next):

1. Modules emit events; they do not call each other's internals.
2. A module may call another module's *published service interface* only for
   synchronous query-style answers (e.g. `inventory.check_availability`).
3. Cross-module table reads are banned. No exceptions.
4. The core layer never imports from any module.

## 3. Module boundaries

The full domain map — all ten domains, their ownership, tables, events, and
explicit non-responsibilities — is specified in [`DOMAIN_MODEL.md`](DOMAIN_MODEL.md).
Summary of the boundary mechanics:

- **One folder per bounded context** under `app/modules/<name>/` with the
  standard layout (models, schemas, repositories, services, routes, workers,
  events, workflows). The module's `__init__.py` exports the only symbols other
  modules may use.
- **Table prefixes per module** (`acc_`, `inv_`, `whs_`, `ops_`, `crm_`, `cs_`,
  `fi_`); core tables are unprefixed. A table that resists prefixing is a table
  in the wrong place.
- **Dependency graph is a DAG.** Founder Intelligence subscribes to everything
  and nothing depends on it. Allowed synchronous calls are enumerated in
  `DOMAIN_MODEL.md` §12; everything else is events.
- **Current state [BUILT]:** only Accounts exists and it still lives in the
  layer-organized layout (`app/services/`, `app/models/`, …). The reorg into
  `app/modules/accounts/` is the first structural milestone
  (see `IMPLEMENTATION_PLAYBOOK.md`, Phase 2) and must land **before** a second
  module exists, while the boundary is still cheap to draw.

## 4. Event-driven architecture

Spec: [`05-event-bus.md`](docs/architecture/05-event-bus.md) ·
Decision: [ADR-0002](docs/architecture/adr/0002-in-process-event-bus.md),
[ADR-0010](docs/architecture/adr/0010-async-fanout-transactional-outbox.md)

Events are the connective tissue. Every state change publishes a
`module.entity.verb_past_tense` event, persisted to the durable `events` table
in the same transaction as the business write, then delivered to subscribers.

**Built today:**
- `EventBus` with subscribe/publish, durable `events` log, outbox semantics.
- Audit log is a `"*"` subscriber — one write, two views (event log + audit
  trail), no dual-write drift.
- Notification subscriber produces in-app notifications from domain events.
- Workflow engine consumes events as its trigger source.
- **All subscribers run synchronously in the publishing transaction** (TD-11).

**Target — two-tier delivery:**

| Tier | Guarantee | Runs | Who belongs here |
|---|---|---|---|
| 1 — sync, in-transaction | exactly-once with the business write | publisher's session, < ~5 ms, no I/O beyond Postgres | audit writer, workflow advancement |
| 2 — async, worker-fanned | at-least-once; handlers must be idempotent | one queue job per subscriber, own session | FI aggregates, notifications, webhooks, cross-module reactions |

The migration from "everything is Tier 1" to two tiers is the **single highest-
priority structural change** (TD-11): a slow or failing subscriber currently
taxes the producing request. Mechanism: rows written to an outbox table inside
the publishing transaction; a fanout worker drains the outbox into the queue
after commit (transactional outbox — no event can be lost between commit and
fanout). Failed deliveries retry with backoff, then land in a dead-letter table
with an operator replay path. Ordering guarantee is **per-subject** (events for
the same aggregate are processed in order), never global.

## 5. Workflow engine and its evolution

Spec: [`06-workflow-engine.md`](docs/architecture/06-workflow-engine.md) ·
Decision: [ADR-0003](docs/architecture/adr/0003-custom-workflow-engine.md),
[ADR-0013](docs/architecture/adr/0013-workflow-definitions-code-to-data.md)

The engine is custom, embedded, and deliberately small. It is already the
single execution path for post-extraction invoice work — it is **load-bearing
today**, not aspirational. Its evolution is staged; each stage is shippable and
none requires rewriting the previous one.

### Stage 0 — code-registered definitions [BUILT]

- Durable `workflow_instances`; a runner that advances steps; a **restricted
  condition evaluator** (AST allowlist — no calls, no imports, no dunders);
  an **action registry** as the only extensibility point.
- One definition (`invoice_post_extraction`) registered in Python:
  confidence gate → approval gate → reconcile. Gates park the instance
  (`needs_verification` / `pending_approval`); verify/approve endpoints resume
  the same instance. Retry/failure-recovery for failed instances exists.

### Stage 1 — definitions become data [TARGET, next]

- `workflow_definitions` table: YAML canonical text + parsed JSONB, versioned,
  immutable per version; running instances pin their version.
- Validation at save time: conditions parse, actions exist in the registry,
  params match the action's declared input schema.
- The Python-registered definition of Stage 0 becomes seed data.
- Admin edit → publish → retire flow via API (`PUT`-a-row, no redeploy) — the
  P4/P9 payoff ("workflows are first-class data; configuration over code").

### Stage 2 — waits, timers, and human-in-the-loop generalized [TARGET]

- `wait_for_event` / `wait_for_duration` step primitives with a
  `wait_descriptor`; wakeup driven by the event bus and the scheduler (no
  polling loop).
- The generic **Task** entity (`core/tasks/`) as the human-in-the-loop
  primitive; **approval chains are just workflows** with wait-for-task steps —
  there is no separate approval engine, ever.
- Per-action retry policies with transient/permanent error classes; exhausted
  retries park the instance and alert; parked instances resume only by human
  action.

### Stage 3 — full catalogue + testing harness [TARGET]

- Standard action catalogue (`core.tasks.create`, `core.notifications.send`,
  `core.events.publish`, `core.integrations.call`, …) plus module-registered
  actions.
- `WorkflowTestRunner` harness (in-memory bus, virtual clock, stubbed actions)
  so YAML definitions are unit-testable before publish.

**What the engine will never be** (anti-goals, held at every stage): no
Turing-complete DSL, no embedded scripting beyond restricted conditions, no
LLM-decided branching, no automatic saga/compensation semantics, no visual
drag-drop editor (a read-only visualizer is welcome).

## 6. Plugin architecture

Decision: [ADR-0012](docs/architecture/adr/0012-internal-plugin-architecture.md)

Nyx explicitly does **not** have a third-party plugin marketplace (a vision
non-goal: no signed-binary loading, no plugin store). "Plugin architecture"
in Nyx means something more valuable at this scale: **every extension point in
the platform is a registry with a uniform contract**, so first-party code
extends the platform without modifying it.

| Extension point | Registry | Contract | Who registers |
|---|---|---|---|
| Business module | router + module `__init__.py` | standard folder layout; events declared in `events.py` | one folder under `app/modules/` |
| Workflow action | action registry [BUILT] | name, handler, input/output JSON Schema, idempotency flag, retry policy | core + each module |
| Event subscriber | event bus subscribe [BUILT] | `Callable[[Event, Session], None]`, idempotent if Tier 2 | core + each module |
| Integration connector | connector registry [TARGET] | `Connector` ABC (push/pull/receive), `auth_test` mandatory | `app/core/integrations/<name>/` |
| Alert definition | `fi_alert_definitions` rows [TARGET] | condition DSL + severity + cooldown | seeded + tenant-edited |
| Notification channel | channel selector [TARGET] | `send(rendered_message) -> result` | `core/notifications/channels/` |
| Conversation intent | intent registry [TARGET] | pattern list per `expects` shape | core (curated, small) |

The test of the plugin architecture is the **module recipe**: adding a new
module must require creating one folder and one router-registration line —
nothing else. If a module addition ever needs surgery elsewhere, the platform
layer has failed and gets fixed before features continue.

Third parties who want to extend Nyx get two supported surfaces, both already
in the integration design: **generic inbound webhooks** (HMAC-verified, mapped
to declared event types) and **generic outbound webhooks** (subscribe a URL to
event types). External systems react to Nyx and feed Nyx without loading code
into the process.

## 7. Automation engine

The "automation engine" is not a new subsystem — it is the composition of four
platform pieces, and naming the composition prevents anyone from building a
fifth thing that duplicates them:

```
  triggers                 decisions              effects
  ────────                 ─────────              ───────
  domain events   ──►  workflow definitions  ──►  registered actions
  schedules (cron)      (conditions, gates,       (tasks, notifications,
  manual API calls       waits, versioned)         events, connector calls)
  WhatsApp intents                                       │
                                                         ▼
                                              alerts (fi_alert_definitions)
                                              notifications (per-user prefs)
```

- **Triggers:** the four workflow trigger kinds — event, schedule, manual,
  WhatsApp intent. The scheduler [TARGET] emits synthetic `core.schedule.tick`
  events so time-based automation reuses the same engine path as everything
  else; there is no separate cron subsystem.
- **Decisions:** workflow conditions (restricted expressions) + trigger
  filters + alert condition DSL. All declarative, all validated at save time,
  all tenant-editable [TARGET].
- **Effects:** only registered actions. Adding an effect type is a code change
  (deliberate friction); *using* effects is configuration.
- **Determinism rule (P6):** automation never branches on LLM output. LLMs
  classify fuzzy free-text input into fixed taxonomies *before* the automation
  layer sees a deterministic verb; below-confidence goes to human triage.

Today [BUILT]: event-triggered workflow + event-driven notifications cover the
Accounts pipeline. The scheduler, alert definitions, and tenant-editable
definitions arrive with Stages 1–2 of the engine evolution (§5).

## 8. Integration architecture

Spec: [`08-integrations.md`](docs/architecture/08-integrations.md)

All external I/O goes through one framework: a `Connector` ABC in three kinds
(**push** — Tally, WhatsApp send, webhook out; **pull** — Shopify/Amazon/
Flipkart orders, Sheets; **receive** — WhatsApp webhook, Shopify webhook,
webhook in), a registry resolving `(tenant_id, connector_id, instance_name)`,
per-tenant config in `integration_configs`, and secrets envelope-encrypted in
`integration_credentials` (never in env vars, never in logs).

Operational disciplines the framework enforces uniformly:
- **No external I/O on the request path.** Pushes run in workers; the only
  synchronous external call is `auth_test` with a 3-second timeout.
- **Failure isolation:** circuit breakers on push, per-instance worker jobs on
  pull, buffer-then-ack on receive (external systems never see our 5xx).
- **Observability:** every call recorded to `integration_call_log`; a health
  rollup feeds the Settings → Integrations page.
- **Idempotency:** stable `_idem` keys; "already exists" responses treated as
  success.

**Current state [BUILT]:** Tally XML generation exists as a service
(`tally_export_service`, dry-run only — the pure `build_tally_xml` property is
already honored). The connector framework itself is not yet built; the Tally
service migrates into it as the first connector, dry-run mode intact, and the
real push lands behind the existing dry-run.

## 9. Data architecture

Spec: [`04-database.md`](docs/architecture/04-database.md) ·
Decisions: [ADR-0005](docs/architecture/adr/0005-single-postgres-no-cqrs.md),
[ADR-0008](docs/architecture/adr/0008-tenant-id-everywhere.md)

- **One relational database.** SQLite by default in dev (zero external
  services — a deliberate feature), Postgres in production, portable
  migrations (enum ADDs are Postgres-only no-ops on SQLite). [BUILT]
- **Tenant-aware everywhere:** `tenant_id` on every business table; reads,
  writes, and audit uniformly tenant-scoped at the repository layer;
  cross-tenant access is 404, proven by tests. [BUILT]
- **Events are a log, not the source of truth.** Entity tables are
  authoritative; no event sourcing as primary store.
- **FI reads only from its own materialized aggregates** — CQRS's shape
  without its plumbing. [TARGET]
- **JSONB policy:** payloads, config, forensic context — yes; anything
  filtered, sorted, joined, or FK'd — a real column. **Money is
  `NUMERIC(14,2)`, never float.**
- **Migrations:** linear Alembic chain, hand-written, reversible;
  add-nullable → backfill → set-NOT-NULL for new required columns. The actual
  chain (`0001`–`0007` as in the repo) is canonical; the illustrative
  numbering in older docs is superseded.

## 10. Security architecture

Full review and findings: [`SECURITY_REVIEW.md`](SECURITY_REVIEW.md).
Anchors: application-layer RBAC with auditable `Decision`s
([ADR-0004](docs/architecture/adr/0004-app-layer-rbac-no-rls.md)); one
authorization path for web, WhatsApp, and workers; restricted expression
evaluation in workflows (no eval of arbitrary code); phone-claim + OTP before
any WhatsApp principal is trusted; envelope-encrypted per-tenant credentials;
append-only audit and event logs.

## 11. Observability

Full spec: [`OBSERVABILITY.md`](OBSERVABILITY.md). Anchors: structured logging
with correlation IDs propagated through events (`correlation_id` /
`causation_id`), workflow instances and step runs as first-class inspectable
records, DLQ depth and outbox lag as the two golden async metrics,
`integration_call_log` for connector health, and the engine SLOs from
`06-workflow-engine.md` Appendix C.

## 12. Scaling strategy

Nyx scales in **deliberate, boring steps**, each triggered by a measured
constraint — never speculatively. The steps are ordered; skipping ahead is a
review-blocking error.

| Step | Trigger | Change | What does *not* change |
|---|---|---|---|
| 0. Dev default [BUILT] | — | SQLite + inline queue, single process | — |
| 1. Production baseline [BUILT, config] | any real deployment | Postgres + Redis + RQ workers | code; the queue abstraction already switches on config |
| 2. Async fan-out (TD-11) | first slow subscriber | Tier 2 delivery via outbox + workers | publisher API; `bus.publish()` is unchanged |
| 3. Worker pool sizing | queue latency SLO missed | more RQ workers, per-queue sizing; slow handlers get dedicated queues | app process |
| 4. Read replica | FI/dashboard reads compete with writes | Postgres read replica for aggregate/dashboard reads | schema; FI already reads only aggregates |
| 5. Multi-process app + HA | single app node saturates | N uvicorn processes behind a load balancer; definition-cache invalidation via Redis pub/sub | modules; the bus fanout is already Redis-backed by step 2 |
| 6. Event/audit retention | events table > ~100 GB or query latency degrades | BRIN indexes, then archive-to-cold-storage job (the only writer of DELETE on those tables) | append-only semantics |
| 7. Tenant sharding | one tenant outgrows one Postgres | decide shape then (tenant-id sharding vs table); schema already partitions naturally by `tenant_id` | not before real data forces it |

Explicitly rejected at every step (each has an ADR): microservices, Kafka,
separate read database, event sourcing as primary store, Kubernetes,
multi-region. The migration paths exist in the ADRs; the costs are not paid
until a constraint is real.

**Capacity honesty:** the target workload is 100s of events/sec/tenant at the
extreme, more typically 10s of business events per minute. Every choice above
is sized for that reality — being right-sized *is* the architecture.

## 13. Known gaps between this document and the code

Kept in one place so the document cannot quietly lie
(cross-checked with `STATUS.md` §4–5):

1. **Sync-only event delivery** (TD-11) — Tier 2 does not exist yet; highest
   structural priority.
2. **Accounts not yet in `app/modules/`** — reorg must precede module #2.
3. **Workflow definitions are code, not data** — Stage 1 of §5 pending.
4. **No task system, conversation runtime, scheduler, config store, or
   connector framework yet** — all [TARGET].
5. **RBAC is static** (role→permission mapping in code, three seed roles);
   DB-backed roles/scopes are [TARGET].
6. **Auth hardening missing** (TD-8): no email verification, password reset,
   or token revocation — blocks any real multi-user deployment.
7. **Tenant schema is ready; onboarding/provisioning flow is not**
   (ADR-0008's deliberate deferral).
8. **Frontend** shows illustrative KPI fallbacks when the API is empty
   (TD-2b) and has no tests.

Every gap above appears with an owner-shaped plan in
[`IMPLEMENTATION_PLAYBOOK.md`](IMPLEMENTATION_PLAYBOOK.md) and as issues in
[`GITHUB_ISSUES.md`](GITHUB_ISSUES.md).
