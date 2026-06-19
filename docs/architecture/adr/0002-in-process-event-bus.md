# ADR 0002 — In-process event bus with Redis fanout, not Kafka

**Status:** Accepted
**Date:** 2026-06-19

## Context

Modules communicate by emitting domain events (`acc.invoice.reconciled`, `ops.dispatch.handed_over`, etc.). Founder Intelligence and the Audit log subscribe to every event. Some handlers must run synchronously (audit log write, workflow runner advancement); others can be slow (analytics aggregates, external webhooks).

We need a delivery mechanism that handles both shapes without dragging in operational weight we don't have the team for.

## Decision

Two-tier delivery:

1. **In-process synchronous bus** for handlers that must run within the same transaction as the publisher. Audit log write, workflow runner advancement, idempotent FI counter upserts.
2. **Redis-backed asynchronous fanout** for slower or fail-isolated handlers. External webhooks, notification fanout, anything calling network I/O.

Every published event is also persisted to an `events` table before fanout, giving us durable replay.

## Consequences

**Positive:**
- Same `bus.publish("acc.invoice.reconciled", payload)` API for the publisher — the bus picks the tier per subscriber.
- Audit and workflow advancement happen in the same transaction as the publishing action — no "the event fired but the row didn't commit" failure mode.
- Replay is trivial: read the `events` table, re-deliver to a single subscriber.
- Operationally cheap: no Kafka cluster, no Zookeeper, no schema registry.

**Negative:**
- A slow synchronous subscriber can stall the request path. Mitigation: explicit `@async_handler` decorator that forces a handler to the Redis tier; lint rule that flags handlers without it that do I/O.
- At-least-once delivery requires idempotent handlers. Documented contract.
- The events table grows forever. We add a partitioning/archival policy after 12 months of production data; until then growth is negligible.

## Why not Kafka

- Operational footprint: brokers, Zookeeper or KRaft, schema registry, monitoring, partition tuning. For our throughput this is comically over-provisioned.
- Persistence semantics duplicate what the `events` table already gives us.
- The interview pitch of "we use Kafka" lasts ten seconds; the follow-up "why do you need a partitioned log?" is the actual question, and the honest answer is "we don't yet."

## Why not Redis Streams as primary

We use Redis as the fanout transport but not as the source of truth. Streams have at-least-once delivery and good semantics, but durability and operability are weaker than Postgres for the kinds of inspection (ad-hoc SQL, joins on the log) we want for audit and replay.

## Why not an external event broker (NATS, RabbitMQ)

Same answer as Kafka but smaller. The marginal value over "in-proc + Redis + a table" is zero at our scale; the marginal operational cost is non-zero. Adopt only when constrained by a concrete need.

## Migration path

If we outgrow this — say, multi-process deployment for HA — the bus becomes a thin wrapper around Redis Pub/Sub or NATS. Publishers and subscribers don't change. The `events` table remains as the durable log regardless of transport.

## Rejected alternatives

**Direct method calls between modules.** Rejected — couples modules. Re-entrant explosions on schema changes.

**Postgres NOTIFY/LISTEN.** Considered. Rejected because the in-process path is faster for same-transaction needs and Redis is already in the stack for RQ.

**Building event sourcing as the primary store (entity state derived by replaying events).** Rejected. Adds enormous complexity for negligible benefit at our scale. Events are an *additive log*, not the source of truth for entity state. See ADR 0005.
