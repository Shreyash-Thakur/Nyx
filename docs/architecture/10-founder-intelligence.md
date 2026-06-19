# 10 — Founder Intelligence

## The mandate

A founder of a 20–500 person SME does not want a BI tool. They want **one page** that answers, every morning:

- Are we making money?
- What's broken right now?
- What decisions need me?
- What is trending against last week / last month?

Everything else — drill-down, custom charts, ad-hoc queries — is a distraction. Founder Intelligence (FI) is the synthesis layer that produces that one page and the alerts that interrupt the founder when something demands attention.

## What FI is not

- **Not a BI tool.** No Looker, no Tableau ambitions. Charts are opinionated and fixed.
- **Not a query interface.** Founders don't write filters; they look at curated views.
- **Not a forecasting engine.** Trends are shown; predictions are not made.
- **Not the home of operational dashboards.** Each module renders its own. FI is *cross-module synthesis only*.
- **Not a notification spammer.** Alerts are rare by design — alert fatigue is the failure mode.

## How FI is fed

FI is a privileged subscriber to the event bus. It listens to **every** event in the system. Each subscriber handler updates one or more aggregate tables. There is no ad-hoc reading of module-private tables and no joining across modules at query time.

```
Event bus
  ├─ acc.invoice.reconciled    → fi_subscriber: incr daily.invoices_reconciled, daily.gross_payables
  ├─ acc.invoice.tally_pushed  → fi_subscriber: incr daily.invoices_tally_pushed
  ├─ ops.order.received        → fi_subscriber: incr daily.orders, by channel
  ├─ ops.dispatch.handed_over  → fi_subscriber: incr daily.dispatches
  ├─ ops.dispatch.delayed      → fi_subscriber: incr daily.delays, raise alert if rate > threshold
  ├─ inv.stock.below_threshold → fi_subscriber: append to fi_alerts (OOS risks)
  ├─ cs.ticket.opened          → fi_subscriber: incr daily.tickets_opened
  ├─ cs.ticket.sla_breached    → fi_subscriber: incr daily.sla_breaches, alert
  ├─ ...                       
```

Subscribers are idempotent (events carry stable ids; an event re-delivered is a no-op via upsert keyed on event_id) and tolerant (a failure in one FI handler does not block others).

## The data model

```
fi_daily_snapshot
  id, tenant_id, date, payload JSONB, generated_at
  UNIQUE (tenant_id, date)
  — one row per tenant per business day; payload is the materialized snapshot

fi_kpi_orders_by_channel
  tenant_id, date, channel, orders_count, gross_revenue, returns_count
  PK (tenant_id, date, channel)

fi_kpi_invoices
  tenant_id, date, uploaded, extracted, reconciled, tally_pushed, failed, gross_payable
  PK (tenant_id, date)

fi_kpi_dispatches
  tenant_id, date, created, handed_over, delivered, delayed, cycle_time_hours_p50, cycle_time_hours_p95
  PK (tenant_id, date)

fi_kpi_tickets
  tenant_id, date, opened, resolved, escalated, sla_breached, csat_responses, csat_avg
  PK (tenant_id, date)

fi_kpi_inventory
  tenant_id, date, oos_skus, low_stock_skus, transfers_completed
  PK (tenant_id, date)

fi_alerts
  id, tenant_id, kind, severity, title, body, payload JSONB, raised_at, acknowledged_at, dismissed_at
  — every alert ever raised, with their lifecycle

fi_alert_definitions
  id, tenant_id, kind, condition_dsl, severity, cooldown_minutes, notify_channels JSONB
  — the rules that produce alerts
```

`fi_*` tables are read-mostly. The KPI tables are append/upsert by handlers; the snapshot is materialized by a nightly job.

## The daily snapshot

A scheduled job at end-of-business (per tenant timezone) reads the KPI tables for that day, computes deltas against last 7-day and 30-day averages, and writes `fi_daily_snapshot` with a payload like:

```json
{
  "date": "2026-06-19",
  "revenue": { "today": 412300, "vs_7d_avg_pct": +12.4, "vs_30d_avg_pct": +6.1 },
  "orders":  { "today": 184, "vs_7d_avg_pct": +9.2, "by_channel": {"shopify": 110, "amazon": 52, "flipkart": 22} },
  "dispatches": { "completed": 178, "delayed": 6, "cycle_p50": 18.5, "cycle_p95": 42.0 },
  "accounts": { "invoices_reconciled": 14, "tally_pushed": 12, "failures": 1, "pending_approvals_value": 246000 },
  "support": { "tickets_opened": 22, "tickets_resolved": 24, "sla_breaches": 0, "csat": 4.6 },
  "inventory": { "oos_skus": 3, "low_stock_skus": 11 },
  "alerts_today": 2,
  "top_problems": [
    { "kind": "tally_push_failed", "count": 1, "first_at": "2026-06-19T11:04Z" },
    { "kind": "dispatch_delayed", "count": 6, "sample": "ORD-29847" }
  ]
}
```

