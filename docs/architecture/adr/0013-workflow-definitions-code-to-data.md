# ADR 0013 — Workflow definitions migrate from code to versioned data, in stages

**Status:** Accepted
**Date:** 2026-07-08
**Extends:** ADR-0003 (custom workflow engine)

## Context

ADR-0003 committed to a custom embedded engine; principles P4/P9 commit to
workflows being *data* an admin edits without redeploy. The engine shipped
(durable instances, restricted conditions, action registry, retry/recovery)
but its one definition (`invoice_post_extraction`) is **registered in Python**,
and the full spec in `06-workflow-engine.md` (YAML DSL, waits, timers, task
integration, test harness) is substantially ahead of the code.

Jumping straight to the full spec in one push is the riskiest possible move on
the platform's most load-bearing component — the engine is the *only*
post-extraction execution path for real invoices today.

## Decision

Evolve in four shippable stages, each keeping the previous stage's tests
green (detail: `ARCHITECTURE.md` §5):

- **Stage 0 [BUILT]** — code-registered definitions; durable instances;
  restricted conditions; action registry; retry/recovery.
- **Stage 1** — `workflow_definitions` table (YAML canonical + parsed JSONB,
  **versioned and immutable**; instances pin their version); save-time
  validation (conditions parse, actions exist, params match action schemas);
  the Stage 0 Python definition becomes seed data; publish/retire via API.
- **Stage 2** — `wait_for_event` / `wait_for_duration` primitives with
  `wait_descriptor` wakeup (event-driven, no polling); the generic Task
  entity; approval chains expressed as workflows with wait-for-task steps
  (no separate approval engine, ever).
- **Stage 3** — the standard action catalogue; `WorkflowTestRunner` harness
  (in-memory bus, virtual clock, stubbed actions) so definitions are testable
  before publish; read-only graph visualizer.

Invariants held at every stage: definitions are versioned and never edited in
place; conditions stay in the restricted expression language; the action
registry remains the only extensibility point; no Turing-complete DSL, no
LLM-decided branching, no auto-retry of parked instances.

## Consequences

**Positive:** each stage is independently valuable (Stage 1 alone delivers
the no-redeploy edit story); the load-bearing pipeline is never rewritten,
only re-expressed; the Temporal escape hatch from ADR-0003 stays open because
the contract surface (definitions, instances, actions, conditions) is
unchanged by the staging.

**Negative:** the interim state has *two* definition sources (seeded rows
that originated in code) — mitigated by making the seed the only code path
that writes definitions, and deleting the Python registration in the same PR
that seeds it. Save-time validation becomes a compatibility surface: actions'
input schemas can't change carelessly once definitions reference them.

## Rejected alternatives

**Ship the full 06-spec in one milestone.** Rejected — highest-risk change on
the highest-risk component, unreviewable diff, and Stages 2–3 have no consumer
until Tasks and the conversation runtime exist.

**Keep definitions in code permanently ("it's simpler").** Rejected — it
silently repeals P4/P9, makes every threshold change a deploy, and forfeits
the tenant-customization story the platform is premised on.

**Adopt Temporal now instead of staging.** Re-rejected per ADR-0003; nothing
about the staging changes that calculus.
