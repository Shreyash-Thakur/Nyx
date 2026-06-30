# ADR 0001 — Modular monolith over microservices

**Status:** Accepted
**Date:** 2026-06-19

## Context

Nyx is being positioned as a platform with five business modules (Accounts, Operations, Inventory, Customer Service, Founder Intelligence) and a substantial Core layer (RBAC, events, workflows, conversation, integrations). A reasonable instinct is to deploy each module as a separate service — it sounds "more architectural" and easier to talk about.

The audience is one of:
- a single-tenant SME deployment (10s of users), or
- a small multi-tenant SaaS (10s of tenants, 100s of users) in v2.

Team size is one engineer building the thing.

## Decision

Build Nyx as a **modular monolith**. One FastAPI application, one PostgreSQL database, one Redis. Modules are bounded by code (folders + `__init__.py` exports) rather than by network.

Inter-module communication is in-process via the event bus or via published service interfaces. Cross-module table reads are banned.

## Consequences

**Positive:**
- Local development is a single process (`uvicorn`) against SQLite. No service mesh, no distributed tracing setup, no inter-service auth.
- Transactions are real ACID transactions. Event publish + DB commit happen atomically.
- Refactoring across modules is a code change, not a coordinated multi-service deploy.
- Interview narrative is sharper: we deliberately rejected microservices.

**Negative:**
- Vertical scale only — one process. Acceptable for the target tenant size; would become a problem at 1000s of concurrent users.
- A bad commit can take down everything. Mitigated by tests and CI.
- "Module boundaries enforced by code review" is less rigorous than "boundaries enforced by HTTP" — needs the lint rule (see roadmap Week 8).

## Migration path

If the platform grows past what one process can handle, the modular layout was deliberately designed to make the split tractable:
1. Each module's public surface is its `__init__.py`. That surface becomes the HTTP interface.
2. The event bus already exists; swap the in-process implementation for Redis Streams or NATS without changing publishers/subscribers.
3. Each module already owns its own tables with prefixed names — split per-module databases would require only an Alembic per-module history, not a data migration.

We will not perform this migration on speculation. We will do it when a real scaling constraint forces it.

## Rejected alternatives

**Microservices from day one.** Rejected. Distributed-system bugs at our scale are losses, not investments. Single-engineer team would spend more time on inter-service plumbing than on business logic.

**Modular monolith with strict hexagonal architecture (ports/adapters everywhere).** Rejected. Over-abstracted for the size; the folder + `__init__.py` discipline is enough.

**A single "god" application with no module boundaries.** Rejected. That's what we're escaping from. The whole point of this redesign.
