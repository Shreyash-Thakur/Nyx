# 11 — Implementation Roadmap

## Sequencing principle

Build the **platform first**, then **modules on top**, then **the conversational layer that makes it real**. We never build a module's UI before the platform mechanisms it depends on. We never demo a dashboard before there is data flowing into the aggregates that feed it.

The roadmap is 8 weeks of focused work. Each week has an exit criterion. Slipping a week is acceptable; skipping an exit criterion is not.

## MVP scope (week 8 exit)

A working demo that shows:

1. Login → operator dashboard with module-grouped navigation.
2. Upload an invoice → OCR → human-verify → reconcile → Tally XML generated (push optional).
3. A founder approval workflow that fires when invoice amount > threshold and is approved either via web or via WhatsApp.
4. A WhatsApp inbound `DONE` against a stock-transfer task completes the task, advances the workflow, updates inventory, and emits events.
5. The Founder Snapshot page rendering today's metrics fed by event subscribers.
6. The Audit log showing every event with actor, time, and matched permission.

That's it. Operations and Customer Service modules are stubbed (tables + minimal CRUD) but not deeply built. Their depth is a v2 push.

## Week-by-week plan

---

### Week 1 — Platform foundations: tenants, RBAC, events

**Goal:** the platform layer exists in code; the existing finance functionality keeps working.

- Alembic migration 0002: `tenants`, `rbac_*`, `events`, `audit_log` (rename existing if needed).
- Seed: default tenant, system roles, permission catalogue.
- Build `core/rbac/` — `can()`, `require()` dependency, decision logging.
- Build `core/events/` — bus (in-proc + persisted log), subscriber registry, `events` table writer.
- Audit log becomes a subscriber to `*`.
- Backfill existing `user.role` → `rbac_user_roles`.
- Replace existing `require_admin`/`require_accountant` deps with `require("...")`.

**Exit criteria:**
- ✅ All existing endpoints work, gated by the new `require()` deps.
- ✅ Every state change in the existing invoice flow emits an event and appears in `events` and `audit_log` tables.
- ✅ Test: a denied request writes an audit row with reason.

---

### Week 2 — Workflow engine + Tasks

**Goal:** declarative workflows can be defined, triggered by events, and executed end-to-end.

- Alembic 0003: `workflow_definitions`, `workflow_instances`, `workflow_step_runs`, `tasks`, `task_assignments`, `task_prompts`.
- Build `core/workflows/` — YAML parser, runner, condition evaluator, action registry.
- Build `core/tasks/` — task entity + assignment + completion.
- First real workflow: `invoice_lifecycle.yaml` reproducing the existing OCR → reconcile → (future) Tally chain as workflow steps instead of hardcoded.
- Approval-chain support: a `core.approval` workflow that creates tasks for approvers and waits on `task.completed`.

**Exit criteria:**
- ✅ An invoice upload event triggers `invoice_lifecycle` workflow which advances through OCR → recon steps without any service-layer chaining code.
- ✅ A workflow definition can be reloaded from DB without restarting the app.
- ✅ Test: poison action retries with backoff then parks the instance.

---

### Week 3 — Module reorganisation + Accounts cleanup

**Goal:** code lives where the architecture says it should.

- Move `app/models/invoice.py` etc. → `app/modules/accounts/models.py` with `acc_` table prefix.
- Alembic 0004: `RENAME TABLE invoices → acc_invoices`, etc.
- Same move for services, repos, routes, workers (kept under `app/modules/accounts/`).
- Add Tally connector as the first real connector under `core/integrations/tally/`.
- Add invoice human-verification UI screen (gated by `invoice.verify` permission).
- Founder-approval workflow integrated into the invoice flow when amount > config threshold.

**Exit criteria:**
- ✅ Grep for `from app.modules.accounts` outside accounts returns only the router registration line.
- ✅ Tally XML can be generated in "dry run" mode and shown on the verification screen.
- ✅ The invoice flow now goes upload → OCR → human verify → (chain if needed) → approved → Tally XML.

---

### Week 4 — Conversational layer: WhatsApp inbound

**Goal:** the platform speaks WhatsApp.

- Alembic 0005: `conversations`, `conversation_messages`, `pending_prompts`, phone-claim fields on `users`.
- WhatsApp connector under `core/integrations/whatsapp/` (Cloud API client, template registry).
- `core/conversation/` runtime: webhook → principal resolution → intent parser → workflow runner.
- Outbound: pending-prompt-aware sender. Templates seeded for: task assignment, approval request, daily summary.
- Wire approval workflow to surface as WhatsApp message to founder when configured.

**Exit criteria:**
- ✅ Outbound WhatsApp from a workflow action lands on the founder's phone.
- ✅ Inbound `APPROVE` from that founder grants the approval, advances the workflow, returns confirmation, writes audit row.
- ✅ Inbound from an unclaimed phone is logged and rejected gracefully.
- ✅ Rule-based intents (`APPROVE/REJECT/DONE/ISSUE/HELP/MORE`) work without any LLM call.

---

### Week 5 — Operations module (orders + dispatches)

**Goal:** orders flow from Shopify into Nyx; dispatches are tracked; warehouse staff complete dispatch tasks via WhatsApp.

