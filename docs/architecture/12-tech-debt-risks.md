# 12 — Technical Debt & Risks

This document is deliberately honest. Every architecture has debt — pretending otherwise is the first interview tell that betrays inexperience. We list what we owe, what could bite us, and what we'd do about it.

## Resolved in the foundation cycle (2026-06-30)

The first implementation cycle paid down several debts and built three core-layer
foundations. See `STATUS.md` for the full picture.

- **TD-1 (coarse roles) → addressed.** A permission layer (`app/core/rbac.py`,
  `can()` / `require()`) now gates every route; the role enum maps to permission
  sets. DB-backed dynamic roles remain future work.
- **TD-2 (static activity feed) → resolved.** The dashboard panel renders live
  domain events from `GET /api/v1/activity` over the durable event log.
- **TD-4 (`.env.example`) and TD-5 (CI) → already present** in the tree
  (`backend/.env.example`, `.github/workflows/ci.yml`).
- **TD-6 (legacy `LedgerFlow.html`) → gone** from the tree.
- **TD-7 (sparse tests) → much improved.** Backend tests 20 → 49, now covering
  storage, workers, dashboard, tenancy, events, RBAC, audit, activity, workflow.
- **New foundations built:** tenant-aware schema (ADR-0008), in-process event bus
  + durable log (ADR-0002), permission RBAC (ADR-0004), and a right-sized
  workflow engine with durable instances (ADR-0003).
- **Four pipeline bugs fixed** (inline OCR event-loop crash, auto-reconcile FK,
  SQLite dashboard SQL, inline status clobber) plus an audit-serialization bug.

Still open from the list below: TD-3 (OCR/human-verify), TD-8 (auth hardening),
TD-9 (S3 smoke test). New debt this cycle: audit writes directly *and* emits
events (converge onto the bus); tenant **reads** not yet uniformly scoped.

## Existing technical debt (pre-redesign)

These are debts the current codebase already carries that the redesign must either pay down or consciously defer.

### TD-1: Three-value role enum is too coarse
**State:** `UserRole = admin / accountant / viewer`, checked in FastAPI deps.
**Cost:** Cannot model department-scoped, warehouse-scoped, or approval-chain authorization. Will not survive multi-tenant.
**Plan:** Replaced in Week 1 by the RBAC system. Backfill mapping documented in `07-rbac.md`.
**Risk if deferred:** Any module beyond Accounts needs richer authz; deferring blocks Operations and CS.

### TD-2: Static activity feed on the dashboard
**State:** `frontend/app/(dashboard)/page.tsx` mixes live API data with a hardcoded `ACTIVITY` array (a comment in the file acknowledges it).
**Cost:** Demos badly under scrutiny; misrepresents capability.
**Plan:** Replaced by FI subscribers in Week 7. Until then, render from `/api/v1/audit?limit=N`.
**Risk:** Low — purely cosmetic.

### TD-3: OCR pipeline is regex-based on Tesseract output
**State:** `app/services/ocr_service.py` extracts invoice fields via regex over raw text.
**Cost:** Accuracy depends entirely on PDF formatting. Confidence numbers are dependable but the field hit-rate is not.
**Plan:** Add a human-verification screen (Week 3) so OCR is treated as a *suggestion*, not a source of truth. A model-based extractor (e.g., Donut, layoutLM, or a Vision-LM API) can swap in later behind the same `OCRService` interface.
**Risk:** Medium — but mitigated by human verify. Don't optimize OCR before that screen exists.

### TD-4: `.env.example` referenced but not in tree
**State:** README references it; the file is missing.
**Cost:** Fresh-clone friction.
**Plan:** Add in Week 1 alongside the platform foundations commit. Trivial.

### TD-5: No CI workflow
**State:** A chore commit mentions CI setup but `.github/workflows/` is empty.
**Cost:** No automated lint, type check, or test on PRs. The `import-linter` discipline (Week 8) has nothing to enforce against until CI exists.
**Plan:** Add CI in Week 1; expand checks each week as the codebase grows.

### TD-6: Legacy `frontend/LedgerFlow.html`
**State:** Pre-rename static mockup still in the tree.
**Cost:** Cosmetic; confuses readers.
**Plan:** Delete in the architecture commit.

### TD-7: Sparse test coverage
**State:** Three test modules (auth, invoices, reconciliation). No tests for vendors, dashboard, audit, workers.
**Cost:** Refactor risk.
**Plan:** Each new module added under `app/modules/` ships with at least a smoke test in its `tests/`. The Week 8 hardening sprint adds the cross-module integration tests for canonical flows.

