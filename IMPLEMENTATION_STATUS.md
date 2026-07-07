# NYX — Implementation Status

**Date:** 2026-07-08 · **Audited by:** Lead Backend Engineer, verified from
code (not from docs). Baseline commit: `ea4560e`. Backend suite: **107
passing** (`pytest`, in-memory SQLite, ~34 s), verified by running it.

**Current position: pre-M1.** Phases 0 (the connected Accounts pipeline) is
complete; Phase 1 of `IMPLEMENTATION_PLAYBOOK.md` has not started. The next
milestone is **M1 — Async & atomic (Phase 1: Platform correctness)**.

## Playbook phase status (verified from code)

| Phase | Status | Evidence |
|---|---|---|
| P0 — Connected Accounts pipeline | ✅ | upload→OCR→verify gate→approval gate→reconcile→Tally dry-run all in code; 107 tests incl. HTTP e2e (`test_e2e_pipeline.py`) |
| P1 — Platform correctness (M1) | ❌ (one item ⚠) | detail below |
| P2 — Boundary milestone (M2) | ❌ | code still layer-organized (`app/services/…`); no `app/modules/`; no import-linter; `can()` is `(user, permission) -> bool` (`app/core/rbac.py:62`) |
| P3 — Workflows as data (M3/V1) | ❌ | one Python-registered definition; conditions are dict equals/not_equals/in (`app/core/workflow/engine.py:60`); no `workflow_definitions` table; no connector framework |
| P4–P6 (V1.5) | ❌ | no tasks, conversation runtime, WhatsApp, Inventory/Warehouse, FI |
| P7+ (V2) | ❌ | — |

## Phase 1 items, exactly

| Item | Status | Verified detail |
|---|---|---|
| 1. Transactional outbox + Tier-2 (ADR-0010; issues #1–#3) | ❌ | `bus.py` runs every handler synchronously in the publishing tx and **swallows exceptions** (`bus.py:72–82`) — audit is best-effort (SEC-2/review P0-1); no outbox/DLQ tables; `events` has no correlation/causation columns (`models/event.py`); no replay CLI; no depth cap |
| 2. Observability for the async tier (issue #11) | ❌ | `/health` exists (queue-aware, `main.py:91`); no `/health/ready`; no outbox metrics; workflow failure sets `status=failed` silently — no alert |
| 3. Auth lifecycle hardening (issues #4–#5) | ❌ | `refresh_tokens()` verifies signature only — no jti, no store, no rotation-revocation (`auth_service.py:90`); no email verification (flag exists, never enforced), no password reset; dev-default secrets accepted in any env (`config.py:30,44`); access TTL 30 min |
| 4. Small fixes (issues #6–#9) | ❌ | dedup is check-then-insert, no unique index (`invoice_service.py:53`); upload commits ≥2× (TD-5, `invoice_service.py:101,110`); `httpx` duplicated / `pypdf2` — actually **pypdf2 already absent**, but `pydantic` listed twice (`requirements.txt`); no security-headers middleware; CORS `*` outside production |
| 5. Postgres CI (issue #10) | ⚠ | CI **already** runs `alembic upgrade head` + full suite on Postgres 16 + Redis (`.github/workflows/ci.yml`) — missing: downgrade round-trip, SQLite (zero-dep) job, and any lint step |

## Tooling gaps against the mission's quality gates

- **ruff:** not installed, no config anywhere.
- **mypy:** not installed, no config.
- Both will be introduced in M1's quality pass (ruff repo-wide; mypy scoped
  pragmatically), since "lint clean / type-safe" is part of the stop
  condition.

## Facts the M1 implementation must respect (from code)

- Inline queue runs jobs synchronously in-process (`workers/queue.py`);
  tests rely on side effects (e.g. notifications) being visible immediately
  after a request — Tier-2 delivery must drain post-commit in inline mode to
  keep the 107 tests green.
- Tests build schema via `Base.metadata.create_all`, not Alembic
  (`tests/conftest.py:79`) — new models must be importable from
  `app.models` for tables to exist in tests; migrations are exercised only
  in CI.
- Migration convention: short revision ids (`"0008"` next,
  `down_revision="0007"`), Postgres-only enum blocks are no-ops on SQLite.
- Workflow advancement is **not** an event subscriber today (it runs via
  explicit queue jobs), so ADR-0010's "workflow advancement = Tier 1" has no
  code impact in M1.
- `slowapi` limiter state is process-global; tests reset it via fixture.

## M1 execution plan (per playbook order)

1. Event-bus tiering + transactional outbox + correlation (Agent A, worktree;
   migration `0008`).
2. Auth hardening (Agent B, worktree, disjoint files; migration `0009`).
3. Coordinator: merge A then B; small-fixes batch + CI round-trip + ruff/mypy
   introduction; docs (`STATUS.md`, `WORKLOG.md`, this file).

Stop after M1 per the stop condition.