The snapshot is what the **Founder Snapshot** page renders. The page also offers WhatsApp delivery — a daily summary template fired to the founder's phone at 9am.

## Alerts

An alert is a workflow output, not magic. Alert definitions are rows in `fi_alert_definitions` with a condition expression evaluated against the KPI tables or events. Cooldowns prevent spam: an alert of the same kind cannot re-fire within `cooldown_minutes`.

Examples of seeded alerts (tenants can edit):

| Kind | Condition | Severity |
|---|---|---|
| `revenue_drop` | today revenue < 0.75 × 7d_avg, after 2pm tenant-local | high |
| `dispatch_delay_spike` | delayed_today / dispatches_today > 0.10 | medium |
| `tally_push_failures` | tally_pushed_failed > 3 in a day | medium |
| `oos_critical_skus` | any SKU in `critical_skus` config goes OOS | high |
| `sla_breach_spike` | sla_breaches_today > 5 | medium |
| `pending_approvals_aging` | any approval >24h in queue, amount > ₹2L | high |

When raised, an alert:
1. Inserts a row into `fi_alerts`.
2. Emits `fi.alert.raised` (so other subscribers — e.g., notification — react).
3. Routes through the Notification system to the channels in `notify_channels` (in-app, WhatsApp, email).

## The dashboard surface

The Founder page in the web UI renders:

1. **Snapshot strip** — today's revenue, orders, dispatches, open critical alerts. Four big tiles.
2. **Trend rows** — 30-day sparklines for the four KPIs above.
3. **Cross-module problems list** — top issues today across modules, grouped by kind.
4. **Approvals queue** — what needs the founder personally.
5. **Alerts log** — last 10 alerts with acknowledge / dismiss.

No filters, no date pickers, no chart customization. There is a "Yesterday" / "Last 7d" / "Last 30d" toggle and nothing else.

## The WhatsApp surface

A scheduled outbound template at 9am tenant-local:

```
Nyx Daily — Mon 19 Jun

Revenue:  ₹4.12L (+12% vs 7d)
Orders:   184  (Shopify 110, Amazon 52, Flipkart 22)
Dispatches: 178/184 ; 6 delayed
Accounts: 12 pushed to Tally, 1 failed
Support:  22 in / 24 out, CSAT 4.6
Alerts:   2 active

Reply MORE for top problems.
```

If founder replies `MORE`, the runtime renders the top-problems list as a follow-up message. `MORE` is a rule-based intent registered globally for the founder role; no LLM.

## Why we don't query module tables at view time

Two reasons:

1. **Decoupling.** The Accounts module can refactor `acc_invoices` freely as long as its events still publish the canonical facts. FI doesn't know or care about the schema.
2. **Read performance.** A founder loading the dashboard cannot wait for cross-module joins. Reading from pre-aggregated KPI rows is bounded and fast.

The cost: FI must be told about every new event a module starts emitting. We accept that — it's a one-line subscriber registration per new event type and forces conscious choice about what's KPI-worthy.

## Why this is interview-valuable

The pattern shown here — event-fed materialized aggregates serving a read-only synthesis layer — is the canonical small-scale CQRS shape without the ceremony of "CQRS". You can explain in an interview:

- The transactional path writes to module-owned tables.
- Domain events publish facts.
- A subscriber materializes read-optimised aggregates.
- The dashboard reads only from aggregates.
- This is a CQRS read model without a separate database or query bus.

That is a more honest and useful answer than "we use CQRS" in a system that has neither command-side nor projection complexity.

## Anti-goals

- No founder-personalised AI assistant in v1 ("Hey Nyx, why are orders down?"). Tempting; will be a poor experience without a long investment in retrieval-correct semantics. Defer.
- No KPI explorer / drill-through editor. Adding a new KPI requires a code change. That is the desired friction.
- No A/B testing of dashboard variants per founder.
- No "white-label" export of the snapshot to PDF in v1. Maybe in v2.

## Failure modes

- **Subscriber lag.** If FI handlers fall behind, snapshot data is stale. The snapshot job records the high-water event id consumed and refuses to publish if it's > N minutes old.
- **Lost events.** Mitigated by the `events` table being durable; replay re-feeds FI subscribers.
- **Alert storms.** Cooldowns + a global circuit breaker (more than X alerts in Y minutes → suppress new and notify operations).

FI is the simplest module in the platform and also the one the founder will see first. The contrast between simple internals and high signal value is, deliberately, the showpiece.
