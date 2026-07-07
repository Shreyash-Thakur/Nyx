# NYX — Observability

**Date:** 2026-07-08 · **Scope:** how Nyx is observed — logging, metrics,
traces, health, alerting — for the shipped system and the target platform.
**Stance:** same philosophy as the rest of the architecture — boring,
DB-backed, right-sized. Nyx's observability leans on a property most systems
don't have: **the durable event log, workflow instances, and audit trail are
already an observability system** for business behavior. This document adds
the operational layer around them and refuses a metrics-vendor buildout the
deployment size doesn't justify.

## 1. What exists today [BUILT]

- **Structured logging** via structlog (`app/core/logging.py`): JSON-shaped
  events (`workflow_failed`, `event_handler_failed`, request logs from
  middleware) with key-value context.
- **`/health`** — DB reachability + queue-backend awareness (inline mode is
  healthy without Redis; explicit redis mode reports degraded when Redis is
  down — fixed in `32ee782`).
- **Business-state introspection:** `events` table (durable log),
  `workflow_instances` (status, current_step, error, context), `audit_logs`,
  `processing_jobs` (OCR pipeline), notifications — all queryable, all
  tenant-scoped, all surfaced partially in the dashboard (activity feed,
  queue counts).
- **Tests as observability:** the e2e pipeline test walks the entire flow and
  asserts the side-effect trail (events, audit, dashboard counts) — drift in
  the observable surface fails CI.

## 2. The three pillars, right-sized

### 2.1 Logging [BUILT → harden]

Rules (mostly held today; make them explicit):

1. **JSON in production, pretty in dev.** One event per line; no multi-line
   stack traces outside the `traceback` field.
2. **Every log line carries:** `request_id`, `tenant_id`, `actor` (user id or
   `system:*` sentinel), and — once ADR-0010 lands — `correlation_id`.
   Middleware binds these into structlog contextvars once; nobody passes them
   manually.
3. **Never logged:** credentials, tokens, message bodies, uploaded file
   contents, full event payloads at INFO (payloads at DEBUG only).
4. **Log levels mean things:** ERROR = a human should look (alertable);
   WARNING = degraded but self-healing (retries, circuit-open); INFO = state
   transitions; DEBUG = payloads and internals.
5. Workers log with the same shape as requests — `job_id` replaces
   `request_id`, correlation propagates through the job payload.

### 2.2 Correlation and tracing [TARGET — with ADR-0010]

Nyx does **not** adopt OpenTelemetry/distributed tracing yet (one process,
one DB — a trace would have two spans). The equivalent power comes from the
event schema: `correlation_id` (one thread per root cause) + `causation_id`
(parent event) on every event row, propagated automatically via contextvar in
`bus.publish()` and through queue job payloads.

- The **trace query** is SQL:
  `SELECT * FROM events WHERE correlation_id = :c ORDER BY created_at` —
  the full story of one user action across modules, workflows, and workers.
- HTTP `request_id` is the correlation root for API-initiated actions; the
  webhook message id for WhatsApp-initiated ones; the schedule tick id for
  timed ones.
- Adopt OTel only at scaling step 5+ (multi-process) if log-correlation
  proves insufficient — record that as a future decision, not a default.

### 2.3 Metrics [TARGET — staged]

**Stage A (now → first production deploy): DB-backed metrics, no new infra.**
The numbers that matter are already rows; expose them on one internal
endpoint `GET /api/v1/ops/metrics` (admin-gated) and render them on an ops
panel:

| Metric | Source | Why it's golden |
|---|---|---|
| outbox lag (oldest undelivered, depth) | outbox table (ADR-0010) | the async health signal |
| DLQ depth by handler | dead-letter rows | subscriber failures |
| workflow instances by status; parked/failed count; age of oldest non-terminal | `workflow_instances` | the pipeline's pulse |
| verify-queue rate (needs_verification / uploaded, daily) | invoice statuses | OCR honesty metric (review A7) |
| approval latency (pending_approval age p50/p95) | invoice + instance timestamps | founder-visible SLA |
| queue depth / job failures | RQ / inline queue introspection | worker health |
| integration call success rate + p95 latency per connector | `integration_call_log` (08 §12) | connector health page feeds from this |
| auth failures, rate-limit hits | limiter + auth logs | probe detection |

