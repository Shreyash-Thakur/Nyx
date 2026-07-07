# Nyx Architecture

Welcome. This directory is the source of truth for **what Nyx is**, **why it is shaped that way**, and **how a new contributor should reason about it**.

If you only read one thing, read [00-vision.md](00-vision.md).

## Read order

The documents are numbered in the order they are best read for the first time.

| # | Document | One-line purpose |
|---|---|---|
| 00 | [Vision & Principles](00-vision.md) | What Nyx is, who it serves, the ten principles, the explicit non-goals |
| 01 | [Platform Overview](01-platform-overview.md) | The three-layer architecture and inter-layer rules |
| 02 | [Modules & Bounded Contexts](02-modules.md) | What each module owns, emits, subscribes to, and refuses to do |
| 03 | [Folder Structure](03-folder-structure.md) | Backend + frontend target layout and the migration map from current |
| 04 | [Database Design](04-database.md) | Naming, tenant strategy, core tables, indexes, JSONB policy |
| 05 | [Event Bus](05-event-bus.md) | Two-tier delivery, schema, replay, ordering, anti-goals |
| 06 | [Workflow Engine](06-workflow-engine.md) | Triggers, conditions, actions, persistence, the runner |
| 07 | [RBAC & Authorization](07-rbac.md) | Roles × permissions × scopes, approval chains, web+WhatsApp parity |
| 08 | [Integration Framework](08-integrations.md) | Connector ABC, registry, per-tenant config, the Tally deep-dive |
| 09 | [Conversational Layer (WhatsApp)](09-conversational.md) | Webhook → intent → workflow, pending prompts, rule-first/LLM-fallback |
| 10 | [Founder Intelligence](10-founder-intelligence.md) | Event-fed aggregates, daily snapshot, founder-only synthesis |
| 11 | [Implementation Roadmap](11-roadmap.md) | 8-week plan with exit criteria, MVP scope, the cuts list |
| 12 | [Technical Debt & Risks](12-tech-debt-risks.md) | Known debt, accepted new debt, risks, mitigations, interview Q&A |

## Architecture Decision Records

Short, dated records of the major architectural choices.

| # | Title |
|---|---|
| [0001](adr/0001-modular-monolith-over-microservices.md) | Modular monolith over microservices |
| [0002](adr/0002-in-process-event-bus.md) | In-process event bus with Redis fanout, not Kafka |
| [0003](adr/0003-custom-workflow-engine.md) | Custom workflow engine, not Temporal/Camunda |
| [0004](adr/0004-app-layer-rbac-no-rls.md) | Application-layer RBAC, not Postgres RLS |
| [0005](adr/0005-single-postgres-no-cqrs.md) | Single Postgres with materialized aggregates, not CQRS+separate read DB |
| [0006](adr/0006-whatsapp-as-primary-ui.md) | WhatsApp as a primary UI, not a notification channel |
| [0007](adr/0007-rules-first-llm-fallback.md) | Rule-based intents in the action path; LLM only as fallback |
| [0008](adr/0008-tenant-id-everywhere.md) | Tenant-aware schema today; tenant onboarding deferred |
| [0009](adr/0009-module-reorg-import-linter.md) | Reorganize by module before the second module exists; enforce with import-linter |
| [0010](adr/0010-async-fanout-transactional-outbox.md) | Async event fan-out via a transactional outbox (TD-11) |
| [0011](adr/0011-domain-map-warehouse-crm.md) | Domain map revision: Warehouse split from Inventory; CRM as narrow customer registry |
| [0012](adr/0012-internal-plugin-architecture.md) | Plugin architecture: first-party registries, not a third-party plugin system |
| [0013](adr/0013-workflow-definitions-code-to-data.md) | Workflow definitions migrate from code to versioned data, in stages |

See [adr/README.md](adr/README.md) for the index in full.

> **Note (2026-07-08):** the top-level platform documents now live at the repo
> root: [`ARCHITECTURE.md`](../../ARCHITECTURE.md) (unifying system
> architecture), [`DOMAIN_MODEL.md`](../../DOMAIN_MODEL.md) (authoritative
> domain map — supersedes the five-module roster below per ADR-0011),
> [`ARCHITECTURE_REVIEW.md`](../../ARCHITECTURE_REVIEW.md),
> [`SECURITY_REVIEW.md`](../../SECURITY_REVIEW.md),
> [`OBSERVABILITY.md`](../../OBSERVABILITY.md), [`MVP.md`](../../MVP.md),
> [`IMPLEMENTATION_PLAYBOOK.md`](../../IMPLEMENTATION_PLAYBOOK.md).

## How to use this directory

- **New contributor onboarding:** read 00 → 01 → 02 → 03 in order. Then skim the rest as needed.
- **Building a module:** open 02 (your module), 03 (where files go), 05/06/07 (platform mechanisms you'll use).
- **Reviewing a PR:** check it against the rules in 02 (no cross-module imports) and the relevant ADR.
- **Preparing for an interview:** 00 sets the framing; 12 lists the pre-rehearsed answers; the ADRs are the "why didn't you use X" defenses.

## What this directory is not

- It is not the API reference. Generated OpenAPI lives in `/docs` of a running app.
- It is not the database migration history. That's Alembic.
- It is not a wiki. We don't add documents loosely. New doc = real architectural commitment.

## Update discipline

- Every architectural change ships with the doc update in the same PR.
- New module = new section in `02-modules.md`.
- New cross-cutting decision = new ADR.
- A doc that lies is worse than no doc. If you find one, fix it or open an issue.
