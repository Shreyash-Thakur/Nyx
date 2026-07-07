# NYX — Issue Backlog

**Date:** 2026-07-08 · Ready to paste into GitHub Issues (one `##` block per
issue). Ordering follows [`IMPLEMENTATION_PLAYBOOK.md`](IMPLEMENTATION_PLAYBOOK.md);
epics = phases. Labels: `platform` `security` `module:<x>` `frontend`
`observability` `docs` `tech-debt` · priority `P0`(now)/`P1`(this
version)/`P2`(next version).
Cross-refs: TD-x = `STATUS.md` debt · SEC-x = `SECURITY_REVIEW.md` ·
review-x = `ARCHITECTURE_REVIEW.md`.

---

## Epic: Phase 1 — Platform correctness (M1)

### 1. Transactional outbox + Tier-2 delivery (ADR-0010)
`platform` `P0` · closes TD-11, review P1-1, part of P0-1
Outbox rows in the publishing tx (one per Tier-2 subscriber); fanout worker
(RQ + inline parity); retry w/ backoff; DLQ rows + replay CLI; per-subject
blocking on failure.
**AC:** kill-worker-mid-fanout loses zero events (test) · failed handler
blocks only its subject's bucket (test) · DLQ replay re-runs one handler for
one event · notifications handler moved to Tier 2.

### 2. Tier-1 handlers re-raise: make audit atomic
`platform` `security` `P0` · closes SEC-2 / review P0-1
Audit (and workflow advancement) registered as Tier 1: exceptions propagate
and roll back the publisher. Bus keeps isolation for Tier 2 only.
**AC:** forced audit failure ⇒ business write rolls back, HTTP 500 (test) ·
docs 05 §7 semantics and code agree.

### 3. Correlation/causation on events
`platform` `P0` · review P2-1
Nullable `correlation_id`/`causation_id`/`actor_kind` columns; contextvar
propagation in `publish()`; request/webhook/schedule roots mint the ID;
worker jobs carry it.
**AC:** e2e invoice run yields one correlation chain queryable by a single
SQL statement (test) · events with same version-field semantics documented
(C1 resolution: events use UUIDv7).

### 4. Auth lifecycle hardening
`security` `P0` · closes SEC-1 (TD-8)
Refresh rotation + jti denylist; revoke on password change + deactivation;
email verification; single-use time-boxed password reset; access TTL ≤ 15 min.
**AC:** revoked refresh dead (test) · deactivated user's tokens dead (test) ·
reset token single-use and expiring (test).

### 5. Production secret guardrails
`security` `P1` · closes SEC-3
Refuse startup with default/short `SECRET_KEY` when `ENV=production`;
JWT dual-key verify window for rotation, documented.
**AC:** boot test matrix (dev default ok, prod default fatal).

### 6. Upload dedup race fix
`security` `tech-debt` `P1` · closes SEC-4 (TD-12)
Postgres partial unique index `(tenant_id, sha256) WHERE status != 'FAILED'`
(+ SQLite fallback path); FAILED re-upload still works.
**AC:** concurrent duplicate upload test — one wins, one 409 · FAILED
re-upload regression test.

### 7. Invoice upload as one unit of work
`tech-debt` `P1` · closes TD-5
Single transaction for the upload path (row + job + event), storage write
compensated on rollback.
**AC:** injected failure mid-upload leaves no partial rows (test).

### 8. Dependency hygiene + pip-audit
`tech-debt` `P2` · closes TD-10, SEC-7
Dedupe `httpx`, drop `pypdf2`, add `pip-audit` to CI.
**AC:** CI fails on known-vuln dependency.

