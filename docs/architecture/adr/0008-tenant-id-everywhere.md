# ADR 0008 — Tenant-aware schema today; tenant onboarding deferred

**Status:** Accepted
**Date:** 2026-06-19

## Context

Nyx targets SMEs. Long-term we want multi-tenant SaaS. Short-term we ship single-tenant. The decision is whether to design for tenancy now or refactor later.

Refactoring tenancy into a system that wasn't designed for it is famously painful: every query, every API, every event, every test has to grow a tenant filter, and the missed ones are the security incidents.

## Decision

Make the **schema and access paths** tenant-aware from day one. Defer the **tenant onboarding flow and UI** to v2.

Concretely:
- `tenants` table exists from migration 0002.
- Every business-data table has `tenant_id UUID NOT NULL` with FK to `tenants`.
- A `default` tenant is seeded; all existing data backfills to it.
- Every request and worker job carries a tenant context (middleware on requests, explicit parameter on jobs).
- The query helper enforces tenant filters; a SQLAlchemy event hook fails any query missing one.
- The RBAC `can()` function requires `tenant_id` as a parameter.
- Events carry `tenant_id` in their schema.

What we do **not** build yet:
- Tenant signup flow.
- Tenant admin onboarding UI.
- Per-tenant subdomain routing.
- Per-tenant integration credential encryption keys (we use a single platform-wide DEK; per-tenant KEKs are a v2 hardening).
- Tenant-level billing / quotas.

## Why

1. **Refactoring tenancy in is the textbook architectural disaster.** The cost of a `tenant_id` column on every table today is approximately zero. The cost of adding it to a 12-month-old codebase is weeks plus security risk.
2. **The query and audit discipline is the same.** We want the "you can't write a query without scoping it" muscle memory whether or not multi-tenant ships in MVP.
3. **Interview narrative.** "Tenant-aware from day one with single-tenant deployment" is a more credible engineering story than "single-tenant; we'd add it later."

## Consequences

**Positive:**
- Migration to actual multi-tenant is days, not months.
- Tests can simulate cross-tenant access and assert denial — useful from day one.
- The events table partitions naturally by `tenant_id` later if scale demands it.

**Negative:**
- A small ongoing cost in every query and every model. Mitigated by helpers.
- The "default tenant" is a magic constant in single-tenant deployments. Mitigated by seeding it explicitly with a fixed UUID and documenting it.

## Specific patterns

### Table column
```sql
tenant_id UUID NOT NULL REFERENCES tenants(id),
```
Indexed when the table is queried by tenant + something else, which is almost always.

### Request middleware
```python
# core/tenants/middleware.py
class TenantContextMiddleware:
    async def __call__(self, request, call_next):
        # for MVP: derive from current user's tenant_id
        # for v2: derive from subdomain or header
        request.state.tenant_id = request.state.user.tenant_id
        with tenant_context(request.state.tenant_id):
            return await call_next(request)
```

### Query helper
```python
# core/db/queries.py
def tenant_query(model, db, *, tenant_id):
    return db.query(model).filter(model.tenant_id == tenant_id)
```

### SQLAlchemy event hook
```python
# core/db/safety.py
@event.listens_for(Engine, "before_execute")
def assert_tenant_scoped(conn, clauseelement, multiparams, params, execution_options):
    if is_tenant_scoped(clauseelement) and not has_tenant_filter(clauseelement):
        if settings.APP_ENV != "production":
            raise UnsafeQueryError(...)
        log_and_alert(...)
```

This hook is the lazy safety net. It catches the queries the helper didn't.

### Event schema
Every event has `tenant_id`. Subscribers receive it and scope their work accordingly.

## Migration path to actual multi-tenant

1. Build a tenant signup flow (web UI + API).
2. Per-tenant subdomain / header → tenant context middleware reads from that instead of the user.
3. Move the "default tenant" magic constant out as a feature-flagged single-tenant deployment mode.
4. Add per-tenant DEKs for integration credentials.
5. Add tenant-scoped admin UI (manage users, roles, integrations).

None of this requires schema changes — that's the entire point.

## Rejected alternatives

**Schema-per-tenant.** Rejected. Operational nightmare for migrations and connection pooling at the scales we target. Reconsidered only if a regulated tenant lands and demands hard isolation.

**Postgres RLS for tenancy.** Considered alongside RBAC (see ADR 0004). Rejected for the same reasons: opaque, hard to test, doesn't carry the human-readable scope reason into the audit log.

**Single-tenant only; refactor later.** Rejected per the disaster-textbook reasoning above. The marginal cost of tenancy-from-day-one is small; the rewrite later is enormous.
