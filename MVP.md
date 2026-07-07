# NYX — MVP Definition

**Date:** 2026-07-08 · **Baseline:** the shipped state in `STATUS.md` (the
Accounts pipeline runs end-to-end; 107 tests). This document supersedes the
calendar in `docs/architecture/11-roadmap.md` (written before implementation
started) while keeping its sequencing principles and its cuts list. Execution
detail lives in [`IMPLEMENTATION_PLAYBOOK.md`](IMPLEMENTATION_PLAYBOOK.md);
this document defines *what ships when and what never ships*.

**Versioning idea:** each version is a **claim we can demo without asterisks**.

---

## V1 — "A deployable Accounts product on real platform bones"

**Claim:** a company can run its vendor-invoice workflow on Nyx in production
— multi-user, secure, auditable — and hand its accountant Tally-ready output.

**In:**

1. Everything already built (upload → OCR → verify gate → approval gate →
   reconcile → dry-run Tally XML; tenancy, RBAC-gated routes, events, audit,
   notifications, dashboard).
2. **Async event fan-out** (ADR-0010): transactional outbox, Tier 1/Tier 2
   split, DLQ + replay, correlation/causation IDs. Audit becomes atomic with
   the business write (fixes review P0-1 / SEC-2).
3. **Auth hardening** (SEC-1): refresh rotation + revocation, email
   verification, password reset, production-secret guardrails (SEC-3).
4. **Module reorg** (ADR-0009): `app/modules/accounts/` + `app/core/`
   subpackages, `acc_` table renames, `import-linter` in CI; RBAC `can()`
   signature upgraded (resource + tenant + Decision), tenancy safety hook.
5. **Workflow engine Stage 1** (ADR-0013): definitions as versioned DB rows
   (YAML), save-time validation, enforced idempotency declarations; the
   Accounts pipeline seeded as data.
6. **Tally, honestly:** dry-run XML download + accountant import runbook
   (the P0-2 bridge decision recorded as an ADR; the on-prem agent is V2).
7. Small-but-blocking fixes: upload dedup race (SEC-4), dependency hygiene
   (TD-10), invoice upload single unit-of-work (TD-5), security-headers pass
   (SEC-5).
8. Frontend: real KPI states replacing illustrative fallbacks (TD-2b); the
   verify + approval queues are first-class screens.
9. Observability Stage A (ops metrics endpoint, readiness incl. outbox drain,
   operational alerts) — ships alongside the async tier it watches.

**Exit test:** a fresh deployment, two users (accountant + founder-role), an
invoice over threshold walks the entire pipeline including a rejected-then-
corrected pass; the audit trail explains every step; a revoked user cannot
act; `pytest` green including a Postgres CI migration round-trip.

## V1.5 — "The platform proves it generalizes"

**Claim:** a second and third module run on the *same* primitives with no
platform surgery, and the floor can drive work through WhatsApp.

**In:**

1. **Task system** (`core/tasks/`): the generic human-in-the-loop entity;
   approval chains re-expressed as workflows with wait-for-task steps
   (engine Stage 2: waits, timers, scheduler).
2. **Conversational layer**: WhatsApp connector + runtime (phone claims + OTP,
   pending prompts, rule-based intents, template registry). Approval prompts
   ship with the disambiguation control (review P0-3) from day one.
   Rule-based only — the LLM classifier is V2.
3. **Inventory + Warehouse modules** (ADR-0011): SKUs, stock levels,
   movements ledger, reservations; transfers + pick tasks executed via
   WhatsApp `DONE`/`ISSUE`.
4. **Founder Intelligence v0:** event-fed daily KPI aggregates for the
   modules that exist (invoices, stock, tasks) + the snapshot page reading
   only aggregates. Alerts: parked-workflow and low-stock only.

**Exit test:** the 01-platform-overview request-lifecycle trace runs for real:
a WhatsApp `DONE` on a transfer task completes it, advances the workflow,
moves stock, notifies, audits — and the founder snapshot reflects it by
morning. Adding Warehouse required zero changes outside its folder + one
router line.

## V2 — "The operations platform"

**Claim:** orders flow in from a real channel, support runs on tickets, the
founder gets the 9 a.m. WhatsApp digest, and a second company could onboard.

**In:**

1. **Operations module** + **Shopify pull connector** (order ingest →
   dispatch lifecycle → pick tasks to Warehouse).
2. **CRM (registry) + Customer Service**: customer identity + dedup/merge;
   tickets with SLA workflows and escalation chains; Gmail send connector.
3. **FI full:** cross-module KPIs, alert definitions (tenant-editable),
   daily WhatsApp digest, `MORE` follow-up.
