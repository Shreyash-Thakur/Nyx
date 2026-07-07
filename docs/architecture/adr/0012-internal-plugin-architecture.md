# ADR 0012 — Plugin architecture: first-party registries, not a third-party plugin system

**Status:** Accepted
**Date:** 2026-07-08

## Context

"Make it a platform" invites the question: should Nyx load third-party
extensions — a plugin marketplace, dynamically loaded connector packages,
tenant-uploaded scripts? The vision already lists "a marketplace of
third-party plugins" as a non-goal, but the positive shape of extensibility
was never recorded as a decision. Meanwhile the codebase has grown its first
real registry (workflow actions), and more are specified (connectors, event
subscriptions, notification channels, intents).

## Decision

Nyx's plugin architecture is **registries with uniform contracts, populated
exclusively by first-party code in this repository**:

| Extension point | Contract |
|---|---|
| Business module | one folder under `app/modules/`, standard layout, `__init__.py` is the public interface, one router-registration line |
| Workflow action | name + handler + input/output JSON Schema + idempotency flag + retry policy |
| Event subscriber | `Callable[[Event, Session], None]`; tier declared; Tier 2 must be idempotent |
| Integration connector | `Connector` ABC (push/pull/receive); `auth_test` mandatory; registered by decorator |
| Notification channel | `send(rendered) -> result` under `core/notifications/channels/` |
| Conversation intent | pattern set per `expects` shape, in the curated intent registry |
| Alert definition | condition DSL rows in `fi_alert_definitions` (tenant-editable **data**, not code) |

Rules:

1. **Code extensions ship as PRs to this repo.** No runtime code loading, no
   entry-points discovery of external packages, no tenant-uploaded code, no
   signed-binary story. A third party who wants a connector contributes a PR.
2. **Data extensions are tenant-editable.** Workflow definitions, alert
   definitions, templates, config-store values, webhook subscriptions — these
   are rows, validated at save time, and are the intended per-tenant
   customization surface (P9: configuration over code).
3. **The escape hatch for external systems is webhooks, both directions** —
   HMAC-verified inbound mapped to declared event types; subscribed outbound
   on event types. External code integrates *with* Nyx, never runs *inside*
   Nyx.
4. **The acceptance test is the module recipe:** if adding a module requires
   edits outside its folder plus one router line, the platform is broken and
   gets fixed before features continue.

## Consequences

**Positive:** every extension point has one shape (find registry → implement
contract → register), reviewable and testable like all other code; no plugin
API to version, no sandboxing problem, no supply-chain surface; tenants still
get real customization through data.

**Negative:** extending Nyx requires a deploy for code-level extensions —
accepted; that friction is the security and quality gate. The registry
contracts become de-facto public APIs within the repo and need the same
change discipline as HTTP APIs.

## Rejected alternatives

**Third-party plugin marketplace / dynamic loading.** Rejected (vision
non-goal): sandboxing, signing, versioning, and support burden of a plugin
ecosystem is a product in itself, and plugin-quality failures would present as
Nyx failures.

**Tenant-uploaded Python/Lua "scripting" for custom logic.** Rejected — it is
`eval()` with extra steps; the restricted workflow-condition language exists
precisely to avoid this.

**No declared extension points ("just edit the code").** Rejected — that is
how the pre-platform codebase worked and why the reorg was needed; registries
are what keep the monolith modular.