- Alembic 0006: `ops_orders`, `ops_order_items`, `ops_channels`, `ops_dispatches`, `ops_couriers`.
- Shopify connector under `core/integrations/shopify/` (scheduled pull → normalized `ops.order.received` event).
- Dispatch task workflow: order received → reserve inventory → create dispatch task → assigned to warehouse staff (WhatsApp) → on `DONE` decrement inventory + advance.
- Minimal Operations UI: orders list, dispatches list, channel toggle.

**Exit criteria:**
- ✅ A Shopify order in a test store becomes an order in Nyx within the pull interval.
- ✅ A dispatch task surfaces on the warehouse staff's WhatsApp.
- ✅ Reply `DONE` completes the task, fires `ops.dispatch.handed_over`, decrements `inv_stock_levels`.

---

### Week 6 — Inventory module + Customer Service stubs

**Goal:** stock is a real entity with transfers; CS module exists in skeleton.

- Alembic 0007: `inv_skus`, `inv_warehouses`, `inv_stock_levels`, `inv_transfers`, `inv_reservations`.
- Threshold alerts wired to FI alert definitions.
- Stock transfer workflow: request → approval (chain) → tasks at source + destination warehouses (WhatsApp) → completion.
- Alembic 0008: `cs_tickets`, `cs_ticket_messages`, `cs_customers`, `cs_templates`, `cs_sla_policies`.
- Minimal CS: open ticket, assign, message thread, close. SLA workflow stubbed.

**Exit criteria:**
- ✅ A stock transfer end-to-end via WhatsApp at both ends.
- ✅ Stock-below-threshold event flows to FI and surfaces as an alert.
- ✅ A ticket can be opened, assigned, replied to, resolved, with events firing throughout.

---

### Week 7 — Founder Intelligence

**Goal:** the founder snapshot is real and reads only from aggregates.

- Alembic 0009: `fi_daily_snapshot`, `fi_kpi_*`, `fi_alerts`, `fi_alert_definitions`.
- FI subscribers for every event currently emitted by Accounts, Operations, Inventory, CS.
- Daily snapshot job (RQ scheduled).
- Founder snapshot page in the web UI.
- WhatsApp daily summary template + scheduled outbound to the founder principal.
- Two seeded alerts: dispatch_delay_spike, pending_approvals_aging.

**Exit criteria:**
- ✅ Replay of the last 7 days of events produces an identical snapshot to the one stored.
- ✅ Founder snapshot page loads in <500ms with realistic data (no cross-module joins).
- ✅ WhatsApp daily summary fires at 9am tenant-local.

---

### Week 8 — Hardening, observability, demo polish

**Goal:** it's defensible in an interview and survives a 30-minute live demo.

- Integration tests: full event traces for the canonical flows (invoice → tally; order → dispatch → DONE; stock transfer; ticket lifecycle).
- Add `import-linter` config that fails CI on cross-module model imports.
- Add a `make demo` target that seeds a tenant with realistic fixtures and stubs the connectors.
- Frontend polish on the snapshot page, the audit log explorer, and the workflow definition viewer.
- Write a "how to read this repo" guide for reviewers (`docs/walkthrough.md`).
- Performance check: invoice upload to event-in-FI-aggregate < 2s p95 on a local Postgres + Redis setup.

**Exit criteria:**
- ✅ All MVP demo paths run green in CI.
- ✅ `import-linter` passes — no cross-module model imports.
- ✅ Demo script captured: 12 minutes, hitting every architectural beat.

---

## What slips first if we run out of time

If by week 6 we are behind, in priority order we **cut** (not defer indefinitely, but defer past week 8):

1. **Outlook integration** — Gmail alone covers the demo.
2. **Returns & RTO flow in Operations** — track only forward dispatches in v1.
3. **CSAT capture** in CS — keep tickets but skip CSAT survey loop.
4. **Approval chain configurable from UI** — keep chains in YAML for the demo.
5. **Founder alerts editor UI** — alerts seeded in code only.

What we do **not** cut:
- The RBAC `can()` path through web + WhatsApp.
- The events table and audit log subscription.
- At least one end-to-end WhatsApp workflow.
- The Tally connector with dry-run mode.
- The Founder snapshot page reading only from aggregates.

These five are the demo. Everything else supports them.

## After week 8 (v2 horizons, not committed)

- Tenant onboarding: a real multi-tenant signup flow with per-tenant integration credentials.
- Approval chain UI editor + workflow definition UI editor.
- Outlook, Flipkart, Amazon connectors.
- IMAP inbound for CS tickets.
- Configurable founder alerts.
- Mobile-responsive web UI (currently desktop-first).
- Generic webhook outbound to customer endpoints.

## How this roadmap is a placement asset

The week-by-week structure itself is the artefact. In an interview:

- "Walk me through how you'd build this" → you have a written, defended sequencing.
- "What would you cut under pressure?" → answer above.
- "How do you decouple modules?" → week 1 events + week 3 reorg.
- "How do you ensure auditability?" → week 1 subscriber pattern.
- "What's the riskiest part?" → conversational layer (week 4). Document why.

A roadmap that survives scrutiny is rarer than a working demo. Both are required.
