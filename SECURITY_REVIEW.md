# NYX — Security Review

**Date:** 2026-07-08 · **Scope:** the shipped backend (per `STATUS.md`, 107
tests), plus the target designs in `docs/architecture/` and `ARCHITECTURE.md`
where they introduce security-relevant machinery (workflow conditions,
WhatsApp principal handling, connector credentials).
**Method:** code reading (`app/core/security*, rbac, events, workflow,
middleware, limiter`, services, migrations), doc review, and STATUS
cross-check. No dynamic testing / no pentest — findings are architectural and
code-level.

**Posture summary:** appropriate for the current stage — a single-tenant
pre-production system with real auth, real tenant scoping proven by tests,
and no external inbound surfaces yet. The dominant risks are (1) auth
lifecycle gaps (TD-8) that block any real multi-user deployment, (2) the
audit-atomicity gap that undermines the system-of-record claim, and
(3) several *designed-but-not-yet-built* surfaces (WhatsApp webhook, workflow
condition evaluator, credential store) whose specs need security conditions
attached **before** they are built, which is the cheapest moment.

Severity: **Critical** (exploitable path to cross-tenant data or money) ·
**High** (blocks production; realistic abuse) · **Medium** (hardening;
defense-in-depth) · **Low** (hygiene).

---

## 1. What is already right

- **Tenant isolation is real and tested.** Reads, writes, and audit rows are
  uniformly tenant-scoped in the repositories; cross-tenant get/update/verify
  return 404 (not 403 — no existence oracle), and adversarial e2e tests prove
  it. This is the platform's most important control and it is in the best
  shape of anything reviewed.
- **Authentication basics:** bcrypt password hashing, JWT access+refresh,
  login rate-limiting (slowapi), password-change endpoint.
- **One authorization path:** every route goes through
  `require(permission)` → `can()`; nothing inspects `user.role` inline.
- **Upload discipline:** content-type and size validation, SHA-256 dedup, no
  execution of uploaded content; OCR treats extraction as suggestion with a
  human-verify gate for low confidence.
- **No dangerous evaluation:** workflow conditions are a restricted data
  structure (`equals`/`not_equals`/`in`) — there is no `eval` anywhere in the
  execution path today.
- **Durable, transactional event log:** the forensic record commits with the
  business write.
- **Secrets hygiene baseline:** no credentials in the repo; `.env`-driven
  config; structured logging that doesn't log request bodies.

## 2. Findings — current code

### SEC-1 · High · No token revocation, no email verification, no password reset (TD-8)

A JWT issued is valid until expiry regardless of password change, user
deactivation, or compromise; registration accepts any email unverified; there
is no reset flow (so ad-hoc resets will happen out-of-band, badly).
**Impact:** an offboarded employee or a stolen refresh token retains access;
account takeover recovery is manual DB surgery.
**Fix (pre-any-real-deployment):** refresh-token rotation with a server-side
denylist (jti) checked on refresh; revoke-on-password-change and
revoke-on-deactivation; email verification + time-boxed single-use reset
tokens; short access-token TTL (≤15 min) so the denylist only needs to cover
refresh. This is `IMPLEMENTATION_PLAYBOOK.md` Phase 1 work.

### SEC-2 · High · Audit trail is best-effort, not atomic (= ARCHITECTURE_REVIEW P0-1)

`EventBus.publish()` swallows subscriber exceptions, so a failing audit
subscriber lets the business write commit without an audit row. For a platform
sold on auditability this is a security finding, not just a correctness one:
an attacker (or a bug) that can make the audit handler raise can act without
trace in `audit_logs` (the `events` row still lands, which mitigates —
but the *human-facing* trail diverges).
**Fix:** Tier 1 handlers re-raise (roll back with the publisher); ship with
ADR-0010.

### SEC-3 · Medium · System JWT secret and crypto config lack guardrails

`SECRET_KEY` comes from env with a dev default; nothing refuses to boot in
production mode with the default key, and there is no key-rotation story for
JWTs. **Fix:** fail startup when `ENV=production` and the secret is default /
shorter than 32 bytes; document JWT key rotation (dual-key verify window).

### SEC-4 · Medium · Upload dedup race (TD-12)

Check-then-insert dedup means two concurrent identical uploads can both pass
the check (no unique constraint, deliberately, to keep FAILED re-upload
working). **Impact:** duplicate invoices entering the pipeline — an integrity
issue with financial consequences downstream (double approval requests).
**Fix:** partial unique index on `(tenant_id, sha256) WHERE status !=
'FAILED'` (Postgres) with the SQLite path falling back to the current check;
or a dedup decision inside a single `INSERT ... ON CONFLICT`.

### SEC-5 · Medium · No security headers / CORS review recorded

Middleware sets request logging and tenant context; there is no recorded
decision on CORS allowlist, `X-Content-Type-Options`, `X-Frame-Options`/CSP
for the dashboard, or cookie flags (the frontend stores JWTs — where and how
is a frontend-ADR question, see review P2-3). **Fix:** one hardening pass +
a paragraph in the frontend ADR; prefer httpOnly-cookie refresh tokens over
localStorage if the dashboard is the only client.

