# 02 — Modules & Bounded Contexts

This document is the contract between the platform and the business. It defines what each module owns, what it emits, what it subscribes to, and what it explicitly does not do.

## Module roster

| Module | Code | Owns | One-line purpose |
|---|---|---|---|
| Accounts | `acc` | Invoices, vendors, reconciliation, Tally pushes | Turn vendor invoices into clean entries in Tally with an audit trail |
| Operations | `ops` | Orders, dispatches, channels, logistics | Track the path from order to delivery across Shopify/Amazon/Flipkart |
| Inventory | `inv` | SKUs, stock levels, transfers, warehouses | Single source of truth for what is where in what quantity |
| Customer Service | `cs` | Tickets, communications, SLAs, escalations | Replace the "Excel + Gmail" support workflow |
| Founder Intelligence | `fi` | Cross-module aggregates, daily snapshot, KPI views | One page that tells the founder how the business is doing today |

## Cross-module dependencies

The dependency graph between modules must remain a DAG. The current intended graph:

```
Founder Intelligence ────── subscribes to everything (passive)
       │
       │ (no module depends on FI)
       ▼
                 ┌──────────────┐
                 │   Inventory  │◀───┐
                 └──────┬───────┘    │
                        │            │
                        ▼            │
                 ┌──────────────┐    │
                 │  Operations  │────┘
                 └──────┬───────┘
                        │
                        ▼
                 ┌──────────────┐
                 │   Accounts   │
                 └──────────────┘
                 ┌──────────────┐
                 │ Cust Service │ (independent of others; reads via events)
                 └──────────────┘
```

Allowed direct calls (synchronous, query-only):
- Operations → Inventory: stock availability checks during dispatch
- Accounts → Operations: link invoice to order/PO during reconciliation
- Customer Service → Operations: lookup order status for a ticket

Everything else is via events.

## Accounts (`acc`)

### Owns
- `acc_vendors`, `acc_invoices`, `acc_invoice_items`, `acc_reconciliation_records`, `acc_processing_jobs`
- Tally XML mapping configuration (`acc_tally_*`)
- Voucher / ledger / GST mapping per tenant

### Responsibilities
1. Ingest vendor invoices (PDF upload, email forward, future: Shopify export).
2. OCR → human verification → structured fields.
3. Reconciliation against expected amounts and POs.
4. Generate Tally XML and push via the Tally connector.
5. Provide vendor master data lookup to other modules (read-only).

### Emits
- `acc.invoice.uploaded`
- `acc.invoice.extracted`
- `acc.invoice.verified` (human approved fields)
- `acc.invoice.reconciled`
- `acc.invoice.duplicate_detected`
- `acc.invoice.tally_pushed`
- `acc.invoice.tally_push_failed`
- `acc.invoice.requires_founder_approval` (amount over threshold)

### Subscribes to
- `ops.order.received` (to auto-link if invoice matches an order)
- `workflow.approval.granted` (to advance invoices awaiting approval)

### Explicit non-goals
- No payment execution. Tally is the system of record for ledger entries; payment is out of band.
- No GST filing. We produce GST-correct entries; filing happens in Tally / by the CA.
- No purchase order creation. POs are created in Operations or imported.

### Why we keep what's already built
The existing OCR + reconciliation pipeline is solid. It moves into `app/modules/accounts/` essentially unchanged. The renames (Tally connector becomes one of many integrations; reconciliation emits events instead of mutating downstream) are surgical.

## Operations (`ops`)

### Owns
- `ops_orders`, `ops_order_items`, `ops_channels` (Shopify, Amazon, Flipkart, manual)
- `ops_dispatches`, `ops_couriers`, `ops_returns`
- Sales KPI tables (channel × day × SKU)

### Responsibilities
1. Ingest orders from sales channels via the integration framework.
2. Track dispatch lifecycle: ready → packed → handed_over → in_transit → delivered.
3. Manage returns and RTOs.
4. Provide order-status lookups to Customer Service.
5. Generate dispatch tasks routed via the Task system to warehouse staff (often via WhatsApp).

### Emits
- `ops.order.received`
- `ops.order.cancelled`
- `ops.dispatch.created`
- `ops.dispatch.handed_over`
- `ops.dispatch.delivered`
- `ops.dispatch.delayed` (workflow-detected, not channel-pushed)
- `ops.return.initiated`

### Subscribes to
- `inv.stock.below_threshold` (to block dispatch if SKU is out)
- `acc.invoice.reconciled` (to mark related PO as paid, if linked)

### Explicit non-goals
- No customer-facing tracking page. We surface tracking links from couriers.
- No warehouse management beyond stock transfers and dispatch tasks.
- No procurement / PO generation in v1.