### TD-8: Auth hardening gaps
**State:** No email verification, no password reset, no token revocation list. Rate-limited login is in place.
**Cost:** Demo-acceptable, production-blocking.
**Plan:** Acknowledge as v2 work. Not on the 8-week MVP.

### TD-9: S3 storage path unverified
**State:** `StorageService` has the S3 code path but it hasn't been smoke-tested against a live bucket.
**Cost:** Storage swap may fail under real load.
**Plan:** Add an integration test against MinIO in CI in Week 8.

## Debt introduced *by* this redesign (and accepted)

The redesign also creates new debt. We accept each consciously.

### ND-1: Custom workflow engine
We are building our own workflow engine instead of using Temporal. **Why accepted:** demo simplicity, interview-narratable, replaceable behind a thin facade. **Cost:** we own its bugs. **Mitigation:** keep the runner deliberately small (<500 LOC), test heavily, document the upgrade path to Temporal in an ADR.

### ND-2: In-process event bus first; Redis fanout second
Synchronous in-proc delivery is the default. **Why accepted:** kills latency and ordering pain for the common case. **Cost:** a long-running handler can stall the request thread. **Mitigation:** lint rule that flags subscribers without `@async_handler` over 50ms in tests; route slow handlers via Redis fanout.

### ND-3: Single Postgres for transactional + read-aggregate data
FI aggregates share the same DB as transactional tables. **Why accepted:** one database is a feature for an SME workload; cross-database queries are not. **Cost:** read traffic from FI can compete with writes under load. **Mitigation:** FI queries are simple, indexed, and bounded; add a read replica if it ever matters.

### ND-4: Application-layer tenant scoping (no RLS)
We enforce tenant boundaries in services and a query helper, not via Postgres RLS. **Why accepted:** RLS adds testing and operational overhead disproportionate to current needs (see `07-rbac.md`). **Cost:** a missed `tenant_id` filter is a data leak. **Mitigation:** a SQLAlchemy event hook + integration tests that simulate cross-tenant queries.

### ND-5: YAML workflow definitions, no UI editor yet
Workflows are edited as YAML in the DB; no drag-and-drop builder. **Why accepted:** the builder is a 3-month project on its own and not the architectural point. **Cost:** non-technical admins can't edit workflows without help. **Mitigation:** add a syntax-highlighted YAML editor in Week 8; full drag-drop is v2.

### ND-6: WhatsApp templates require manual approval at Meta
Cloud API requires pre-approved templates for transactional sends. **Why accepted:** unavoidable per platform constraint. **Cost:** new outbound shapes need a 24h+ approval cycle. **Mitigation:** seed a small fixed set of generic templates ("{task} requires {action}") that cover most cases.

### ND-7: No tenant onboarding flow yet
Schema is tenant-aware; UI for creating a new tenant is not. **Why accepted:** MVP demos single-tenant; multi-tenant onboarding is a 1–2 week feature on its own. **Cost:** internal seeding required to create a tenant. **Mitigation:** scripted seed; build onboarding in v2.

## Risks and mitigations

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | The "modular monolith" rots into a ball of mud — cross-module imports creep in | High over time | High | `import-linter` in CI (Week 8); module-boundary checklist in PR template |
| R2 | The workflow engine becomes a kitchen sink with a Turing-complete DSL | Medium | High | The action registry is the only extensibility point; conditions are intentionally restricted (no function calls). Documented in `06-workflow-engine.md` |
| R3 | WhatsApp templates rejected by Meta block a demo | Medium | High | Seed templates two weeks before any demo; have a web-UI fallback for the same workflow |
| R4 | Tally connector breaks for a tenant with a non-standard Tally configuration | High | Medium | "Dry-run" mode shows XML before push; per-tenant XML mapping config; explicit error surface in Settings → Integrations |
| R5 | OCR accuracy disappoints in a demo | High | Medium | Always go through human-verification screen; never show "auto-pushed to Tally" with low confidence; demo with a curated invoice |
| R6 | Event bus delivery silently drops events | Low | High | Events persisted in `events` table before fanout; failed handlers land in DLQ; replay tool exists |
| R7 | FI aggregates drift from event log (subscriber bug) | Medium | Medium | Replay-from-zero capability; snapshot job aborts if FI subscriber high-water-mark is too old |
| R8 | Approval workflow stalls because the approver is on holiday | Medium | Medium | SLA on each step; on breach, escalate per chain; emit `rbac.approval.sla_breached` event |
| R9 | A tenant's connector credentials leak | Low | Catastrophic | Encryption at rest with a platform key; never logged; rotation procedure documented; least-privilege IAM on the platform-key KMS |
| R10 | Demo against live Shopify fails due to network/API issue | Medium | High | Recorded fixtures + stub connector for demo; live mode only after fixtures verified |
| R11 | Interviewer asks "why didn't you use [Kafka / microservices / Temporal / Mongo]" | Certain | Low | Each "no" has a written ADR (see `adr/`) explaining the trade-off |
| R12 | Roadmap slips and Week 8 demo is incomplete | Medium | High | The "cuts list" in `11-roadmap.md` is pre-decided. Defend the cut, not the omission |

