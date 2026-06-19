# 07 — RBAC & Authorization

## What we are replacing

The current codebase has a three-value `UserRole` enum (`admin / accountant / viewer`) checked via FastAPI dependencies. That model collapses under the platform vision: an "accountant" in the Mumbai tenant has no business approving founder-level invoices in the Bangalore tenant; a warehouse staffer needs to complete tasks but not view financials; a customer service lead can escalate within CS but not push to Tally.

We replace it with a **role × permission × scope** model with optional **approval chains** layered on top. Same model serves web requests and WhatsApp messages.

## The model

```
                ┌────────────┐
                │   User     │
                └─────┬──────┘
                      │
                      │ user_roles
                      ▼
                ┌────────────┐
                │    Role    │ (e.g., "accounts_clerk", "ops_head", "founder")
                └─────┬──────┘
                      │
                      │ role_permissions
                      ▼
                ┌────────────┐
                │ Permission │ (action × resource_type)
                └────────────┘

  scope = filter applied per (user, role, resource): tenant, department, region, all
```

A check is: **"Can user U perform action A on resource R within scope S?"**

```
can(user, action="invoice.approve", resource=invoice_42, scope=auto) → bool
```

## Resources, actions, scopes

A **resource type** is a noun the platform protects: `invoice`, `vendor`, `order`, `dispatch`, `stock_transfer`, `ticket`, `workflow_definition`, `integration_config`, `user`, `role`, `report`. New modules register new resource types in their `__init__.py`.

An **action** is a verb: `view`, `create`, `update`, `delete`, `approve`, `push`, `assign`, `escalate`, `complete`. Not all actions apply to every resource. Modules declare allowed (resource_type, action) pairs.

A **permission** is `(resource_type, action)`. E.g., `("invoice", "approve")`. Stored as a row in `rbac_permissions`.

A **scope** narrows the permission to a subset of resources:

| Scope | Means | Example |
|---|---|---|
| `tenant` | All resources in the user's tenant | The default for most roles |
| `department:<id>` | Only resources tagged to that department | A CS lead seeing only CS tickets |
| `warehouse:<id>` | Only resources at that warehouse | A picker bound to Mumbai DC |
| `owned` | Only resources where the user is the creator/assignee | A clerk sees only their own drafts |
| `all` | Cross-tenant (platform admin only) | Internal support staff |

Scope is attached to the **user_role assignment**, not the role itself, because the same role at different scopes is the common case (e.g., one user is `ops_lead` for Mumbai AND `ops_viewer` for Bangalore).

## Tables

```
rbac_roles
  id, tenant_id, name, description, is_system (bool), created_at, updated_at
  UNIQUE (tenant_id, name)

rbac_permissions
  id, resource_type, action, description
  UNIQUE (resource_type, action)        — global; not per-tenant

rbac_role_permissions
  role_id, permission_id
  PK (role_id, permission_id)

rbac_user_roles
  id, user_id, role_id, scope_kind, scope_value, granted_by, granted_at, expires_at NULL
  INDEX (user_id), INDEX (role_id)

rbac_approval_chains
  id, tenant_id, name, resource_type, condition_dsl (JSONB)
  — declares which approval chain applies to which (resource, condition)

rbac_approval_steps
  id, chain_id, position (int), approver_kind (role|user|workflow_expr), approver_value, sla_hours
  — ordered steps; position 1 first

rbac_approval_requests
  id, tenant_id, chain_id, resource_type, resource_id, created_by, status, current_step,
  context JSONB, created_at, decided_at NULL
  — in-flight approvals; backed by tasks for human action
```

`rbac_permissions` is shared across tenants (the catalogue is part of the platform schema). `rbac_roles`, `rbac_user_roles`, and approval tables are tenant-scoped.

## System roles (seeded per tenant)

| Role | Indicative permissions |
|---|---|
| `platform_admin` | Everything in the tenant; only assignable by another platform_admin |
| `founder` | Read everything; approve at the highest threshold; manage roles |
| `finance_head` | All accounts actions; approve mid-tier invoices; configure Tally maps |
| `accounts_clerk` | invoice.create, invoice.view, invoice.verify; cannot push to Tally |
| `ops_head` | All operations actions; approve dispatch exceptions |
| `ops_executive` | order.view, dispatch.create, dispatch.update |
| `warehouse_staff` | task.complete (scoped to their warehouse); inv.transfer participate |
| `cs_head` | All CS actions; configure templates and SLAs |
| `cs_agent` | ticket.create/view/update/resolve (own + assigned) |
| `viewer` | Read-only across modules (configurable per module) |

System roles are seeded with the tenant. Custom roles can be created by `role.create` permission holders (usually founder + platform_admin).

## The check

The runtime check is one function, used identically by web and WhatsApp:

