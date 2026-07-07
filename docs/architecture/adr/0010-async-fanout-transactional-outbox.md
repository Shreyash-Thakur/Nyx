# ADR 0010 — Async event fan-out via a transactional outbox (TD-11)

**Status:** Accepted
**Date:** 2026-07-08
**Extends:** ADR-0002 (in-process event bus with Redis fanout)

## Context

ADR-0002 specified two delivery tiers, but the implementation shipped Tier 1
only: **every subscriber runs synchronously inside the publishing
transaction**. That was the correct first step (simple, exactly-once, easy to
test) and it is now the last structural gap in the event architecture (TD-11):

- A slow subscriber adds its latency to the producing request.
- A failing subscriber rolls back the business write — correct for the audit
  writer, wrong for a notification renderer.
- Adding Founder Intelligence aggregates or outbound webhooks on this model
  would couple dashboard math and third-party endpoints to invoice commits.

## Decision

Implement Tier 2 as a **transactional outbox**:

1. `bus.publish()` continues to persist the event and run Tier 1 handlers
   (audit writer, workflow advancement) in the publisher's transaction —
   unchanged API, unchanged guarantees.
2. In the **same transaction**, one `event_outbox` row is written per
   registered Tier 2 subscriber: `(event_id, handler_name, status,
   attempt_count, next_attempt_at)`.
3. A **fanout worker** drains the outbox after commit: enqueues one queue job
   per row (RQ on Redis; the inline queue in dev), which runs the handler in
   its own session/transaction and marks the row delivered.
4. **Retries** with exponential backoff per row; after exhaustion the row
   moves to a dead-letter state with error + traceback, alertable and
   **replayable by an operator**. Poison events are parked for a human, never
   auto-dropped and never auto-skipped.
5. **Handler contract:** every Tier 2 handler must be idempotent (natural
   idempotency or an `(event_id, handler_name)` dedup record). This is a
   review-blocking requirement, not advice.
6. **Ordering:** per-subject only (same aggregate → processed in publish
   order, via subject-hashed queue buckets); no global ordering, deliberately.
7. **Tier assignment default:** when in doubt, Tier 2. Tier 1 is reserved for
   handlers that must be atomic with the business write, take < ~5 ms, and do
   no I/O beyond Postgres. The current subscribers re-sort as: audit → Tier 1;
   notifications → Tier 2; workflow advancement → Tier 1 (state-machine
   consistency on read).

## Why an outbox and not "publish to Redis after commit"

Publish-after-commit has an unclosable crash window: commit succeeds, process
dies, event never fans out, and nothing knows. The outbox rows commit with the
event, so the worst crash outcome is *delayed* delivery, never *lost*
delivery. This is the standard answer and we take it unmodified.

## Consequences

**Positive:** producer latency independent of subscriber count/health; failure
isolation per subscriber; the DLQ + replay path gives operations a story for
"the notification handler was broken for 2 hours."

**Negative:** eventual consistency for Tier 2 effects (seconds) — accepted and
already assumed by the FI design; one more moving part (fanout worker) —
mitigated by the inline queue running the same code path in dev/tests; the
outbox table needs retention (delivered rows purged after N days).

## Rejected alternatives

**Kafka / NATS / RabbitMQ.** Re-rejected per ADR-0002; nothing changed.

**Redis Streams as the durable log.** Rejected — Postgres already is the
durable log; Redis remains transport only.

**Best-effort async (fire tasks post-commit without an outbox).** Rejected —
silent event loss under crash is the one failure mode an audit-first platform
cannot accept.

**Keeping everything synchronous.** Rejected — correct yesterday, but blocks
FI, webhooks, and every latency SLO the moment a second module emits events.
