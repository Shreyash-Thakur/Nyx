# ADR 0005 — Single Postgres with materialized aggregates, not CQRS+separate read DB

**Status:** Accepted
**Date:** 2026-06-19

## Context

Founder Intelligence reads from cross-module aggregates. A natural reach is a separate read database with command/query separation, possibly fed by an event-sourced write side. This is "the right shape" in textbooks for analytical-vs-transactional separation.

## Decision

One Postgres. Transactional tables live alongside Founder Intelligence aggregate tables (`fi_*`). Aggregates are maintained by event subscribers — write-then-fanout, no separate read store, no separate command/query buses.

We get the **shape** of CQRS (write side mutates module tables; read side projects to FI tables; events are the propagation) without the **plumbing** of CQRS (separate buses, separate stores, deserialization, eventual consistency tooling).

## Why

1. **Workload size.** Target tenants generate tens to low thousands of events per day. A single Postgres on modest hardware handles this with margin to spare. There is no contention worth solving.
2. **Operational simplicity.** One database to back up, one to restore, one to upgrade, one to monitor.
3. **Transactional propagation.** The "outbox-then-publish" pattern is implemented as `INSERT into events; then bus.fanout(event_id)`. Same transaction commits both the module mutation and the event row. This avoids the classic "the operation happened but no event fired" bug at the cost of nothing.
4. **Joins are still possible.** If FI ever needs to enrich a read with module data, it can join — though we discourage it for the decoupling reason in `10-founder-intelligence.md`.

## Consequences

**Positive:**
- FI is just another module. Same DB, same migrations, same backup story.
- No "is the read store stale?" anxiety beyond seconds of subscriber lag.
- Snapshots and KPI queries are SQL on indexed tables. Fast and explainable.

**Negative:**
- FI reads share resources with transactional writes. Mitigation: read queries are narrow, indexed, and bounded; we monitor and add a read replica if it ever matters.
- We don't get free time-travel "what did the state look like 30 days ago" — only what we computed and stored. Acceptable; that's what the daily snapshots are for.

## Why not event sourcing as primary

Event sourcing means: entity state is derived by replaying events; the events table is the source of truth.

Rejected:
- Significant complexity in command handlers, projections, snapshots, migrations of event schemas.
- Most of our entities (invoice, order, ticket) have natural, well-understood relational shapes; forcing them through an event-sourced lens adds friction for zero gain.
- The interview narrative "we event-source everything" is unhelpful if pressed: most candidates can't defend it past slogan level. Better to defend a narrower claim — "events are an additive log subscribed to by FI and audit" — which we can.

## What we keep from CQRS thinking

- **Write side and read side are conceptually distinct.** Modules write; FI reads from its own materialized projections.
- **Eventual consistency is acceptable for reads.** FI lags transactions by seconds; the founder dashboard does not need transactional consistency with every action.
- **Replay is possible.** Re-running subscribers over the `events` table rebuilds aggregates from scratch.

These are the load-bearing ideas. The infrastructure (separate DB, separate query bus, event sourcing) is not what makes them work.

## Migration path

If FI ever justifies its own database, the path is:
1. Create read DB.
2. Subscribers write to both (dual-write window).
3. Read traffic switches to the new DB.
4. Stop writing to FI tables in the primary; drop them.

Days of work, not weeks. Not on the radar.

## Rejected alternatives

**Separate analytics warehouse (BigQuery / Snowflake) from day one.** Rejected as overkill. If founders ever want analyst-level BI, add a CDC pipeline to a warehouse then. The dashboard does not need it.

**Materialized views in Postgres instead of subscriber-maintained tables.** Considered. Subscribers are more flexible (event-driven update granularity; can compute things SQL cannot easily, like p95s) and align with the event-bus discipline we want elsewhere.
