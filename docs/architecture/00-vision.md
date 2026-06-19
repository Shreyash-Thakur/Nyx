# 00 — Vision & Principles

## What Nyx is

**Nyx is a Modular Internal Business Operations Platform for SMEs (20–500 employees).**

It is **not** a finance product. It is **not** an OCR tool. It is **not** a Tally wrapper. Those are features of one module. Nyx is the platform that makes those features — and many others — composable, configurable, and operable through a single coherent system.

A useful mental model:

> *Odoo + Monday + Airtable + a WhatsApp bot, sized and priced for an Indian SME, opinionated for D2C / eCommerce operations.*

Critically, Nyx is **not** competing with SAP, Oracle NetSuite, or Odoo Enterprise. Those products solve everything for everyone and are unaffordable, unusable, and over-configurable for a 20–500 person company. Nyx wins by being **smaller, opinionated, WhatsApp-native, and Tally-friendly**.

## Who it serves

Concretely, the target user is an Indian SME — typically D2C, retail, or light manufacturing — running on:
- Tally for accounting
- Shopify / Amazon / Flipkart for sales channels
- Gmail / Outlook for customer communication
- WhatsApp Business for warehouse, dispatch, vendor coordination
- A growing pile of Google Sheets and Excel files for everything in between

The pain is not "lack of software." The pain is **fragmentation**. The founder cannot see one truth. The warehouse cannot update inventory without opening five apps. The accountant manually posts Shopify orders into Tally. The customer service rep maintains a personal spreadsheet of escalations.

Nyx replaces the spreadsheets-and-WhatsApp-groups operating layer with a structured, auditable system that the **same people already using WhatsApp** can use without retraining.

## Why we are building it (placement context)

This project is also a portfolio artifact. The architecture is designed to demonstrate, in order of priority:

1. **System architecture** — modular monolith with clean boundaries, not a microservices cosplay.
2. **Workflow orchestration** — a reusable engine that drives every department's processes.
3. **Event-driven design** — modules communicate by emitting and consuming events, not by calling each other's services.
4. **RBAC and authorization** — non-trivial role + scope + approval-chain model that works identically across web and WhatsApp.
5. **Integration architecture** — a connector framework, not point-to-point integrations littered across modules.
6. **Data modeling** — normalized, auditable, multi-tenant-ready schema.
7. **Operational pragmatism** — chooses boring tech (Postgres, Redis, RQ) deliberately and explains why Kafka/Mongo/microservices were rejected.

An interviewer should be able to walk through this codebase and see a coherent platform, not a bag of features.

## Core principles

### P1 — Platform first, modules second
Every module (Accounts, Operations, Inventory, Customer Service, Founder Intelligence) consumes the **same** primitives: users, RBAC, audit, notifications, workflows, events, integrations. A module is just a bounded context that owns its tables and exposes its operations via the platform's mechanisms.

### P2 — Modular monolith. No microservices.
One deployable. One database. Clean code boundaries via folders and explicit interfaces. Inter-module communication via events or service interfaces — never via cross-module raw table reads. Microservices would buy nothing here except deployment pain and distributed-system bugs.

### P3 — Events are the connective tissue
Modules emit domain events. Other modules subscribe. The Founder Intelligence layer is just a privileged subscriber. The audit log is just a persistent subscriber. This is the single most important architectural lever — it lets us add modules without touching existing ones.

### P4 — Workflows are first-class data
A workflow is not Python code embedded in a service. It is a **declarative definition** (trigger → conditions → actions) persisted in the database, instantiated per event, and progressed by a runner. Workflows can be edited without redeploying.

### P5 — WhatsApp is a UI, not an integration
Most ERPs treat WhatsApp as a notification channel. Nyx treats it as a **primary interface**. A warehouse picker should never need to log into the dashboard. The conversation layer is a UI that maps inbound messages to the same workflow engine the web UI uses.

### P6 — Deterministic actions are rule-based. AI is for fuzzy inputs only.
`DONE`, `APPROVE`, `REJECT`, `HELP`, `ISSUE` are regex/keyword matches. They must be fast, free, and reliable. LLMs are used only for free-text classification ("the box arrived torn"), summarization, and founder-facing insight generation — never in the action path.

### P7 — Multi-tenant ready, single-tenant today
Every table carries a `tenant_id`. Every query is scoped by it. We do not implement tenant onboarding yet, but the schema and access paths are tenant-aware so a future "Nyx for ACME Co." takes weeks, not a rewrite.

### P8 — Auditability is non-negotiable
Every state change in every module emits an event and writes an audit row. No exceptions. This is what makes Nyx defensible as a system of record vs. a spreadsheet replacement.

### P9 — Configuration over code
Tally XML mappings, voucher types, ledger names, approval thresholds, SLA windows, notification templates — all in the database, edited via UI, not in Python. A new client gets onboarded by editing config, not by forking code.

### P10 — Boring tech, deliberately
FastAPI, PostgreSQL, Redis, RQ, Next.js. No Kafka, no Mongo, no microservices, no event-sourcing-as-primary-store, no Kubernetes. Each "no" is a documented trade-off (see `adr/`). Boring tech ships and gets hired.

## Non-goals (explicit)

We will **not** build, now or in any near roadmap horizon:

- HRMS, payroll, attendance
- CRM (lead capture, sales pipeline, marketing automation)
- A general-purpose form builder
- "AI agents" that autonomously run business processes
- ChatGPT-in-a-textbox features
- A mobile app (WhatsApp is the mobile interface)
- An internal scripting language richer than the workflow DSL
- A multi-region / multi-DC deployment story
- Realtime collaborative editing
- A marketplace of third-party plugins

Every one of these is a credible feature for an ERP. Every one of them is also how this project dies if we say yes.

## Definition of done for the platform layer (Phase 1)

A reviewer should be able to verify that:

1. A new module can be added by creating one folder under `app/modules/`, registering its events, workflows, and routes — without touching any other module.
2. Any state change in any module emits an event that is visible in an `events` table and consumed by the audit log.
3. A workflow definition (trigger + conditions + actions) can be added via API call and immediately fires on the next matching event.
4. Permissions can be granted at role × module × action × scope granularity, and the same check applies to a web request and a WhatsApp message.
5. A WhatsApp inbound `DONE` against an open task completes that task, advances its workflow, and emits the same events as a UI click would.
6. The Founder dashboard reads only from materialized aggregates, never from module-private tables.

If any of these is false, the platform layer is not done — regardless of how shiny individual module features look.

## Why this scope is the right one for a placement project

A finance-only product invites a narrow conversation: "how accurate is your OCR?" That is a research question, not an engineering one, and you will lose to anyone with a Vision API key.

A platform invites the conversations interviewers actually want:

- "How do you keep two modules from creating a circular dependency?"
- "How does an event get from one module to another without coupling them?"
- "How does the same permission check apply to a WhatsApp message and an HTTP request?"
- "What happens if the Tally connector is down for two hours?"
- "Walk me through what happens when a customer service rep replies `ESCALATE` to a WhatsApp message."

These are the questions where senior backend engineers are made. The scope of Nyx is deliberately chosen so that answering them well is the natural outcome of building the thing.
