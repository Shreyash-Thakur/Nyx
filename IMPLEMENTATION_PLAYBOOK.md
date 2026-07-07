# NYX — Implementation Playbook

**Date:** 2026-07-08 · **Baseline:** `STATUS.md` (Accounts pipeline complete,
107 tests). This is the execution plan for [`MVP.md`](MVP.md): exact order,
dependencies, what can run in parallel, milestones, and Definitions of Done.
Issues for every work item: [`GITHUB_ISSUES.md`](GITHUB_ISSUES.md).

**Planning unit:** the **phase** (a coherent, demoable increment), not the
calendar week — the original 8-week calendar (`11-roadmap.md`) is superseded
(review finding A4). Phases are strictly ordered unless marked parallel.

**Standing rules (apply to every phase):**

- Nothing merges red; the e2e pipeline test is the canary and runs on every PR.
- Every schema change: hand-written linear Alembic migration with a real
  `downgrade()`; add-nullable → backfill → NOT-NULL for required columns.
- Every new event handler declares its tier; Tier 2 handlers prove
  idempotency in a test.
- Every phase updates `STATUS.md` and any doc it invalidates **in the same
  PR** (a doc that lies is worse than no doc).
- Commit in logical batches; one concern per PR; pure-move commits separated
  from logic changes.

---

## Dependency spine (why this order and no other)

```
P1 outbox/Tier-2 ──► everything async later (FI, notifications at scale, webhooks)
P1 auth hardening ──► any real deployment
P2 reorg + RBAC signature + tenancy hook ──► any second module (cheaper before than after)
P3 engine Stage 1 (definitions-as-data) ──► editable automation; Stage 2 waits
P4 tasks + engine Stage 2 (waits/timers/scheduler) ──► approval chains, SLA timers, WhatsApp prompts
P4 conversation runtime ──► any WhatsApp-driven module flow
P5 inventory+warehouse ──► operations dispatch (reservations), FI stock KPIs
P6 FI v0 ──► founder demo beat 4
P7 connector framework (built in P3 for Tally-decision, generalized here) ──► Shopify/Gmail
```

The two **hard gates**: nothing user-facing multi-user before P1;
no module #2 before P2. Everything else tolerates reordering under pressure.

---

## Phase 1 — Platform correctness (V1 · the "no asterisks" phase)

**Goal:** the async tier exists, audit is atomic, and auth survives contact
with real users. Closes: TD-11, TD-8, SEC-1..4, review P0-1/P1-1/P2-1.

Order within phase:

1. **ADR-0010 outbox** — `event_outbox` table + fanout worker (RQ / inline);
   Tier 1/Tier 2 handler contract (Tier 1 re-raises → rollback; audit = Tier 1,
   notifications = Tier 2); retry w/ backoff; DLQ rows + replay CLI;
   **per-subject blocking** on failure (review P1-1 semantics);
   correlation/causation columns + contextvar propagation (P2-1).
2. **Observability for what #1 built** — outbox/DLQ metrics, `/health/ready`,
   parked/failed workflow alert (OBSERVABILITY.md §7.1).
3. **Auth hardening** — refresh rotation + jti denylist, revoke on password
   change/deactivation, email verification, password reset, production
   secret guardrails.
4. **Small fixes batch** — dedup race partial-unique index (SEC-4), TD-5
   single unit-of-work upload, TD-10 requirements hygiene + `pip-audit`,
   security headers/CORS pass (SEC-5).
5. **Postgres CI job** — migration round-trip (`upgrade head` → `downgrade
   base` → `upgrade head`) + test suite on Postgres. **Must exist before
   Phase 2's rename migration.**

**Parallel track (frontend, independent):** TD-2b real empty-states; verify +
approval queue screens polished; frontend ADR (state/data-fetch/token
storage — review P2-3, SEC-5).

**DoD:** killing the worker mid-fanout loses zero events (test);
a failing audit handler rolls back the business write (test); a revoked
refresh token is dead (test); e2e green on SQLite *and* Postgres in CI;
`STATUS.md` regenerated.