### 9. Security headers + CORS pass
`security` `P1` · closes SEC-5
Explicit CORS allowlist; `X-Content-Type-Options`, frame/CSP headers for the
dashboard; document token-storage decision with the frontend ADR (#12).
**AC:** header assertions in tests; CORS wildcard absent in prod config.

### 10. Postgres CI job (migrations + suite)
`platform` `P0` · gate for Phase 2
`upgrade head → downgrade base → upgrade head` on clean Postgres; full test
suite on Postgres service container.
**AC:** CI matrix shows sqlite+postgres green; a deliberately irreversible
migration fails the job (test-of-the-test, then removed).

### 11. Observability Stage A (async tier)
`observability` `P1` · OBSERVABILITY.md §7.1
Outbox lag/depth + DLQ metrics; `/health/ready` (DB, queue, outbox drain,
scheduler heartbeat once it exists); parked/failed-workflow alert via
notifications.
**AC:** readiness flips unhealthy when fanout worker stopped (test) ·
parked instance produces an admin notification within 60s (test).

### 12. Frontend ADR + real empty states (TD-2b)
`frontend` `P1` · review P2-3
One-page ADR (data fetching, token storage, live-update strategy for
approval inbox — recommend SSE on notifications); replace illustrative KPI
fallbacks with real empty/zero states.
**AC:** no fabricated numbers anywhere with an empty API (visual test list).

## Epic: Phase 2 — Boundary milestone (M2)

### 13. Module reorg: pure moves
`platform` `P0` · ADR-0009
`app/modules/accounts/` + `app/core/*` subpackages per 03 move-map;
move-only commits; imports rewritten.
**AC:** zero behavior diff (full suite green, no test edits beyond imports).

### 14. Table prefix migration (`acc_*`)
`platform` `P0` · ADR-0009
Rename-only Alembic migration continuing the real chain; constraint/index
renames to 04 conventions; API paths unchanged (aliases allowed).
**AC:** Postgres round-trip green · old paths serve · `\dt` shows ownership.

### 15. import-linter + prefix-ownership tests
`platform` `P0` · ADR-0009, review P2-4a
Three lint contracts (modules↛modules, core↛modules, router-only) + test
asserting each module maps only its prefix.
**AC:** deliberate violation branch goes red (proof kept in PR description).

### 16. RBAC signature upgrade → Decision
`platform` `security` `P0` · review P1-3
`can(user, action, resource, *, tenant_id) → Decision(allowed, reason,
matched_role)`; routes migrate; Decision reason written to audit rows.
Static role backing unchanged (DB-backed roles are V2).
**AC:** denied request's audit row records the deny reason (test) · no route
reads `user.role` directly (grep-test).

### 17. Tenancy safety hook
`security` `P1` · closes SEC-12 / review A6
SQLAlchemy listener failing unscoped statements on tenant tables outside
production; log+alert in production.
**AC:** unscoped query raises in tests (test) · allowlisted tables
(`tenants`, `users`, `audit_logs` cross-tenant paths) documented in code.

## Epic: Phase 3 — Workflows as data + Tally decision (M3 / V1)

### 18. workflow_definitions: versioned rows (Stage 1)
`platform` `P0` · ADR-0013
YAML + parsed JSONB, immutable versions, instance pinning; save-time
validation (conditions, action refs, param schemas); publish/retire API;
seed Accounts pipeline as data and delete the Python registration.
**AC:** MVP V1 exit's no-deploy-threshold-change test · running instance
keeps old version (test).

### 19. Restricted AST condition evaluator with sandbox guards
`platform` `security` `P0` · closes SEC-9 / review P1-5
Allowlist evaluator per 06 §4 **plus**: node/length caps, arithmetic operand
type checks, timeout, plain-JSON-only context, dunder rejection; fuzz suite.
**AC:** `'x'*999999999*999999999`-class expressions rejected/capped (tests) ·
fuzz corpus in CI.

### 20. Action registry: enforced idempotency declarations
`platform` `P1` · review P1-4
`idempotent: bool` mandatory on registration; `retry()` refuses replaying
instances containing executed non-idempotent steps.
**AC:** registering without the flag fails at import (test) · retry-refusal
test.

### 21. ADR-0014: Tally bridge model
`docs` `P0` · review P0-2
Decide agent vs tunnel vs export-file; record trade-offs; V1 ships the
export runbook, V2 the chosen bridge.
**AC:** ADR merged; MVP.md/playbook references stay consistent.

### 22. Connector framework skeleton + Tally as first connector
`platform` `P1` · SEC-10 conditions attached
`Connector` ABC (push/pull/receive), registry,
`integration_configs`/`integration_credentials` (AES-GCM envelope, KEK from
secret store, `key_id` rotation), framework-owned `redacted_call()` logging,
`integration_call_log`; `tally` connector wraps the existing dry-run service.
**AC:** secrets never appear in logs (test with canary secret) · `auth_test`
side-effect-free · dry-run byte-identical to current service output (test).

## Epic: Phase 4 — Tasks + WhatsApp (M4)

### 23. Generic task system + engine Stage 2 (waits/timers/scheduler)
`platform` `P1` · ADR-0013 Stage 2, review P2-2
`tasks`/`task_assignments`; `wait_for_event`/`wait_for_duration` +
wait descriptors; rq-scheduler as Redis-locked singleton with heartbeat;
approval gate re-expressed as task + wait.
**AC:** approval chain runs as a workflow with zero bespoke approval code
(test) · duplicate scheduler instance does not double-fire (test).

### 24. WhatsApp connector (Cloud API)
`platform` `P1`
Token mgmt, per-phone rate bucket, template send vs free-form window
routing, `wa_message_id` capture, send idempotency by `client_send_id`.
**AC:** outside-24h freeform returns `retryable=False` template error (test)
· duplicate `client_send_id` = one API call (test).

### 25. Conversation runtime + phone claims
`platform` `security` `P1` · SEC-8 conditions are the AC
Webhook (signature verify → dedup by `wa_message_id` → enqueue → 200); OTP
phone claims (lockout, revocation cancels prompts); pending prompts;
rule-based intent registry; outbound templating.
**AC:** forged signature ⇒ 401 + metric, nothing enqueued (test) · unknown
sender mutates nothing (test) · revoked claim's prompts cancelled (test) ·
OTP 3-attempt lockout (test).

### 26. Approval prompt disambiguation
`platform` `security` `P0` (within Phase 4) · review P0-3
Approval-shaped prompts: interactive buttons carrying prompt id (preferred)
or reference-required replies; bare `APPROVE` with >1 open approval prompt
triggers a clarification, never a guess.
**AC:** two concurrent approvals cannot cross (integration test — the P0-3
scenario verbatim).

### 27. Founder approval via WhatsApp, end-to-end
`module:accounts` `P1`
Wire the existing approval gate to WhatsApp prompts + confirmations.
**AC:** docs 09 §9.3 trace as an integration test incl. audit channel
metadata.

## Epic: Phase 5 — Inventory + Warehouse (M5)

### 28. Inventory module
`module:inventory` `P1` · ADR-0011
SKUs, stock levels + append-only movements, reservations, thresholds;
`check_availability` published interface; `inv.*` events.
**AC:** stock_levels reconstructable from movements (property test) ·
reservation blocks oversell under concurrency (test).

### 29. Warehouse module + transfer workflow
`module:warehouse` `P1` · ADR-0011
Warehouse master data, transfers, pick tasks via core Tasks; transfer
workflow definition with WhatsApp prompts both ends; floor-issue capture →
`whs.issue.reported`.
**AC:** platform-overview lifecycle trace as integration test · module
recipe proven (no edits outside folder + router line — checked in PR).

## Epic: Phase 6 — Founder Intelligence v0 (M6 / V1.5)

### 30. FI subscribers + daily snapshot
`module:fi` `P1`
Idempotent Tier-2 subscribers for existing events → `fi_kpi_*`; nightly
snapshot job; snapshot page reads aggregates only; verify-queue-rate KPI.
**AC:** replay determinism (re-run N days ⇒ identical snapshot) · zero
module-table reads (grep/lint test) · page < 500 ms seeded.

### 31. Seed alerts: parked-workflow + low-stock
`module:fi` `P1`
`fi_alert_definitions` rows + cooldowns; raised alerts → notifications.
**AC:** cooldown suppresses re-fire (test).

## Epic: V2 (placeholders — refined at Phase 6 exit)

### 32. Operations module + Shopify pull connector
`module:operations` `P2` — order ingest (cursor store, per-instance
isolation), dispatch lifecycle, pick-task handoff. AC drafted with ADR at
scheduling time.

### 33. CRM registry + Customer Service module
`module:crm` `module:cs` `P2` — identity/links/merge; tickets + SLA
workflows + escalation; Gmail send connector (OAuth per 08 §8).

### 34. FI full: cross-module KPIs + WhatsApp daily digest
`module:fi` `P2` — digest template, `MORE` intent, tenant-editable alerts.

### 35. LLM classifier fallback (ADR-0007 shape)
`platform` `P2` — fixed taxonomies, confidence threshold → triage queue,
8s budget, rationale stored; never in the action path.

### 36. Tally on-prem agent (per ADR-0014)
`platform` `P2` — outbound-only polling agent; real push behind V1 dry-run.

### 37. Tenant onboarding/provisioning + per-tenant DEKs
`platform` `security` `P2` · ADR-0008 payoff, SEC-10/13 — signup, role
seeding, integration setup wizard, backup-encryption + PII policy page.

## Standing (not phase-bound)

### 38. STATUS.md regeneration discipline
`docs` `P1` — every phase-closing PR regenerates STATUS; drift between
STATUS and code is a bug.

### 39. Event payload schema registry + versioning
`platform` `P1` (starts Phase 3) · review P2-4b — payload schemas versioned
in a registry; subscribers tolerate unknown fields; breaking change = new
version int.

### 40. S3/MinIO storage smoke test in CI
`tech-debt` `P2` · TD-9 — MinIO service container exercising the S3 path.
