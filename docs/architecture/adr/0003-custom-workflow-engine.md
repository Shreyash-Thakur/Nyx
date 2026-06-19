# ADR 0003 — Custom workflow engine, not Temporal/Camunda

**Status:** Accepted
**Date:** 2026-06-19

## Context

Every module in Nyx has multi-step processes that span time, await human action, and need retries and visibility: invoice approval chains, dispatch tasks awaiting WhatsApp confirmations, SLA escalations, stock-transfer protocols. We need an engine that runs declarative workflow definitions and is reusable across modules.

The conventional answers are Temporal, Camunda, or Airflow. Each is excellent in its own niche.

## Decision

Build a small, embedded workflow engine inside the platform core. YAML definitions, a step runner, a restricted condition expression language, a registry of typed actions. Persistence in our existing Postgres.

## Why custom, briefly

- **Operational simplicity.** No separate cluster, no separate database, no separate UI to maintain. The engine ships with the app.
- **Right-sized.** Our requirements fit in <500 LOC for the runner. Temporal is built for orders of magnitude larger demands.
- **Owned.** The DSL is ours; we extend it for our action catalogue without depending on an upstream's release cadence.
- **Replaceable.** The runner is hidden behind an API. If we ever outgrow it, replacing it with Temporal is a backend swap, not a system rewrite.

## Consequences

**Positive:**
- Workflows live in the same DB as everything else. Joins, audit, transactional consistency just work.
- A workflow runs through the same event bus and RBAC as everything else; no impedance mismatch.
- Interviewable: we can walk through the runner code in 15 minutes.

**Negative:**
- We own the engine's bugs. Mitigation: keep it small, test heavily.
- Lacks features Temporal has out of the box: cron with timezone DST awareness, side-effect-deterministic replay, long-running activity heartbeats. We don't need any of these in MVP; we will add minimal versions as needed.

## Specific design constraints we adopt

- Conditions are a **safe restricted expression language**, not Python. AST allowlist: comparisons, AND/OR/NOT, attribute access on payload, references to tenant config, simple arithmetic. No function calls, no imports, no dunder access. This is the single most important constraint; arbitrary Python in a workflow definition makes the engine a footgun.
- Actions are a **registered catalogue**, not arbitrary code. Adding an action is a code change. This is deliberate friction.
- Workflows are **versioned**; running instances keep the version they started with.

## Migration path to Temporal (if ever)

A hypothetical migration:
1. The action registry becomes the Temporal activity registry — same function signatures.
2. YAML definitions get translated to Temporal workflows (manual or scripted).
3. The runner's "wait for event X" pattern maps to Temporal's signal/wait.
4. Existing workflow instances drain on the old runner; new ones land on Temporal.

This migration is straightforward because we kept the runner's responsibilities narrow and explicit. Not committing to it.

## Rejected alternatives

**Temporal.** Excellent product. Requires a separate cluster. Solves problems we don't have. Reconsider at a workload our current target tenants will never produce.

**Camunda / BPMN.** BPMN diagrams are powerful but the tooling assumes a BA/architect audience who designs them. We're not that audience. Workflows in our world are written by the engineer who owns the module.

**Airflow.** Built for data pipelines, not human-in-the-loop transactional workflows. Wrong tool.

**No workflow engine — orchestration inside services.** Rejected. That's what the current finance code mostly does; the redesign exists in part to fix it. Service-embedded orchestration metastasizes across modules and resists change.

**A no-code visual drag-and-drop builder.** Out of scope. A UI editor over the YAML is enough; full visual builder is its own product.
