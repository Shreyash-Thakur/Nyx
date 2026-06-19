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