```python
# core/rbac/service.py
def can(
    user: User,
    action: str,                # "invoice.approve"
    resource: Any | None,        # invoice instance, optional for create
    *,
    tenant_id: UUID,             # always required
) -> Decision:
    # 1. system bypass: platform_admin in user's roles
    if has_role(user, "platform_admin", tenant_id):
        return Decision.allow()

    # 2. fetch user's roles in this tenant
    user_roles = load_user_roles(user, tenant_id)

    # 3. for each role, check permission and scope match
    resource_type, action_verb = action.split(".")
    for ur in user_roles:
        if not role_grants(ur.role, resource_type, action_verb):
            continue
        if scope_matches(ur, resource):
            return Decision.allow(matched_role=ur.role.name)

    return Decision.deny(reason="no_matching_role")
```

Return type is a `Decision` (not a bool) so the audit log can record *why* an action was allowed. This is the difference between a defensible audit and a checkbox audit.

## FastAPI integration

```python
# core/rbac/dependencies.py
def require(action: str, resource_loader: Callable | None = None):
    def dep(user: User = Depends(current_user), db: Session = Depends(get_db), ...):
        resource = resource_loader(...) if resource_loader else None
        decision = can(user, action, resource, tenant_id=user.tenant_id)
        if not decision.allowed:
            raise HTTPException(403, decision.reason)
        # bind decision to request scope for audit middleware
        request.state.rbac_decision = decision
        return user
    return dep
```

```python
@router.post("/invoices/{id}/approve",
             dependencies=[Depends(require("invoice.approve",
                                            resource_loader=load_invoice))])
def approve_invoice(...): ...
```

The same `can()` is called from the WhatsApp runtime before invoking the action mapped to an intent. There is one authorization path.

## Approval chains

Some actions require not one person's authority but a sequence: clerk submits → finance head approves → founder approves (if amount > ₹2L). A chain models this declaratively:

```
chain: "high_value_invoice"
resource_type: invoice
condition: amount > 200000
steps:
  1. role: finance_head, sla_hours: 4
  2. role: founder,      sla_hours: 24
```

When an action fires that's gated by a chain, the platform creates an `rbac_approval_request`, instantiates step 1's approver(s), and creates a `Task` for them. The chain is itself a workflow — the workflow engine wakes on the task completion event, advances to step 2, and on final approval emits `rbac.approval.granted`.

This means approval is **observable, auditable, resumable, and editable without redeploy** — properties the existing simple `role == admin` check cannot give.

## WhatsApp parity

A WhatsApp `APPROVE` reply traces:

```
inbound → runtime resolves principal → loads pending_prompt
  → prompt is bound to rbac_approval_request id
  → runtime calls can(user, "invoice.approve", invoice)
  → if allowed: approval_service.grant(request, by=user)
                  → emits rbac.approval.granted
                  → workflow advances
  → if denied: outbound "You don't have permission to approve this."
```

Same check, same outcome, same audit row. The interface differs; the authorization does not.

## Why not Postgres Row-Level Security (RLS)?

RLS is tempting for tenant isolation but we reject it because:

1. Our scoping is multi-dimensional (tenant × department × warehouse × ownership). Expressing all of that in RLS policies becomes opaque.
2. Application-layer scoping is easier to test, log, and explain in an interview.
3. RLS makes background jobs awkward — workers run as different roles or with `SET LOCAL` gymnastics.
4. The audit trail needs the human-readable *why* of an allow/deny, which RLS doesn't give.

We instead enforce tenant scoping in a single place — a SQLAlchemy event hook + a query-builder helper — backed by integration tests. This is the right trade-off until we have a customer demanding RLS for compliance reasons.

## Why not external authz (OPA, Cerbos)?

Same answer as workflow engines: external systems impose deployment and reasoning overhead disproportionate to current needs. The check fits in 50 lines of Python. The catalogue lives in DB rows. We can adopt OPA later by exporting permissions to Rego if a customer requires it — until then it's complexity tax.

## Migration from the current `UserRole` enum

| Current value | Maps to |
|---|---|
| `admin` | seed roles: `platform_admin` |
| `accountant` | seed role: `accounts_clerk` (plus, for some users, `finance_head`) |
| `viewer` | seed role: `viewer` |

Migration plan:
1. Add new RBAC tables (Alembic 0002).
2. Seed system roles per tenant.
3. Backfill `rbac_user_roles` from the existing `user.role` column.
4. Switch dependencies from `require_admin` etc. to `require("...")`.
5. After all routes migrated, drop `user.role` (or keep as a denormalised hint).

## Anti-goals

- **No ABAC engine.** We don't evaluate arbitrary attribute predicates per request. The scope kinds above are fixed.
- **No per-field permissions.** Granularity stops at (resource, action). UI hides fields; API does not enforce field-level redaction.
- **No tenant-tenant sharing.** Resources don't cross tenants. A platform_admin operates as one tenant or another, never both at once.
- **No "negative" permissions.** Roles are additive. If a role grants `invoice.view`, you cannot have another role that "removes" it. Compose roles narrowly instead.

## Test surface

- Unit: `can()` against a permission matrix.
- Integration: every route's `require(...)` declaration matches the catalogue; orphaned permissions and undeclared actions fail CI.
- E2E: WhatsApp `APPROVE` from an unauthorized phone is rejected with audit row.

The audit log table will, after this migration, record one row per allow/deny with the matched role, which is the single most useful artefact for an interviewer pressing on authorization design.
