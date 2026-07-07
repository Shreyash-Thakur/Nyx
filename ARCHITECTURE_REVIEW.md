# NYX — Architecture Review

**Reviewer stance:** Principal Engineer, enterprise ERP platform background
(Dynamics/SAP/Oracle-class systems), reviewing as if this platform will carry a
customer's books.
**Date:** 2026-07-08
**Inputs:** `ARCHITECTURE.md`, `DOMAIN_MODEL.md`, `docs/architecture/00–12`,
ADRs 0001–0013, `STATUS.md`, and the actual code
(`backend/app/core/events/bus.py`, `backend/app/core/workflow/engine.py`,
`backend/app/core/rbac.py`, migrations 0001–0007).

**Verdict:** The architecture is unusually honest and unusually coherent for
its stage — the BUILT/TARGET discipline, the ADR trail, and the boring-tech
posture are exactly right. The fundamental bets (modular monolith, events as
connective tissue, workflows as data, one authorization path) are sound and
correctly sequenced. But the design documents are ahead of the code in ways
that hide **three correctness risks** (audit atomicity, ordering-vs-retry,
approval prompt ambiguity), one **deployment-reality gap** (Tally reachability)
that will surface with the first real tenant, and several internal
contradictions that must be resolved before more code hardens around them.

---

## 1. What is genuinely good (kept short, but earned)

1. **The event log as a durable outbox in the publisher's transaction** —
   already in the code, not just the docs. This is the single hardest thing to
   retrofit, and it exists.
2. **Restricted conditions over embedded scripting.** The shipped dict-based
   condition (`equals`/`not_equals`/`in`) is even *more* conservative than the
   documented AST evaluator. Right instinct.
3. **The self-declared gap list** (`ARCHITECTURE.md` §13) matches STATUS and
   the code. Most teams' architecture docs lie; these mostly don't.
4. **The refusal list** (no Kafka, no microservices, no event sourcing, no
   plugin marketplace) with written trade-offs. This is what right-sized looks
   like.
5. **Idempotent, replay-safe reconciliation** proven by tests, and adversarial
   e2e cases (cross-tenant 404s, duplicate upload) at the HTTP level.

---

## 2. Findings

Severity scale: **P0** = will corrupt data, mislead an auditor, or block the
first real deployment · **P1** = will cause an incident under realistic load
or growth · **P2** = will slow the team or bite later.

### P0-1 · Audit is documented as atomic but implemented as best-effort

`05-event-bus.md` §7: *"if the audit log can't write, the action shouldn't
succeed"* — Tier 1 failures must roll back the publisher. The shipped bus does
the opposite: `EventBus.publish()` wraps every handler in `try/except` and
**swallows the exception with a log line** (`bus.py:72–82`). A failing audit
subscriber therefore lets the business write commit *without* its audit row —
on a platform whose principle P8 is "auditability is non-negotiable" and whose
pitch is "system of record."

The `events` row itself is transactional (good — the log is still complete),
but `audit_logs` can silently diverge, which re-creates the dual-write drift
that TD-6 was supposed to eliminate — the failure mode just moved.

**Recommendation:** split the handler contract *now*, before more subscribers
exist. Tier 1 handlers (audit) re-raise and roll back with the publisher;
everything else is Tier 2 (ADR-0010) where isolation is correct. The current
"isolate everything" policy is the correct *Tier 2* semantics accidentally
applied to Tier 1.

### P0-2 · The Tally connector assumes a network path that will not exist

`08-integrations.md` treats Tally as an HTTP-XML server at
`192.168.1.10:9000`. That address is the tenant's **office LAN**. Nyx's
production shape (a hosted FastAPI + Postgres) cannot reach it: Tally runs
on-prem, un-NATed, behind a consumer router, on a machine that is off at
night. Every Indian-SME integrator hits this; none of the eleven Tally pages
in the docs mention it.