## Phase 2 — The boundary milestone (V1 · reorg before module #2)

**Goal:** code lives where the architecture says; the boundary is enforced by
CI; authorization signature is future-proof. Closes: ADR-0009, review
P1-3/A6, SEC-12.

1. Pure-move PRs: `app/modules/accounts/` + `app/core/{identity,audit,
   events,workflow,rbac,tenancy}/` per the 03 move-map (no logic changes).
2. Rename migration: `acc_` prefixes (+ `audit_logs` stays core, unprefixed);
   route aliases keep old API paths working.
3. `import-linter` contracts in CI (modules↛modules, core↛modules,
   router-only imports) + prefix-ownership test (review P2-4a).
4. RBAC signature upgrade: `can(user, action, resource, *, tenant_id) →
   Decision` (static role backing unchanged); routes migrate to the new
   `require()`; Decision reason lands in audit rows.
5. Tenancy safety hook: SQLAlchemy event listener failing unscoped queries on
   tenant tables outside production.

**DoD:** grep `from app.modules.accounts` outside the module → router line
only; lint contracts red on a deliberate violation (test-of-the-test); all
107+ tests green post-move; old API paths still serve.

## Phase 3 — Workflows become data + the Tally decision (V1 completes)

**Goal:** the P4/P9 promise is real; Tally has an honest ship path.
Closes: ADR-0013 Stage 1, review P1-4/P1-5 (evaluator guards), P0-2 decision.

1. `workflow_definitions` table (YAML + parsed JSONB, versioned, immutable);
   save-time validation (conditions, action existence, param schemas);
   **registry requires `idempotent` declaration; retry refuses non-idempotent
   replays**.
2. Restricted AST evaluator replacing dict conditions, shipped with SEC-9
   guards (node/length caps, operand type checks, timeout, JSON-only
   context) + fuzz tests.
3. Seed the Accounts pipeline as data; delete the Python registration in the
   same PR. Publish/retire API endpoints (admin-gated).
4. **Tally bridge ADR (0014)** — decide agent-vs-tunnel-vs-export (review
   P0-2); ship the export runbook (download XML + import steps) as V1's
   honest path; connector framework skeleton (`Connector` ABC + registry +
   `integration_configs`/`integration_credentials` with envelope encryption
   per SEC-10) with Tally-dry-run as the first connector.
5. **⇒ Tag V1.** Run the recruiter demo script end-to-end as the release test.

**DoD:** threshold change = a definition edit via API, no deploy, next
instance uses it, running instances don't (version-pinning test); evaluator
fuzz suite green; V1 exit test from `MVP.md` passes.

## Phase 4 — Humans in the loop: tasks + WhatsApp (V1.5 begins)

**Goal:** the generic task primitive and the conversational layer.
Closes: engine Stage 2, review P0-3, SEC-8.

1. `core/tasks/` (tasks, assignments) + engine Stage 2: `wait_for_event` /
   `wait_for_duration`, wait descriptors, scheduler (rq-scheduler singleton
   w/ Redis lock — review P2-2); approval gate re-expressed as
   create-task + wait-for-completion (approval chains = workflows, no
   separate engine).
2. WhatsApp connector (Cloud API client, token mgmt, rate limiting, template
   registry) — connector-framework citizen from day one.
3. Conversation runtime: webhook (verify → dedup → enqueue → 200), phone
   claims + OTP (lockout, revocation), pending prompts, rule intents
   (`DONE/ISSUE/APPROVE/REJECT/HELP/STATUS/CANCEL`), outbound templating.
   **Approval prompts carry explicit references / interactive buttons; bare
   `APPROVE` with >1 open approval prompt asks (P0-3).**
4. Wire the founder approval to WhatsApp end-to-end.

**Parallel track:** frontend approval inbox + task list; conversation debug
view (admin).

**DoD:** the §9.3 founder-approval trace passes as an integration test
(signature-verified webhook → intent → RBAC → workflow advance → audit with
channel metadata); unknown sender mutates nothing (test); two concurrent
approval prompts cannot cross (test).