**Stage B (scaling step 3+, real worker fleet): Prometheus.**
`prometheus-fastapi-instrumentator` for RED metrics (rate, errors, duration),
`rq-exporter` for queues, `postgres_exporter`. Grafana with four dashboards:
API, workers/outbox, workflows, integrations. Not before a real fleet exists.

**SLOs (adopted from `06-workflow-engine.md` Appendix C, plus platform):**

| SLO | Target |
|---|---|
| API p95 (non-upload) | < 300 ms |
| event publish → first workflow step | p95 < 200 ms |
| wait-event arrival → instance wake | p95 < 500 ms (Stage 2 engine) |
| outbox commit → Tier-2 handler start | p95 < 5 s |
| parked instance → alert | < 60 s |
| WhatsApp inbound → outbound ack | p95 < 3 s (when built) |

## 3. Health and readiness [BUILT → extend]

- `/health` (liveness): process up, DB reachable — stays cheap and
  dependency-honest (inline queue ≠ degraded).
- `/health/ready` [TARGET]: DB + queue backend + **outbox drain moving**
  (oldest undelivered < threshold) + scheduler heartbeat fresh. Readiness is
  what a load balancer or deploy gate consults; it must include the async
  path, or deploys look green while events pile up.
- Connector health is *not* in readiness (a tenant's Tally being off must
  never fail our deploy); it lives on the integrations health page from
  `integration_health` rollups.

## 4. Alerting [TARGET — with the pieces they watch]

Alert channel: in-app notifications to admin role now; email later. FI alert
definitions (`fi_alert_definitions`) handle *business* alerts; this section is
*operational* alerts, config-defined, evaluated by a scheduler job over the
Stage-A metrics:

| Alert | Condition (default) | Severity |
|---|---|---|
| outbox stalled | oldest undelivered > 5 min or depth > 1000 | page-worthy |
| DLQ growth | any new DLQ row | high |
| workflow parked/failed | any instance parks; failed count > 0 for 10 min | high |
| scheduler silent | no heartbeat > 2× tick interval | high |
| verify-queue spike | daily rate > 2× 7-day avg | medium |
| integration failing | consecutive failures > threshold (per 08 §13, auto-disables pull) | medium |
| auth anomalies | webhook signature failures > N/min; lockout spike | medium |

Rules: every alert has a cooldown (alert fatigue is the failure mode — same
stance as FI); every alert names the *query to run next* in its body; a
silent pager is only trustworthy because the readiness endpoint and CI e2e
walk exist.

## 5. Runbook seeds (the queries that answer incidents)

- **"Why didn't invoice X reconcile?"** — instance + step trail:
  `SELECT * FROM workflow_instances WHERE context->>'invoice_id' = :id;`
  then its status/error/current_step; audit rows for the aggregate.
- **"What did user U do yesterday?"** —
  `SELECT * FROM audit_logs WHERE actor_id=:u AND created_at::date=:d ORDER BY created_at;`
- **"Why did the founder get pinged?"** — notification → `source_event_id` →
  correlation walk (post ADR-0010).
- **"Is async healthy?"** — outbox depth + oldest, DLQ count, RQ queue sizes.
- **"Did the deploy break the pipeline?"** — run the e2e test against
  staging; it *is* the synthetic monitor. [TARGET: run it on a schedule
  against a canary tenant in production — cheapest synthetic possible.]

## 6. Non-goals

No APM vendor (Datadog/New Relic) at this scale · no OpenTelemetry until
multi-process reality · no log aggregation cluster (journald/file + `jq` until
a second host exists; then Loki, not Elastic) · no custom metrics DSL — FI
owns business KPIs, this page owns ops, neither grows a query language ·
no dashboards nobody looks at: every panel must answer a runbook question
above, or it doesn't ship.

## 7. Build order

1. **With ADR-0010:** correlation/causation columns + contextvar binding;
   outbox/DLQ metrics; `/health/ready`. (The observability of the async tier
   ships *with* the async tier, not after it.)
2. **With the reorg milestone:** log-field standardization (`tenant_id`,
   `actor`, `request_id` everywhere), ops metrics endpoint Stage A.
3. **With each integration:** `integration_call_log` + health rollup (framework-enforced).
4. **With the conversation runtime:** inbound/outbound message metrics,
   signature-failure alerting.
5. **Prometheus/Grafana:** at scaling step 3, not before.