**Recommendation:** decide the bridge model *before* building the connector,
because it changes the connector's kind. Options, in order of preference:
(a) a tiny on-prem agent that polls Nyx for pending vouchers over HTTPS
(outbound-only, survives NAT) and pushes to local Tally — this inverts the
connector from *push* to *queue-and-collect*; (b) require the tenant to expose
Tally via a tunnel (fragile, support-heavy); (c) file export the accountant
imports manually (the current dry-run XML is already 80% of this). The
existing dry-run-first design is the saving grace: ship (c) as the honest v1,
build (a) as the real integration.

### P0-3 · "Most recent prompt wins" can approve the wrong invoice

`09-conversational.md` §4 resolves an inbound reply against the user's *most
recent unexpired* pending prompt. For `done_or_issue` on warehouse tasks the
blast radius of a mismatch is small. For `approve_reject` it is not: a founder
with two open approval prompts (INV-1029 for ₹2.4L, then INV-1030 for ₹8L
arrives) who replies `APPROVE` meaning the first one **approves the second**.
The worked example (§9.3) only shows a single open prompt; the design never
addresses concurrent approvals, which for a busy founder is the *normal* case.

**Recommendation:** for money-moving prompt shapes, one of: (a) allow only one
open `approve_reject` prompt per user — queue the rest and send the next after
the current one resolves; (b) require the reference in the reply
(`APPROVE 1029`) and treat a bare `APPROVE` with >1 open prompt as ambiguous →
ask; (c) interactive-button replies (WhatsApp supports them) that carry the
prompt ID in the callback payload. Option (c) is the strongest and cheapest;
(a) is an acceptable v1. A bare-text protocol that is fine for `DONE` is not
fine for approvals.

### P1-1 · Per-subject ordering is promised, and the retry design breaks it

`05-event-bus.md` §9 guarantees per-subject ordering via subject-hashed queue
buckets, and §7 gives failed handlers retries with backoff (30s/5m/30m). These
two composed are a contradiction: event A (invoice X) fails and enters a 5-minute
backoff; event B (same invoice X) arrives and processes immediately;
A then succeeds — **out of order, on the same subject**, exactly what the
ordering guarantee exists to prevent (state-machine coherence in FI).

**Recommendation:** pick one semantics and document it: (a) a failed delivery
*blocks its subject's bucket* until resolved (ordering preserved, head-of-line
blocking accepted and alertable) — right for state-machine consumers; or
(b) ordering is best-effort and every consumer must tolerate reordering (then
delete the guarantee from the doc — an undelivered promise is worse than none).
For an audit-first platform, (a) per-subject blocking with DLQ escape is the
defensible choice.

### P1-2 · Tier 1 reentrancy is unbounded

Workflow advancement is a Tier 1 (in-transaction) subscriber, and workflow
actions can publish events (`core.events.publish`), which re-enter the bus,
which can advance more workflows — all inside the *original* HTTP request's
transaction. A definition chain three workflows deep executes as one giant
transaction with one giant lock footprint, and a cycle between two definitions
is an infinite loop holding a DB transaction. `06-workflow-engine.md`
acknowledges cycles *within* a definition (`max_iterations`) but not cycles
*across* definitions via events.

**Recommendation:** (a) cap synchronous publish depth (e.g. 5) — beyond it,
spill to Tier 2; (b) detect definition-level cycles at publish-validation time
where trigger/emit pairs are statically known; (c) put a hard step budget per
correlation_id per transaction. Cheap now, an outage post-mortem later.

### P1-3 · RBAC's shipped surface cannot express what the modules need

