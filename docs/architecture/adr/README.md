# Architecture Decision Records

Short, dated records of the major architectural choices behind Nyx. Each one captures **what** we decided, **why**, and **what we rejected** — in enough detail to defend the choice in code review or an interview.

Format: light Michael Nygard ADR — Context → Decision → Consequences → Rejected alternatives.

## Index

| # | Title | Status |
|---|---|---|
| [0001](0001-modular-monolith-over-microservices.md) | Modular monolith over microservices | Accepted |
| [0002](0002-in-process-event-bus.md) | In-process event bus with Redis fanout, not Kafka | Accepted |
| [0003](0003-custom-workflow-engine.md) | Custom workflow engine, not Temporal/Camunda | Accepted |
| [0004](0004-app-layer-rbac-no-rls.md) | Application-layer RBAC, not Postgres RLS | Accepted |
| [0005](0005-single-postgres-no-cqrs.md) | Single Postgres with materialized aggregates, not CQRS+separate read DB | Accepted |
| [0006](0006-whatsapp-as-primary-ui.md) | WhatsApp as a primary UI, not a notification channel | Accepted |
| [0007](0007-rules-first-llm-fallback.md) | Rule-based intents in the action path; LLM only as fallback for fuzzy text | Accepted |
| [0008](0008-tenant-id-everywhere.md) | Tenant-aware schema today; tenant onboarding deferred | Accepted |
| [0009](0009-module-reorg-import-linter.md) | Reorganize by module before the second module exists; enforce with import-linter | Accepted |
| [0010](0010-async-fanout-transactional-outbox.md) | Async event fan-out via a transactional outbox (TD-11) | Accepted |
| [0011](0011-domain-map-warehouse-crm.md) | Domain map revision: Warehouse split from Inventory; CRM as narrow customer registry | Accepted |
| [0012](0012-internal-plugin-architecture.md) | Plugin architecture: first-party registries, not a third-party plugin system | Accepted |
| [0013](0013-workflow-definitions-code-to-data.md) | Workflow definitions migrate from code to versioned data, in stages | Accepted |
