# NYX — Domain Model

**Status:** Living document · **Date:** 2026-07-08
**Companions:** [`ARCHITECTURE.md`](ARCHITECTURE.md) ·
[`docs/architecture/02-modules.md`](docs/architecture/02-modules.md) (original 5-module contract) ·
[ADR-0011](docs/architecture/adr/0011-domain-map-warehouse-crm.md) (Warehouse split, CRM scope)

This document defines every domain in the Nyx platform: what it owns, what it
emits, what it consumes, and — most importantly — what it refuses to do.
Boundaries are the product here; a domain model that only lists features is a
feature list.

## 1. Two kinds of domain

Nyx distinguishes **business modules** (bounded contexts owning business data,
living under `app/modules/`) from **platform capabilities** (cross-cutting
infrastructure every module consumes, living under `app/core/`). Putting a
capability inside a module is the most common architectural mistake this
document exists to prevent.

| Domain | Kind | Prefix | Status |
|---|---|---|---|
| Accounts | business module | `acc_` | **BUILT** (pending reorg into `app/modules/`) |
| Inventory | business module | `inv_` | designed |
| Warehouse | business module | `whs_` | designed (split from Inventory — ADR-0011) |
| Operations | business module | `ops_` | designed |
| CRM | business module | `crm_` | designed, deliberately narrow (ADR-0011) |
| Customer Service | business module | `cs_` | designed |
| Founder Intelligence | business module (privileged) | `fi_` | designed |
| Automation | platform capability | core tables | **partially BUILT** (workflow engine) |
| Permissions | platform capability | core tables (`rbac_*` target) | **partially BUILT** (static RBAC) |
| Integrations | platform capability | core tables | designed |

**Evolution note (ADR-0011):** the original module roster
(`02-modules.md`) had five modules. This domain map adds **Warehouse** (split
out of Inventory: stock *truth* vs stock *movement work* are different bounded
contexts with different users) and **CRM** (previously a non-goal; admitted in
a deliberately narrow form — a customer registry, not a sales pipeline). The
vision's non-goal against "CRM (lead capture, sales pipeline, marketing
automation)" still stands: *that* CRM remains out of scope forever.

## 2. Accounts (`acc`) — BUILT

**One line:** turn vendor invoices into clean, reconciled, Tally-ready entries
with a complete audit trail.

**Owns:** `acc_invoices`, `acc_invoice_items`, `acc_vendors`,
`acc_reconciliation_records`, `acc_processing_jobs`; Tally voucher/ledger/GST
mapping config (per tenant, via config store).
*(Current tables are unprefixed — `invoices`, `vendors`, … — until the module
reorg renames them.)*

**Responsibilities**
1. Ingest vendor invoices (upload today; email-forward later).
2. OCR → extraction → **human-verify gate** for low-confidence reads
   (OCR output is a suggestion, never a source of truth).
3. **Approval gate** for amounts above the founder threshold.
4. Reconciliation: reference match against a PO/expected amount when one
   exists; self-consistency check (subtotal + taxes vs total) as fallback.
   Idempotent on replay.
5. Tally XML generation (dry-run first, always) and push via the Tally
   connector.
6. Vendor master data, exposed read-only to other modules.

**Emits:** `acc.invoice.uploaded` · `.extracted` · `.needs_verification` ·
`.verified` · `.requires_founder_approval` · `.approved` · `.rejected` ·
`.reconciled` · `.duplicate_detected` · `.tally_pushed` · `.tally_push_failed`

**Consumes:** `ops.order.received` (auto-link invoice ↔ order/PO) ·
task/approval completion events (to resume gated workflows).

**Refuses to do:** payment execution (Tally owns the ledger; payment is out of
band) · GST filing (we produce GST-correct entries; the CA files) · purchase
order creation (Operations' job) · anything with customer money (that is
Operations/CRM territory — Accounts is *payables*).

## 3. Inventory (`inv`)

**One line:** the single source of truth for *what exists where, in what
quantity, at what cost*.