`can(user, permission)` today is a boolean over a static enum — no `tenant_id`
parameter, no resource, no scope, no `Decision` reason for the audit log
(`rbac.py:62`). The docs (07) specify role × permission × scope with
warehouse-level scoping, which **Warehouse and Operations need on day one**
(a picker may complete only their warehouse's tasks). The gap is documented,
but its *ordering* isn't: if module #2 ships against the boolean `can()`,
scope semantics get bolted on under live routes.

**Recommendation:** upgrade the `can()` **signature** (resource + tenant +
Decision return) before module #2, even if the implementation stays
static-role-backed initially. Routes written against the right signature don't
churn when the DB-backed model lands. This belongs in the same milestone as
the module reorg (ADR-0009).

### P1-4 · The engine's retry model quietly demands universal idempotency

`engine.py` has no per-step resume cursor; `retry()` **replays every step from
the top** and the docstring says this is safe "exactly because every
registered action is expected to be idempotent." Today's actions are. But
nothing *enforces* the expectation — the registry accepts any callable, and
the docs' `ActionSpec.idempotent` flag (06 §5.1) doesn't exist in code. The
first non-idempotent action someone registers (send a WhatsApp message, call
Tally without an idem key) turns every retry into a duplicate side effect.

**Recommendation:** in Stage 1 (ADR-0013), make the registry require the
declaration: `idempotent: bool` mandatory, and `retry()` refuses to replay an
instance whose executed steps include a non-idempotent action. That is 20
lines now versus a duplicate-voucher incident later. (The docs' Appendix B
checklist is good — make the registry enforce its first four questions.)

### P1-5 · The documented condition evaluator has a DoS surface the shipped one doesn't

The shipped condition language (dict equals/in) is safe. The documented
Stage-1+ evaluator (06 §4.4) `eval()`s an AST-allowlisted expression with
`{"__builtins__": {}}`. The allowlist blocks calls and dunders (good) but
permits arithmetic on untrusted-sized operands: `"x" * 999999999 * 999999999`
(Mult is allowed; strings live in context) allocates gigabytes inside a
request. Admin-authored, so the threat is misuse-not-attack — but "admin
YAML cannot take down the process" is exactly the promise the restricted
language makes.

**Recommendation:** when building the evaluator: cap expression length and AST
node count; forbid Mult between str/list operands (type-check operands at
eval); add an evaluation timeout. Also: evaluate against **plain JSON data
only** — never pass ORM objects into the context namespace, or `ast.Attribute`
walks become a lazy-loading query gun.

### P2-1 · Event schema lacks correlation/causation — retrofit gets pricier weekly

The `events` table (migration 0003, `bus.py` DomainEvent) has no
`correlation_id`, `causation_id`, `version`, or actor-kind sentinel — all
load-bearing in the docs (05 §10's incident-tracing story is the platform's
best operational feature). Every event written today is an event that will
never trace.

**Recommendation:** add the columns (nullable) + contextvar propagation in the
same PR as ADR-0010's outbox — both touch `publish()`, and Tier 2 debugging
without correlation IDs is grep-archaeology.

### P2-2 · Scheduler HA/leadership is unaddressed

The scaling plan (step 5) goes multi-process, and the automation engine leans
on a scheduler for SLA timers, pull cadences, snapshot jobs. Nothing says who
runs the scheduler when there are N processes — duplicate firing (two daily
digests, double pulls) is the default failure. **Recommendation:** one line of
design now: scheduler runs as a singleton worker (rq-scheduler already
requires this) with a Redis lock as a guard; scheduled *effects* must be
idempotent like everything else.

### P2-3 · The frontend is a named layer with no architecture

The interface layer's web half gets one paragraph in STATUS and a folder
layout in 03. No decisions on: server components vs client fetching for
tenant-scoped data, OpenAPI type generation (mentioned as "future codegen"),
optimistic updates against workflow-gated mutations, or how the approval inbox
stays live (poll vs SSE). None of this blocks the backend, all of it blocks a
credible demo. **Recommendation:** a one-page frontend ADR before V1.5's
approval-inbox work; SSE on the notifications endpoint is probably the only
non-obvious call.

### P2-4 · Nothing measures the module boundary except imports

`import-linter` (ADR-0009) catches `import` statements. It does not catch the
subtler rots: module A writing module B's tables via raw SQL, shared JSONB
shapes becoming implicit contracts, or events whose payloads embed another
module's internal representation. **Recommendation:** add two cheap checks:
(a) a test asserting each module's models only map tables with its prefix;
(b) event payload schemas versioned in the registry from Stage 1 — the payload
*is* the public contract, and unversioned payloads are how event-driven
systems grow secret coupling.

---

## 3. Assumptions challenged

| # | Assumption | Challenge | Position after review |
|---|---|---|---|
| A1 | *WhatsApp Cloud API is a stable foundation for a primary UI* | Meta owns pricing (per-message, rising), template approval SLAs, and policy. A policy change is an existential UI outage; per-message pricing makes chatty workflows a COGS line. | Keep the bet (it's the differentiator) but the runtime already abstracts the connector — hold that line ruthlessly, and model per-tenant message cost in FI so the bill is visible. |
| A2 | *A custom workflow engine stays small* | Every ERP vendor said this; every ERP workflow engine became a product. The docs' own scope (waits, timers, versioning, testing harness, visualizer) is already ~5× the shipped engine. | The staging (ADR-0013) is the right containment. Add one hard rule: any proposed engine feature not in the 06 spec requires a new ADR. The spec is the fence, not the floor. |
| A3 | *Events-for-everything keeps modules decoupled* | Event coupling is still coupling — it just hides in payloads and ordering expectations. FI subscribing to `*` couples it to every payload's shape forever. | Accept, with P2-4's payload versioning as the mitigation. FI handlers must tolerate unknown fields and missing events by design. |
| A4 | *Single engineer, 8-week roadmap* (11-roadmap.md) | The roadmap predates the build and is already superseded by events: weeks 1–3 of it took one cycle and delivered *more* depth (gates, notifications, e2e tests) on *fewer* modules. The remaining weeks 4–7 (WhatsApp + 3 modules + FI) are 3–4 cycles of real work, not 4 weeks. | Re-baseline (done — see `MVP.md`/`IMPLEMENTATION_PLAYBOOK.md`, which supersede 11-roadmap's calendar while keeping its cuts list). |
| A5 | *SQLite-first dev parity is safe* | Enum/trigger/BRIN/partial-index behaviors diverge from Postgres; the docs specify Postgres-only constructs (triggers for `updated_at`, BRIN, partial unique indexes) that SQLite silently skips — tests pass where prod fails. | Acceptable *only* with the CI Postgres migration round-trip job the STATUS test-gap note already names. Make it exist before the reorg's rename migration, which is the riskiest migration yet. |
| A6 | *Application-layer tenancy is enough* (ADR-0004/0008) | The docs promise a SQLAlchemy safety hook that fails unscoped queries; it does not exist in code. Until it does, isolation rests on repository discipline + tests. | The tests are real (cross-tenant 404s), so accept for now — but the hook is cheap and is the difference between "we test it" and "we enforce it." Schedule with the RBAC signature work (P1-3). |
| A7 | *OCR quality is mitigated by human verification* | True for correctness, but the economics matter: if 80% of invoices park at `needs_verification`, the automation pitch collapses into a data-entry tool with extra steps. | Track verify-queue rate as a first-class FI KPI from day one; it is the product's honesty metric. Swap the extractor (LayoutLM/vision-LM behind the same interface) when the rate, not the vibes, says so. |

---

## 4. Internal contradictions found (must be resolved, all cheap now)

| # | Contradiction | Resolution adopted |
|---|---|---|
| C1 | `04-database.md` §3.1 mandates **UUIDv4** client-side; `05-event-bus.md` §3 mandates **UUIDv7** for event IDs (time-sortable, used as ordering tiebreaker) | Events get UUIDv7 (ordering needs it); entities stay UUIDv4 until the stack supports v7 cleanly. Record in the event-schema PR (P2-1). |
| C2 | `09-conversational.md` schemas use `BIGSERIAL`/`BIGINT` PKs; `04-database.md` §3.1 mandates UUID PKs everywhere | 04 wins; 09's DDL is illustrative and must be rewritten UUID when built. |
| C3 | `05-event-bus.md` §5: events "retained indefinitely in v1"; `04-database.md` §4.9: "hot 90 days, archived thereafter" | Indefinite in v1 (nothing to archive yet); retention becomes real at scaling step 6 (`ARCHITECTURE.md` §12). |
| C4 | Docs 03/04 plan migrations `0002_platform_core`, `0003_module_prefix_rename`, …; the repo's real chain 0001–0007 is entirely different | The real chain is canonical; doc numbering is illustrative-only (noted in ARCHITECTURE.md §9 and ADR-0009). |
| C5 | `07-rbac.md` puts scope on `rbac_user_roles` ("not the role itself"); `04-database.md` §4.5 *also* puts scope on `rbac_role_permissions` | 07 wins: scope attaches to the grant (user_role). One scoping site; two is how contradictory grants happen. |
| C6 | ADR-0003 says the runner is "<500 LOC"; `06-workflow-engine.md` says "~1,500 lines is the right size" | Non-binding size talk; the binding constraint is the anti-goals list. (Today's engine: 152 lines.) |
| C7 | `04-database.md` §4.9 events table has `delivery_status` columns; `05-event-bus.md` §5 has `delivered_to` JSONB instead; shipped 0003 migration has neither | ADR-0010's outbox table owns delivery state; the events row stays immutable (cleanest of the three designs). |
| C8 | `02-modules.md`/`00-vision.md` five-module roster & CRM non-goal vs the ten-domain mandate | Resolved by ADR-0011 (Warehouse split; CRM narrowed to registry; funnel-CRM still banned). `DOMAIN_MODEL.md` authoritative. |
| C9 | `01-platform-overview.md` allows "Accounts → Operations: link invoice to order/PO" sync call; `02-modules.md` DAG draws Accounts at the bottom with no such edge rendered | The call is legitimate (query-style); `DOMAIN_MODEL.md` §12 enumerates it explicitly. Prose lists, not diagrams, are the source of truth for allowed calls. |

---

## 5. Prioritized recommendations (what I would actually do next)

1. **Fix Tier 1 semantics (P0-1)** in the same PR as the outbox (ADR-0010):
   audit re-raises; everything else moves to Tier 2. Add correlation/causation
   columns while `publish()` is open (P2-1). *One PR, three findings closed.*
2. **Decide the Tally bridge model (P0-2) now, build later.** It changes the
   connector contract; a one-page ADR prevents building the wrong connector.
3. **Module reorg (ADR-0009) + RBAC signature upgrade (P1-3) + tenancy safety
   hook (A6)** as one milestone — all three are "before module #2" work.
4. **Write the ordering-vs-retry semantics down (P1-1)** inside ADR-0010's
   implementation; choose per-subject blocking.
5. **Engine Stage 1 with enforced idempotency declarations (P1-4) and the
   evaluator guards (P1-5).**
6. **Approval prompt disambiguation (P0-3)** goes into the conversation
   runtime's design before any WhatsApp code exists — it is a data-model
   requirement (prompt references), not a polish item.

Everything else on the review is tracked in `GITHUB_ISSUES.md`.

---

## 6. What I did not flag

Deliberately not raised, with reasons: **Postgres as a single point of
failure** (correct trade at this scale; backups + replica path exist) ·
**no caching layer** (nothing measured needs one; adding Redis caching now
would be resume-driven) · **Python/FastAPI throughput** (the workload is
I/O-thin and human-paced; the modular monolith saturates far above target
load) · **absence of Kubernetes/Terraform** (a single VPS + systemd is the
honest deployment story for the target market, and the docs already say so).

The strongest thing about this architecture is that it knows what it is not.
The review's job was to make sure it also knows where it is not yet what it
claims — that list is above, and it is all fixable in weeks, not quarters.