## Inventory (`inv`)

### Owns
- `inv_skus`, `inv_warehouses`, `inv_stock_levels`, `inv_transfers`, `inv_reservations`
- Reorder rules (`inv_reorder_thresholds`)

### Responsibilities
1. Single source of truth for stock quantity per SKU per warehouse.
2. Stock transfer workflows (warehouse A → B), executed predominantly through WhatsApp tasks.
3. Reservation against pending dispatches (so we don't oversell).
4. Threshold-based alerts.

### Emits
- `inv.stock.adjusted`
- `inv.stock.reserved`
- `inv.stock.released`
- `inv.stock.below_threshold`
- `inv.transfer.requested`
- `inv.transfer.completed`

### Subscribes to
- `ops.order.received` → reserve stock
- `ops.order.cancelled` → release reservation
- `ops.dispatch.handed_over` → decrement stock, release reservation

### Explicit non-goals
- No barcode scanning / hardware integration. WhatsApp confirmation is the interface.
- No multi-currency cost accounting. Cost is per SKU per warehouse, INR.
- No batch / serial number tracking in v1.

## Customer Service (`cs`)

### Owns
- `cs_tickets`, `cs_ticket_messages`, `cs_customers`
- `cs_templates` (email / WhatsApp message templates)
- `cs_sla_policies`

### Responsibilities
1. Capture tickets from email, WhatsApp, manual entry, eventually webhook.
2. Track ticket state: open → in_progress → waiting_customer → resolved → closed.
3. Enforce SLAs via the workflow engine (e.g., first-response within 2h).
4. Surface customer history: prior tickets + orders (via Operations service interface).
5. Manage escalations through approval chains.

### Emits
- `cs.ticket.opened`
- `cs.ticket.assigned`
- `cs.ticket.escalated`
- `cs.ticket.resolved`
- `cs.ticket.sla_breached`
- `cs.message.received`
- `cs.message.sent`

### Subscribes to
- `ops.dispatch.delayed` → auto-create proactive ticket if customer has flagged the order
- `ops.order.cancelled` → auto-resolve open tickets tied to that order

### Explicit non-goals
- No CRM (lead pipeline, marketing). This is post-sale support only.
- No phone / IVR. Email + WhatsApp only.
- No multi-language ticket UI in v1 (data is multi-lingual; UI is English).

## Founder Intelligence (`fi`)

### Owns
- `fi_daily_snapshot`, `fi_kpi_*` aggregates
- `fi_alert_definitions`, `fi_alert_instances`

### Responsibilities
1. Subscribe to every event in the system and update aggregates.
2. Generate a daily snapshot at end of business day.
3. Compute cross-module KPIs (e.g., dispatch-cycle-time, recon-success-rate, CSAT).
4. Fire founder-level alerts (e.g., revenue down >20% vs 7-day avg).

### Emits
- `fi.alert.raised`
- `fi.snapshot.published`

### Subscribes to
- Everything. This is a deliberate privilege.

### Explicit non-goals
- Not a BI tool. No ad-hoc query UI, no custom chart builder. The dashboard is opinionated.
- Not a forecasting engine. Trends are visible; predictions are not made.
- Not where module dashboards live. Each module renders its own operational dashboards. FI is the **founder-only** synthesis.

## Module boundary enforcement

In code, we enforce module boundaries through:

1. **Folder layout** — each module is one folder; cross-folder imports of `models.py` or `repositories.py` are banned.
2. **`__init__.py` exports** — each module's `__init__.py` is the only legal entry point; everything else is private.
3. **Lint rule (future)** — an import-linter config flags cross-module model imports in CI.
4. **Event-first reviews** — a PR that adds a cross-module call must justify in the description why it isn't an event.

We will not introduce a fancier abstraction (interfaces, ports/adapters, hexagonal) until the boundaries are stressed by real second and third modules. The folder + `__init__.py` discipline is enough for now and stays simple.

## What is *not* a module

These are platform capabilities, not modules:

- **Workflow Engine** — used by every module; lives in `app/core/workflows/`.
- **Conversation Runtime / WhatsApp** — used by every module to surface tasks; lives in `app/core/conversation/`.
- **Notification system** — `app/core/notifications/`.
- **Integration connectors** — `app/core/integrations/`; Tally is a connector, not a module.
- **Tasks** — the generic `Task` entity is owned by `app/core/tasks/`. Operations creates tasks; Accounts creates tasks; the runtime is shared.

Putting Workflow or WhatsApp inside a module would be the most common architectural mistake. They are infrastructure for every module.