**Owns:** `inv_skus`, `inv_stock_levels`, `inv_stock_movements` (append-only
ledger; stock_levels is reconstructable from it), `inv_reservations`,
`inv_reorder_thresholds`.

**Responsibilities**
1. Quantity per SKU per warehouse — the number every other module trusts.
2. Reservations against pending dispatches (no overselling); soft-released,
   never deleted, so oversell attempts are auditable.
3. Reorder thresholds and `inv.stock.below_threshold` alerts.
4. Answer the one allowed synchronous query: `check_availability(sku, qty)`.

**Emits:** `inv.stock.adjusted` · `.reserved` · `.released` ·
`.below_threshold`

**Consumes:** `ops.order.received` → reserve · `ops.order.cancelled` → release ·
`ops.dispatch.handed_over` → decrement + release ·
`whs.transfer.completed` → apply the movement.

**Refuses to do:** *executing* physical work — picking, packing, moving boxes
is Warehouse's domain; Inventory only records the resulting facts ·
multi-currency cost accounting (INR only) · batch/serial tracking (not in v1/v2).

**Boundary with Warehouse (the load-bearing line):** Inventory owns **state**
(quantities, reservations, thresholds). Warehouse owns **work** (transfer
tasks, picking, physical confirmation). A transfer is *requested and executed*
in Warehouse; the completed movement is *recorded* in Inventory via events.
Neither writes the other's tables.

## 4. Warehouse (`whs`)

**One line:** the physical-work module — where stock movement is requested,
assigned to humans (predominantly via WhatsApp), and confirmed.

**Owns:** `whs_warehouses` (locations, addresses), `whs_transfers`,
`whs_transfer_items`, `whs_pick_tasks` (dispatch picking work, referencing
core Tasks).

**Responsibilities**
1. Warehouse master data (the `warehouse_id` everyone else references).
2. Stock transfer lifecycle: requested → approved (chain, if configured) →
   in_transit → received; tasks at both ends surfaced through the Task system
   and answered with WhatsApp `DONE`/`ISSUE`.
3. Pick/pack tasks for dispatches, created on `ops.dispatch.created`.
4. Issue capture from the floor ("only 8 units available") → classified →
   routed as incidents to Operations.

**Emits:** `whs.transfer.requested` · `.approved` · `.in_transit` ·
`.completed` · `.cancelled` · `whs.pick.completed` · `whs.issue.reported`

**Consumes:** `ops.dispatch.created` → create pick task ·
`inv.stock.below_threshold` → suggest transfer from a surplus warehouse.