4. **LLM classifier fallback** for free-text issue/ticket categorization
   (rules-first per ADR-0007; confidence-thresholded to human triage).
5. **Tally on-prem agent** (the real push path) behind the V1 dry-run.
6. **Tenant onboarding/provisioning** (signup → seed roles →
   integration setup) + per-tenant DEKs (SEC-10).
7. Amazon/Flipkart connectors, returns/RTO — only after Shopify is boring.

## Out of scope — permanently (inherited + affirmed)

HRMS/payroll/attendance · funnel-CRM (leads, pipeline, campaigns — ADR-0011
narrows, does not repeal) · form builder · autonomous AI agents / LLM-decided
workflow branches · mobile app (WhatsApp is the mobile UI) · plugin
marketplace / third-party code loading (ADR-0012) · multi-region ·
realtime collaborative editing · scraping or headless-browser integrations ·
voice-note transcription as authoritative input · open-ended chatbot Q&A.

**Out of scope for MVP horizon (not permanent):** barcode/hardware, batch/
serial tracking, multi-currency, GST filing, payment execution, BI/queryable
analytics, workflow drag-drop editor (visualizer only), OPA/RLS adoption.

---

## Recruiter demo (12 minutes, architecture-first)

*Audience: engineers/interviewers. Goal: system design depth, not features.
Runs on V1; each beat names the artifact that proves it.*

1. **(1 min) Frame:** "Modular business-ops platform for Indian SMEs;
   Accounts is the first module *on* the platform, not the product."
   Show `ARCHITECTURE.md` §2 layers.
2. **(3 min) One invoice, end to end:** upload a high-value low-confidence
   PDF → watch it park at `needs_verification` → verify → park at
   `pending_approval` → approve → `RECONCILED` → Tally XML. Narrate: *"no
   service chained any of that — it's one workflow definition."* Show the
   definition row (Stage 1) and the instance's step trail.
3. **(2 min) The event spine:** the `events` table filling; audit as a `*`
   subscriber ("one write, two views"); correlation-ID SQL trace of the
   invoice's whole story.
4. **(2 min) Boundaries under test:** cross-tenant GET → 404, with the test
   on screen; `import-linter` contracts; `can()` returning a Decision with
   the matched role in the audit row.
5. **(2 min) The "why nots":** ADR index — no Kafka (0002), no Temporal
   (0003), no microservices (0001), outbox over publish-after-commit (0010).
   One deliberate trade-off each, 20 seconds apiece.
6. **(2 min) Honesty close:** `ARCHITECTURE_REVIEW.md` — "here's my own
   principal-level review finding the audit-atomicity bug and the Tally
   reachability gap, and here's the fix trail." *(This beat is the
   differentiator; nobody demos their own review.)*

**Prep:** seeded demo tenant (`make demo` target), curated invoice PDFs,
network-free (everything local; Tally is dry-run by design).

## Founder demo (10 minutes, value-first)

*Audience: the founder/ops head of an SME (the Nasher Miles shape). Goal:
"this replaces the spreadsheet-and-WhatsApp chaos." Runs on V1.5; V1-only
fallback marked.*

1. **(1 min) The pain, named:** five apps, one truth nowhere, approvals in
   DMs, the accountant re-typing into Tally.
2. **(3 min) An invoice that manages itself:** photo/PDF in → fields
   extracted → *"it wasn't sure, so it asked a human"* (verify queue) →
   *"it's ₹2.4L, so it asked **you**"* — approval arrives on the founder's
   WhatsApp; reply `APPROVE` → reconciled → *"your accountant downloads
   Tally-ready XML; nothing was re-typed."*
   *(V1 fallback: approve in the web inbox instead of WhatsApp.)*
3. **(2 min) The floor without logins:** transfer task lands on a picker's
   WhatsApp → `DONE` → stock moves, everything recorded. *"Your warehouse
   just used an ERP and doesn't know it."* *(V1.5 only.)*
4. **(2 min) One page every morning:** founder snapshot — what happened,
   what's stuck, what needs you; the 9 a.m. WhatsApp digest. *(V1.5: v0
   snapshot.)*
5. **(1 min) Trust close:** the audit trail for the invoice from step 2 —
   who touched it, when, through which channel. *"Every action, provable.
   That's the difference from the spreadsheet."*
6. **(1 min) Ask:** run one month of real invoices in parallel with the
   current process; success = zero re-typing and one caught discrepancy.

**Prep:** founder's real phone claimed beforehand (OTP flow as a teaser);
tenant seeded with their vendor names; INR formatting everywhere; no
engineering vocabulary — "workflow engine" is *"it follows your rules."*
