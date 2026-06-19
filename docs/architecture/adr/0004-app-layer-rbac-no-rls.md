# ADR 0004 — Application-layer RBAC, not Postgres Row-Level Security

**Status:** Accepted
**Date:** 2026-06-19

## Context

Nyx is tenant-aware (`tenant_id` on every business-data table) and has multi-dimensional scoping (tenant × department × warehouse × ownership). We must enforce that scoping consistently across web routes, WhatsApp inbound, background workers, and FI subscribers.

Two camps:
1. Enforce in the database via Postgres Row-Level Security (RLS) policies.
2. Enforce in the application layer (services + query helpers + middleware).

## Decision

Application-layer enforcement. RBAC checks go through a single `can(user, action, resource, *, tenant_id)` function. Tenant scoping is applied in a query-builder helper and a SQLAlchemy event hook that fails any query missing a tenant filter (when running with the helper).

## Why

1. **Scoping is multi-dimensional.** Tenant, department, warehouse, ownership. Expressing all of those as RLS policies becomes opaque and brittle.
2. **Decisions need to be observable.** A `Decision` object records *why* an action was allowed (matched role, matched scope). This goes into the audit log. RLS gives you a yes/no with no reason.
3. **Background jobs are first-class.** Workers don't authenticate as a user; they run as a system principal with a tenant context. RLS for system principals requires `SET LOCAL` gymnastics or running with a privileged role, both of which weaken the security guarantee.
4. **Testability.** Application-layer checks are unit-testable in plain Python. RLS policies require Postgres in the loop and are slower to iterate on.
5. **Interview narrative.** Walking through a `can()` function and an audit-friendly `Decision` is concrete. Pointing at a `policy` definition in SQL is less so.

## Consequences

**Positive:**
- One authorization path for web, WhatsApp, workers, FI. Same code, same audit.
- Decisions are loggable with reasons.
- Workers and FI subscribers don't need privileged DB roles.

**Negative:**
- A missed `tenant_id` filter in a hand-written query is a data leak. RLS would catch that.
  - Mitigation: a SQLAlchemy event hook that inspects every `SELECT`/`UPDATE`/`DELETE` on tenant-scoped tables and asserts a `tenant_id` filter, failing loudly in dev/test. In prod, log + alert + return empty.
  - Mitigation: integration tests that explicitly attempt cross-tenant access and expect denial.
- Compliance audits that ask "is row isolation enforced at the database layer?" require us to argue for the application enforcement as equivalent. Acceptable for an SME audience; revisit if a regulated tenant lands.

## Migration path to RLS (if ever)

If a customer requires database-layer enforcement:
1. Every tenant-scoped table already has a `tenant_id` column — RLS policies become straightforward.
2. The application's tenant context middleware already calls `SET LOCAL app.tenant_id = ...`; we'd use that in policy `USING (tenant_id = current_setting('app.tenant_id')::uuid)`.
3. Application checks stay (defense in depth); RLS becomes the floor.

This is a future option, not a current obligation.

## Rejected alternatives

**Postgres RLS as the primary boundary.** See above. Rejected for multi-dimensional scope and observability.

**OPA / Cerbos / external authorization service.** Adds a network hop on every check and a separate policy language. The check fits in 50 lines of Python. Adopt only if a customer requires it.

**Granular per-field authorization.** Out of scope. Granularity stops at (resource, action). UI hides fields; API does not field-mask.

**Negative permissions.** Out of scope. Roles are additive; compose narrowly instead.
