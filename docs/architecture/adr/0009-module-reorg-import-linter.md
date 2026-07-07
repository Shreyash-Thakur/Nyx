# ADR 0009 — Reorganize by module before the second module exists; enforce with import-linter

**Status:** Accepted
**Date:** 2026-07-08

## Context

The codebase is organized by technical layer (`app/models/`, `app/services/`,
`app/repositories/`, `app/api/v1/`). The architecture
(`01-platform-overview.md`, `03-folder-structure.md`) mandates organization by
bounded context (`app/modules/accounts/`, …) with the core platform under
`app/core/`. Today only Accounts exists, so the layer layout has not yet hurt —
but the moment a second module lands in the layer layout, invoice code and
inventory code interleave in the same folders and the boundary becomes
archaeology instead of structure.

Module boundaries are currently enforced by nothing but review culture.

## Decision

1. **Reorganize Accounts into `app/modules/accounts/` and platform code into
   `app/core/` subpackages *before* starting any second module.** The move-map
   in `03-folder-structure.md` is the plan; it is a file move + import rewrite,
   not a rewrite of logic.
2. **Table renames (`invoices` → `acc_invoices`, …) ship in the same milestone**
   as a rename-only Alembic migration (non-destructive `ALTER TABLE RENAME`),
   continuing the real chain (next free number after `0007`), not the
   illustrative numbering in the older docs.
3. **Add `import-linter` to CI in the same PR** with three contracts:
   - modules may not import from other modules (except published `__init__` interfaces),
   - `app/core/` may not import from `app/modules/`,
   - `app/api/v1/router.py` is the only file that imports module routers.
4. **The public API surface does not break.** Existing paths keep working;
   new canonical module-prefixed paths may be added as aliases.

## Consequences

**Positive:** the boundary exists in the filesystem and in CI before it is
stressed; adding module #2 is a folder copy; reviewers check a lint result,
not their memory.

**Negative:** one disruptive PR (large diff, mostly moves); git blame noise.
Mitigation: pure-move commits separated from any logic change; `git log
--follow` still works.

## Rejected alternatives

**Reorganize lazily when module #2 arrives.** Rejected — that PR would mix a
new module with a reorg, the worst possible review unit.

**Enforce boundaries with hexagonal/ports-and-adapters abstractions.**
Rejected (per `02-modules.md`): folder + `__init__.py` discipline + lint is
enough at this size.

**Skip the table prefixes.** Rejected — the prefix is what makes ownership
visible in `\dt` without opening code, and renaming later multiplies cost.