**Refuses to do:** owning quantities (Inventory's) · courier/tracking concerns
(Operations') · barcode/hardware integration (WhatsApp confirmation is the
interface — explicit vision stance).

## 5. Operations (`ops`)

**One line:** track the path from order to delivery across sales channels.

**Owns:** `ops_orders`, `ops_order_items`, `ops_channels` (Shopify, Amazon,
Flipkart, manual), `ops_dispatches`, `ops_couriers`, `ops_returns`,
`ops_incidents`, `ops_sales_daily` (pre-aggregated, subscriber-maintained).

**Responsibilities**
1. Ingest orders from channels via pull connectors, normalized to
   `ops.order.received` — Operations never knows which channel a payload came
   from.
2. Dispatch lifecycle: packing → packed → handed_over → in_transit →
   delivered / failed; delay detection via workflow timers.
3. Returns and RTOs.
4. Order-status lookups for Customer Service (published service interface).
5. Incident triage from Warehouse floor reports.

**Emits:** `ops.order.received` · `.cancelled` · `ops.dispatch.created` ·
`.handed_over` · `.delivered` · `.delayed` · `ops.return.initiated` ·
`ops.incident.created`

**Consumes:** `inv.stock.below_threshold` → block dispatch for OOS SKUs ·
`acc.invoice.reconciled` → mark linked PO paid · `whs.pick.completed` →
advance dispatch.

**Refuses to do:** customer-facing tracking pages (we surface courier links) ·
warehouse work execution (Warehouse's) · stock truth (Inventory's) ·
procurement/PO generation in v1.

## 6. CRM (`crm`) — deliberately narrow

**One line:** one customer, one identity, one history — across channels and
modules.

**Owns:** `crm_customers` (identity: name, emails, phones, external channel
IDs), `crm_customer_links` (customer ↔ external identity per channel, e.g.
Shopify customer ID), `crm_segments` (rule-based, e.g. "repeat buyer",
"high-value"), `crm_notes`.

**Responsibilities**
1. Deduplicate and merge customer identities arriving from channels
   (Shopify/Amazon order payloads) and support tickets.
2. Provide the canonical `customer_id` that Operations orders and CS tickets
   reference.
3. Rule-based segments computed from events (order counts, ticket counts,
   lifetime value) — inputs for founder KPIs and CS context.
4. Timeline view: this customer's orders, tickets, and conversations in one
   place (read via events/aggregates, never via other modules' tables).

**Emits:** `crm.customer.created` · `.merged` · `.segment_changed`

**Consumes:** `ops.order.received` → upsert/link identity ·
`cs.ticket.opened` → link identity.

**Refuses to do — permanently (ADR-0011):** lead capture, sales pipeline,
deal stages, marketing automation, campaign sends, cold outreach. The vision
non-goal against pipeline-CRM stands. Nyx's CRM is a **registry**, not a
funnel. If a tenant asks for a funnel, the answer is an integration to a real
CRM, not scope creep here.

## 7. Customer Service (`cs`)

**One line:** replace the "Excel + Gmail" support workflow with tickets, SLAs,
and escalations.

**Owns:** `cs_tickets`, `cs_ticket_messages`, `cs_templates`,
`cs_sla_policies`.
*(Customer identity moved to CRM — `cs_customers` from the original design is
superseded; CS references `crm_customers.id`.)*

**Responsibilities**
1. Capture tickets from email, WhatsApp, manual entry, webhooks.
2. Ticket state machine: open → in_progress → waiting_customer → resolved →
   closed.
3. SLA enforcement via workflow timers (first-response, resolution);
   escalation via approval chains.
4. Customer context: prior tickets + orders (via Operations' service
   interface + CRM timeline).

**Emits:** `cs.ticket.opened` · `.assigned` · `.escalated` · `.resolved` ·
`.sla_breached` · `cs.message.received` · `.sent`

**Consumes:** `ops.dispatch.delayed` → proactive ticket if the customer
flagged the order · `ops.order.cancelled` → auto-resolve related tickets.

**Refuses to do:** anything pre-sale (CRM-funnel territory, banned) ·
phone/IVR (email + WhatsApp only) · owning customer identity (CRM's).

## 8. Founder Intelligence (`fi`) — privileged

**One line:** one page that answers, every morning: are we making money,
what's broken, what needs me, what's trending.

**Owns:** `fi_daily_snapshot`, `fi_kpi_*` aggregates, `fi_alerts`,
`fi_alert_definitions`.

**Privilege and its price:** FI is the only module allowed a `*`-adjacent
subscription (alongside the audit writer). In exchange it accepts hard
constraints: **read-only from everyone else's perspective** (no module
consumes FI data to make decisions), **eventually consistent** (Tier 2
subscriber, aggregates lag by seconds), **reads only its own aggregates** —
never module tables — so module refactors can't break the founder page and
founder page loads can't tax transactional paths.

**Responsibilities:** subscribe to everything → maintain KPI aggregates ·
nightly snapshot with 7-day/30-day deltas · alert rules with cooldowns
(revenue drop, dispatch-delay spike, Tally failures, OOS-critical SKUs,
approvals aging) · 9 a.m. WhatsApp digest.

**Emits:** `fi.alert.raised` · `fi.snapshot.published`

**Refuses to do:** BI/ad-hoc query UI · forecasting · module-level operational
dashboards (each module renders its own) · proactive LLM "insights" in chat.

## 9. Automation (platform capability)

**One line:** triggers → declarative decisions → registered effects; the
composition of the workflow engine, scheduler, and alert/notification routing
(full description: `ARCHITECTURE.md` §7).

**Owns (core tables):** `workflow_instances` [BUILT],
`workflow_definitions` + `workflow_step_runs` [TARGET], `tasks` +
`task_assignments` [TARGET], scheduler state [TARGET].

**Boundary:** Automation executes; it never contains business policy in code.
Policy lives in definitions (data). Modules register **actions** (the only way
automation touches a module) and **emit events** (the only way a module
triggers automation). A module hard-coding a multi-step process in its service
layer instead of a workflow definition is a boundary violation — this is
exactly what the Accounts pipeline migration already fixed.

## 10. Permissions (platform capability)

**One line:** "can user U perform action A on resource R in scope S?" —
answered identically for a web request, a WhatsApp message, and a worker job.

**Owns:** permission catalogue + `can()`/`require()` [BUILT, static];
`rbac_roles`, `rbac_permissions`, `rbac_role_permissions`, `rbac_user_roles`
(scoped grants), approval-chain definitions [TARGET].

**Boundary rules:**
- Modules **declare** resource types and actions; they never implement checks.
- One authorization path. A second one appearing anywhere (a "bot" identity, a
  bypass header) is a security incident by definition.
- Decisions are objects with reasons (matched role, matched scope), recorded
  to audit — not booleans.
- Approval chains are **workflow definitions** referencing approver roles —
  Permissions defines *who may approve*; Automation runs the chain.

**Refuses to do:** ABAC (fixed scope kinds only) · per-field permissions ·
negative permissions (roles are additive) · cross-tenant sharing.

## 11. Integrations (platform capability)

**One line:** all external I/O behind one connector registry — uniform,
per-tenant, fault-isolated, observable (full spec: `08-integrations.md`).

**Owns:** `integration_configs`, `integration_credentials` (encrypted),
`integration_call_log` + health rollup, cursor store for pulls, inbound
buffer for receives.

**Boundary rules:**
- A module never imports a connector class, never holds credentials, never
  parses external payloads. If a module contains `httpx.post(...)` to an
  external host, the framework has failed.
- Connectors never publish events directly; they *yield* normalized events and
  the framework persists/dedups/publishes — this is what keeps replay uniform.
- Tally is push-only (we never read the ledger back). The conversation
  runtime is **not** an integration — it is an interface-layer peer that
  *uses* the WhatsApp connector.

## 12. Interaction contract (the whole map on one page)

Allowed **synchronous** service calls (query-style only, via published
interfaces) — everything else is events:

| Caller → Callee | Call | Why synchronous is justified |
|---|---|---|
| Operations → Inventory | `check_availability(sku, qty)` | dispatch decision needs the answer now |
| Accounts → Operations | `find_order_for_invoice(...)` | reconciliation link needs it now |
| Customer Service → Operations | `get_order_status(order_id)` | agent is on the ticket now |
| Customer Service / Operations → CRM | `resolve_customer(identity)` | ticket/order needs its FK now |

Dependency DAG (arrows = "depends on / may call"; events flow freely):

```
        Founder Intelligence  (subscribes to everything; nothing depends on it)

  Accounts ──► Operations ──► Inventory ◄── Warehouse
                  │   ▲
                  ▼   │
   CRM ◄── Customer Service
    ▲
    └── Operations (customer resolution)
```

Cycles are forbidden. A proposed edge that would create one means the domains
are drawn wrong — redraw the boundary, don't add the import.

## 13. Build order (summary — full plan in IMPLEMENTATION_PLAYBOOK.md)

1. **Accounts** exists; reorg into `app/modules/accounts/` first.
2. **Automation/Permissions/Integrations** deepen as platform work, each stage
   pulled by the next module's needs — never speculatively.
3. **Inventory + Warehouse** next (they are the WhatsApp-task showcase).
4. **Operations** (needs Inventory reservations + the first pull connector).
5. **CRM** (needs order/ticket identities to exist) and **Customer Service**.
6. **Founder Intelligence** last-but-continuous: subscribers accrete as each
   module's events start flowing.