## Phase 5 — Inventory + Warehouse (V1.5 core)

**Goal:** modules #2 and #3 on the platform, proving the recipe.
Closes: ADR-0011 build-out.

1. Inventory: SKUs, warehouses ref data, stock levels + append-only
   movements, reservations, thresholds; `check_availability` published
   interface.
2. Warehouse: transfers + items, pick tasks (via core Tasks), floor-issue
   capture; the transfer workflow definition (request → approve → tasks both
   ends → complete) with WhatsApp prompts.
3. Events wiring per `DOMAIN_MODEL.md` §3–4; movement events are the only
   Inventory↔Warehouse contract.

**DoD:** the platform-overview lifecycle trace (WhatsApp `DONE` → task →
workflow → stock moved → audit → notification) is an integration test; both
modules pass the recipe test (no edits outside their folders + router lines);
reservation prevents oversell under a concurrency test.

## Phase 6 — Founder Intelligence v0 (V1.5 completes)

1. FI subscriber set (Tier 2, idempotent, replay-safe) for existing events →
   `fi_kpi_*` + daily snapshot job; snapshot page reads aggregates only.
2. Alerts: parked-workflow, low-stock (definitions seeded, cooldowns).
3. Verify-queue rate KPI (the OCR honesty metric, review A7).
4. **⇒ Tag V1.5.** Founder demo script is the release test.

**DoD:** replay of N days of events reproduces the stored snapshot
byte-for-byte (determinism test); snapshot page < 500 ms with seeded data;
zero module-table reads from FI (lint/grep test).

## Phase 7+ — V2 sequence (ordering fixed, scope per MVP.md)

1. Operations + Shopify pull connector (cursor store, per-instance isolation)
   → dispatch → pick-task handoff to Warehouse.
2. CRM registry (identity, links, merge) → CS tickets + SLA workflows +
   Gmail send.
3. FI full (cross-module KPIs, tenant-editable alerts, 9 a.m. digest).
4. LLM classifier fallback (ADR-0007 shape; confidence → triage).
5. Tally on-prem agent (per ADR-0014).
6. Tenant onboarding/provisioning + per-tenant DEKs.

Each of these gets its own phase-DoD when scheduled; they are deliberately
not detailed further here — plans decay, and Phase 4–6 learnings will reshape
them.

---

## Milestones

| Milestone | Phase | Proof |
|---|---|---|
| **M1 — Async & atomic** | P1 | kill-the-worker test; audit rollback test; Postgres CI green |
| **M2 — Boundaries enforced** | P2 | import-linter red-test; Decision in audit rows |
| **M3 — V1 tagged** | P3 | MVP V1 exit test + recruiter demo run |
| **M4 — WhatsApp approval live** | P4 | §9.3 trace as integration test |
| **M5 — Module recipe proven** | P5 | Warehouse added with zero outside edits |
| **M6 — V1.5 tagged** | P6 | founder demo run + snapshot determinism test |

## Parallelization map

Safe to run concurrently at any point: **frontend track** (own milestones,
consumes stable APIs) · **docs/STATUS updates** · **observability Stage A**
(after P1.1) · **connector framework skeleton** (P3.4) can start during P2
(different files than the reorg). Never parallelize: the reorg (P2.1–2) with
anything touching backend code — it is a merge-conflict machine; freeze other
backend PRs for its window.

## Global Definition of Done (every phase, every PR)

1. Tests: new behavior covered; e2e canary green; SQLite + Postgres CI green.
2. Migrations: linear, reversible, tested round-trip.
3. Security: new surface reviewed against `SECURITY_REVIEW.md` conditions
   (SEC-8/9/10/11 are acceptance criteria on their issues).
4. Observability: new async paths emit the §2 log fields; new failure modes
   have an alert or an explicit "no alert because" note.
5. Docs: `STATUS.md` and affected architecture docs updated in-PR; new
   cross-cutting decision ⇒ new ADR.
6. Boundaries: import-linter green (post-M2); events versioned payloads
   (post-P3); no module reads another's tables — ever.