## Risks specifically about the *repositioning*

The decision to evolve from "finance product" to "platform" introduces narrative risks too.

### NR-1: "Why not just polish the finance product?"
An interviewer may push that a finished narrow product beats a half-built platform. **Answer:** the work isn't lost — finance is the first and most-built module — but the platform framing turns one accuracy-of-OCR debate into a system-design conversation. The architecture is the interviewable artefact.

### NR-2: "Are you over-engineering for what is, in practice, a CRUD app?"
Possible read. **Answer:** event bus + workflow engine + RBAC are platform primitives — they exist *once* and serve all modules. Without them, every module reinvents authorization, async coordination, and audit. The investment pays back at the second module, which is exactly where we are.

### NR-3: Scope creep toward becoming an actual ERP
The same vision that powers placement value tempts us to add HR, payroll, CRM, etc. **Answer:** the explicit non-goals list in `00-vision.md` is the firewall. Every "what about adding X" gets pushed to v2 if it isn't on the 8-week plan.

## Talking points for placement interviews

Pre-rehearsed answers grounded in this architecture:

**Q: "Why a modular monolith and not microservices?"**
- Operational overhead and distributed-system bugs at this team / scale are losses, not investments.
- Modules are bounded by code, not by network. Communication is in-process events, no network failure modes.
- A microservices migration path exists: each module's `__init__.py` is already the public interface; a service boundary would simply make those interfaces HTTP.

**Q: "How do you handle cross-module consistency?"**
- Inside a single transaction (event publish happens after commit but before response).
- The event bus has at-least-once delivery + idempotent handlers + a durable `events` table.
- We deliberately accept eventual consistency for FI aggregates (~seconds) and reject it for transactional state.

**Q: "How does the same authorization work for web and WhatsApp?"**
- One `can(user, action, resource)` function. Both interfaces call it. Both write the same audit row with matched role.
- Principal resolution differs (JWT vs phone-claim); the check after that is identical.

**Q: "What happens if Tally is down for two hours?"**
- The `acc.invoice.verified` event still publishes. The Tally push step in the workflow retries with backoff. The instance parks if the failure persists. Audit shows the failure and the retries. On Tally recovery, the parked instance resumes automatically.
- We never block the verification flow on Tally availability.

**Q: "Walk me through what happens when a CS rep replies `ESCALATE`."**
- Webhook → runtime → principal → matches a `pending_prompt` on a ticket → intent `ESCALATE` → RBAC check `ticket.escalate` → service mutates ticket → emits `cs.ticket.escalated` → workflow on that event creates an approval task for the CS lead → FI subscriber increments daily escalations → notification fires to CS lead via in-app and WhatsApp.
- Same path a UI click would take. Different entry point, identical downstream.

**Q: "What's the riskiest part of this design?"**
- The workflow engine. Custom-built. Bugs in the runner manifest as stuck instances. Mitigation: small surface, heavy tests, parked-instance alerting, replaceable behind a thin facade.

**Q: "What would you do differently if you had three more months?"**
- Multi-tenant onboarding + per-tenant integration credentials with a real KMS.
- Workflow definition editor in the UI.
- A second connector per category (Outlook alongside Gmail; Amazon alongside Shopify).
- An anomaly-detection layer on top of FI events.
- Migrate the workflow engine to Temporal if the volume justifies it.

## Closing principle

> Debt and risk are both inevitable. The win is naming them clearly, choosing them deliberately, and never being surprised by them in a room.

Everything in this document is defensible. Anything not in this document is something we missed. Add to it the moment you notice.