### SEC-6 · Low · Rate limiting covers login only

Registration, refresh, upload, and (future) webhook endpoints have no
per-principal throttles. **Fix:** extend limiter policies when each surface
ships; uploads get per-tenant daily quotas (also a cost control).

### SEC-7 · Low · `requirements.txt` hygiene (TD-10)

Duplicate `httpx`, unused `pypdf2` — unused parsers are attack surface and
audit noise. **Fix:** remove; add `pip-audit` to CI.

## 3. Findings — target designs (conditions to attach before building)

### SEC-8 · High · WhatsApp inbound is the largest new attack surface

The conversational design (09) is security-conscious (signature verification
before any processing, phone-claim + OTP with attempt lockout, RBAC re-check
at action time, revocation cancelling open prompts, no state mutation for
unknown senders). Hold these **plus** the review's P0-3 (approval prompt
disambiguation — a *financial authorization* integrity control, not UX):
approval-shaped prompts must carry an explicit reference or be limited to one
open per user.
Additional conditions: webhook endpoint rate-limited and 401-on-bad-signature
with alerting (signature failures are probes); OTP messages must never
contain context that confirms a valid employee target; prompt expiry enforced
server-side, never by message text.

### SEC-9 · High · Workflow condition evaluator (Stage 1+) is a sandbox — treat it like one

When the AST evaluator replaces the dict conditions (ADR-0013 Stage 1), it
must ship with: node-count and length caps, operand type checks on `Mult`/
arithmetic (string/list repetition DoS — review P1-5), evaluation timeout,
plain-JSON-only context (no ORM objects), dunder rejection (already in the
sketch), and a fuzz test suite. Save-time validation is a *usability* feature;
the runtime re-validation is the *security* boundary — keep both.

### SEC-10 · High · Credential store: keep the promises already written

The integrations design (08 §11) is sound — AES-GCM envelope encryption,
KEK outside the DB, `key_id` rotation, secrets never in env/logs, split
config/credentials tables. Conditions to hold at build time: the KEK loads
from a real secret store (not a file in the repo directory); `redacted_call()`
wraps every connector's logging **by construction** (the framework logs, the
connector cannot); `auth_test` must be side-effect-free; per-tenant DEKs
before any multi-tenant hosting (ADR-0008 already says so).

### SEC-11 · Medium · Webhook connectors: HMAC + replay windows

`webhook_in` verifies HMAC (constant-time compare — already in the sketch);
add a timestamp header bound into the signature with a ±5 min window to stop
replay, and per-instance secrets so one leaked secret burns one integration.
Outbound webhooks must sign with per-subscription secrets and never include
credentials or full PII payloads (send IDs; let the receiver fetch).

### SEC-12 · Medium · Tenant-scoping safety net is documented but unbuilt

ADR-0004/0008 promise a SQLAlchemy hook that fails unscoped queries on
tenant-scoped tables outside production. Until it exists, isolation rests on
repository discipline + tests (currently good). **Fix:** build the hook with
the RBAC signature upgrade (one milestone, see review §5.3) — it converts a
testing practice into an enforced invariant.

### SEC-13 · Medium · PII handling needs one page of policy

Conversation bodies, customer identities (CRM), and invoice files are PII.
Decide and record: encryption at rest for backups; `conversation.read` gated
and audited (09 §12 already says this — keep it); no message bodies in logs
or analytics; data-deletion path per tenant (the hard-delete policy in 04 §8
actually helps here); retention for uploaded invoice files.

## 4. Threat model (summary table)

| Actor | Vector | Current control | Gap → finding |
|---|---|---|---|
| Offboarded insider | still-valid JWT / phone claim | token expiry only | SEC-1; phone-claim revocation designed (09) — build with runtime |
| Malicious tenant user | cross-tenant IDs in API calls | tenant-scoped repos + 404s + tests | SEC-12 (make it enforced) |
| External attacker | login brute force | rate limit + lockout counters | SEC-6 (other endpoints) |
| External attacker | forged WhatsApp webhook | designed: signature verify | SEC-8 conditions |
| Careless admin | pathological workflow definition | dict conditions (safe today) | SEC-9 before Stage 1 |
| Compromised DB backup | credential theft | designed: envelope encryption | SEC-10; backup encryption (SEC-13) |
| Buggy/racy client | duplicate financial records | SHA-256 dedup (racy) | SEC-4 |
| Anyone | act without audit trace | durable events row | SEC-2 (audit row atomicity) |

## 5. Priority order

1. **SEC-2** with ADR-0010 (one PR, already planned).
2. **SEC-1** auth lifecycle — gate for any real deployment (Playbook Phase 1).
3. **SEC-4 + SEC-3 + SEC-7** — small, this cycle.
4. **SEC-12** with the RBAC/reorg milestone.
5. **SEC-8/9/10/11** — attach as acceptance criteria to their build issues
   (done in `GITHUB_ISSUES.md`); they cost nothing until those features start.
6. **SEC-5/6/13** — hardening pass before first external user.

*Re-review triggers:* first WhatsApp webhook in production, first stored
tenant credential, first multi-tenant deployment, Stage-1 evaluator merge.
