# 08 — Integration Framework

The Integration Framework is the core capability that every business module relies on to talk to the outside world. Accounts pushes to Tally. Operations pulls orders from Shopify, Amazon, Flipkart. Customer Service sends and receives email through Gmail or Outlook. The Conversation Runtime drives WhatsApp through the WhatsApp Cloud API. None of those modules contain integration-specific code. They all go through one entry point:

```python
integrations.get("tally", tenant_id).push(invoice_payload)
```

That single line is the contract. Everything in this document exists to make that line work — uniformly, swappably per tenant, fault-isolated from the calling module, and observable in operations.

## 1. Goal

The Integration Framework must satisfy five properties, in priority order:

1. **Common interface.** Every connector implements the same Python ABC. A module never knows whether it is talking to Shopify or Flipkart; it asks the registry for a connector by capability and calls a typed method.
2. **Swappable per tenant.** Tenant A may use Tally HTTP-XML at `192.168.1.10:9000`. Tenant B may use Tally ODBC. Tenant C may not use Tally at all. The framework resolves the connector instance by `(tenant_id, connector_id, instance_name)`; the module is unchanged.
3. **Fault-isolated.** A 30-second Tally timeout cannot block an invoice transaction. A Shopify rate-limit error cannot stall the order ingestion of an unrelated tenant. All external I/O happens in workers or behind circuit breakers on the sync path.
4. **Observable.** Every call records latency, status, payload size, and last error. The `Settings → Integrations → Health` page reads from one table and shows the truth without any per-connector special casing.
5. **Module-clean.** Integration logic never leaks into a module. If a module has `import xml.etree.ElementTree`, the framework has failed. If a module has `httpx.post("https://...")`, the framework has failed.

Anti-property, equally important: **the framework is not a general iPaaS.** We do not build a no-code arbitrary-SaaS integration builder. We build a tightly-curated set of connectors for the integrations Indian SMEs actually use. The benefit of a closed connector set is enormous — we control versioning, auth, and error semantics for each.

## 2. Connector taxonomy

Every connector is exactly one of three kinds. The kind determines the lifecycle and the methods the connector must implement.

| Kind | Direction | Trigger | Examples |
|---|---|---|---|
| **Push** | Nyx → external | Synchronous call from a worker | Tally HTTP-XML, Gmail send, WhatsApp send, generic outbound webhook |
| **Pull** | external → Nyx | Scheduler-driven poll | Shopify orders, Amazon orders, Flipkart orders, Google Sheets read |
| **Receive** | external → Nyx | External system POSTs / mailbox event | WhatsApp inbound webhook, Shopify order webhook, generic inbound webhook, email IMAP poll (modeled as receive even though it polls) |

A few clarifications on the boundary cases:

- **IMAP poll-as-receive.** IMAP technically requires us to poll, but semantically the mailbox is the source of truth and we react to whatever arrives. Modeling it as a *receive* connector keeps the conversation/CS code symmetric with the WhatsApp webhook path. The fact that we poll is an implementation detail of the connector.
- **Webhooks-as-pull vs receive.** Outbound webhooks (Nyx POSTing to a customer URL on an event) are *push*. Inbound webhooks (an external service POSTing to us) are *receive*. The verb is "from Nyx's point of view."
- **Tally is not pull.** We never read Tally back. Tally is the system of record for ledger; Nyx is the system of action. The connector is push-only.

### Connector inventory (initial)

| Connector ID | Kind | Module consumers | Notes |
|---|---|---|---|
| `tally` | push | accounts | XML-HTTP server; tenant-mapped voucher/ledger config |
| `gmail_send` | push | customer_service, notifications | OAuth2; per-user or per-tenant sender |
| `outlook_send` | push | customer_service, notifications | OAuth2; Microsoft 365 |
| `whatsapp` | push + receive | conversation, notifications | Meta Cloud API; one token per WABA |
| `webhook_out` | push | any (via events) | Generic HMAC-signed outbound POST |
| `shopify_orders` | pull | operations | REST + GraphQL; cursor-based since token |
| `amazon_orders` | pull | operations | SP-API; LWA refresh tokens |
| `flipkart_orders` | pull | operations | Seller API |
| `sheets_read` | pull | any (via workflow action) | Google Sheets v4 |
| `gmail_inbound` | receive | customer_service | IMAP poll OR Gmail push notifications |
| `outlook_inbound` | receive | customer_service | IMAP poll OR Graph subscription |
| `shopify_webhook` | receive | operations | Order create/update/cancel webhooks |
| `whatsapp_webhook` | receive | conversation | Meta Cloud API webhook (paired with `whatsapp` push) |
| `webhook_in` | receive | any (via workflow trigger) | Generic HMAC-verified inbound POST |

This list is the boundary of v1. Adding a connector is a recipe (Section 5); inventing a 14th category is not.

## 3. The Connector ABC

Every connector subclasses `Connector` and one of `PushConnector`, `PullConnector`, `ReceiveConnector`. The ABC is intentionally small.

```python
# app/core/integrations/base.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Iterable, Mapping
from uuid import UUID


class ConnectorKind(str, Enum):
    PUSH = "push"
    PULL = "pull"
    RECEIVE = "receive"


@dataclass(frozen=True)
class ConnectorContext:
    """Per-call context. Built by the registry from integration_configs."""
    tenant_id: UUID
    connector_id: str
    instance_name: str           # "default", "warehouse_a", etc.
    config: Mapping[str, Any]    # decrypted, merged config + credentials
    correlation_id: str          # for tracing across modules and workers


@dataclass(frozen=True)
class HealthResult:
    ok: bool
    latency_ms: int
    error: str | None = None
    extra: Mapping[str, Any] | None = None


class Connector(ABC):
    """Root ABC. A concrete class registers itself by id + kind."""
    id: str                       # e.g. "tally", "shopify_orders"
    kind: ConnectorKind
    version: str = "1"            # connector implementation version

    def __init__(self, ctx: ConnectorContext):
        self.ctx = ctx

    @abstractmethod
    def auth_test(self) -> HealthResult:
        """Cheap call that verifies credentials + reachability.
        Used by health checks and by the Settings UI 'Test connection' button.
        Must NOT mutate any external state."""
        ...


class PushConnector(Connector):
    kind = ConnectorKind.PUSH

    @abstractmethod
    def push(self, payload: Mapping[str, Any]) -> "PushResult":
        """Send one payload. Idempotency key (if any) is in payload['_idem']."""
        ...


@dataclass(frozen=True)
class PushResult:
    ok: bool
    external_id: str | None       # e.g. Tally voucher number, Gmail message id
    latency_ms: int
    error: str | None = None
    retryable: bool = False


class PullConnector(Connector):
    kind = ConnectorKind.PULL

    @abstractmethod
    def pull(self, since: datetime | None) -> Iterable["PullEvent"]:
        """Yield normalized domain events since the given cursor.
        Connector is responsible for paginating and for converting
        channel-specific shapes into the canonical domain shape."""
        ...

    @abstractmethod
    def cursor_key(self) -> str:
        """Key under which last-pulled cursor is persisted per instance."""
        ...


@dataclass(frozen=True)
class PullEvent:
    event_type: str               # e.g. "ops.order.received"
    external_id: str
    occurred_at: datetime
    payload: Mapping[str, Any]    # normalized domain payload


class ReceiveConnector(Connector):
    kind = ConnectorKind.RECEIVE

    @abstractmethod
    def verify(self, headers: Mapping[str, str], raw_body: bytes) -> bool:
        """HMAC / signature verification."""
        ...

    @abstractmethod
    def handle(
        self, headers: Mapping[str, str], body: Mapping[str, Any]
    ) -> Iterable[PullEvent]:
        """Translate the inbound payload into one or more normalized events.
        Returning an iterable lets one webhook expand to multiple domain events
        (e.g. a Shopify order create with refunds)."""
        ...
```

Three properties of this ABC matter:

- **Connectors do not call the event bus directly.** `PullConnector.pull` and `ReceiveConnector.handle` *yield* `PullEvent`s. The framework — not the connector — decides whether to publish them, persist them first, or dedupe. This is what allows replay and idempotency to be uniform.
- **`push` returns a structured result.** Callers do not catch exceptions from connector internals; they read `result.ok` and `result.retryable`. Exceptions are still raised for programmer errors (bad config, missing field) but transport errors are values.
- **`auth_test` is mandatory.** Every connector must offer a cheap reachability check. Health monitoring assumes this.

## 4. Configuration model

Two tables, both keyed by `(tenant_id, connector_id, instance_name)`. The composite key — note that `instance_name` is part of it — supports the realistic case where one tenant has, say, two Shopify stores or two Tally companies.

```sql
CREATE TABLE integration_configs (
    id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id               uuid NOT NULL REFERENCES tenants(id),
    connector_id            text NOT NULL,         -- e.g. "tally"
    instance_name           text NOT NULL DEFAULT 'default',
    display_name            text NOT NULL,         -- "Tally — Mumbai Books"
    status                  text NOT NULL DEFAULT 'enabled',
                                                   -- enabled | disabled | error
    config                  jsonb NOT NULL DEFAULT '{}'::jsonb,
                                                   -- non-secret config
    last_health_check_at    timestamptz,
    last_health_ok          boolean,
    last_health_error       text,
    created_at              timestamptz NOT NULL DEFAULT now(),
    updated_at              timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, connector_id, instance_name)
);

CREATE TABLE integration_credentials (
    id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    integration_config_id   uuid NOT NULL REFERENCES integration_configs(id) ON DELETE CASCADE,
    -- AES-GCM ciphertext; nonce stored alongside, key id allows rotation
    ciphertext              bytea NOT NULL,
    nonce                   bytea NOT NULL,
    key_id                  text  NOT NULL,
    rotated_at              timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX ix_integration_configs_tenant_connector
    ON integration_configs (tenant_id, connector_id) WHERE status = 'enabled';
```

The split between `integration_configs` and `integration_credentials` is deliberate: non-secret config (Tally server URL, mapping ids, polling cadence) is queryable, inspectable, exportable. Secrets are a separate, encrypted blob whose plaintext is only ever held in memory inside a connector instance.

`config` JSONB structure is per-connector but always includes a `schema_version` field. Migration of config shapes is handled by the connector's `migrate_config` hook at registry load time.

## 5. Registry & discovery

Connectors register themselves at startup. The registry is a process-wide singleton built from imports.

```python
# app/core/integrations/registry.py

from typing import Type
from app.core.integrations.base import Connector, ConnectorContext


class ConnectorRegistry:
    def __init__(self):
        self._classes: dict[str, Type[Connector]] = {}

    def register(self, cls: Type[Connector]) -> Type[Connector]:
        if cls.id in self._classes:
            raise RuntimeError(f"Duplicate connector id: {cls.id}")
        self._classes[cls.id] = cls
        return cls

    def get(
        self,
        connector_id: str,
        tenant_id,
        instance_name: str = "default",
    ) -> Connector:
        cls = self._classes.get(connector_id)
        if cls is None:
            raise UnknownConnector(connector_id)
        ctx = self._load_context(tenant_id, connector_id, instance_name)
        return cls(ctx)

    def list_for_tenant(self, tenant_id) -> list["ConnectorInstance"]:
        ...

    def _load_context(self, tenant_id, connector_id, instance_name) -> ConnectorContext:
        # SELECT FROM integration_configs JOIN integration_credentials,
        # decrypt credentials, build ConnectorContext.
        ...


registry = ConnectorRegistry()
```

Each connector module registers itself by decorator at import time:

```python
# app/core/integrations/tally/connector.py
from app.core.integrations.registry import registry
from app.core.integrations.base import PushConnector

@registry.register
class TallyConnector(PushConnector):
    id = "tally"
    ...
```

`app/core/integrations/__init__.py` imports every connector subpackage so the decorators fire. The order does not matter; duplicate-id detection catches mistakes.

**Module-side usage** is one line — never a direct import of the connector class:

```python
# app/modules/accounts/services.py
from app.core.integrations import registry

def push_invoice_to_tally(invoice, tenant_id):
    tally = registry.get("tally", tenant_id=tenant_id)
    return tally.push(build_tally_payload(invoice))
```

**Adding a new connector** requires zero changes outside `app/core/integrations/`:

1. Create `app/core/integrations/<new>/connector.py`.
2. Subclass the right kind ABC. Implement methods.
3. Add an import line in `app/core/integrations/__init__.py`.
4. Add a row in the seed for default config schema (Section 4).
5. Add the connector card in `frontend/.../settings/integrations/`.

No module changes. No router changes. No migration unless the connector ships new tables of its own.

## 6. Tally connector

Tally is the most important push connector and gets a dedicated section because everything that can go wrong with integrations goes wrong with Tally.

### 6.1 Mapping is configuration, not code

The Tally connector does not hard-code voucher types, ledger names, or GST groups. All of those are per-tenant configuration stored under `integration_configs.config`:

```jsonc
{
  "schema_version": 2,
  "server": { "host": "192.168.1.10", "port": 9000, "mode": "http_xml" },
  "company_name": "ACME Trading Pvt Ltd",
  "voucher_map": {
    "purchase_invoice": "Purchase",
    "credit_note": "Credit Note",
    "debit_note": "Debit Note"
  },
  "ledger_map": {
    "default_vendor_ledger": "Sundry Creditors",
    "default_expense_ledger": "Purchase Accounts",
    "tcs_ledger": "TCS Payable",
    "round_off_ledger": "Round Off"
  },
  "gst_groups": {
    "intra_state": { "cgst": "CGST", "sgst": "SGST" },
    "inter_state": { "igst": "IGST" }
  },
  "narration_template": "Invoice {invoice_number} dated {invoice_date} from {vendor_name}"
}
```

The connector's `push(payload)` receives a normalized invoice dict from the Accounts module. It is the **connector's** job to look up mappings and build the XML. The module never sees Tally-specific identifiers.

### 6.2 XML generation as a pure function

```python
def build_tally_xml(invoice: dict, mapping: dict) -> str: ...
```

This is a pure function: same invoice + same mapping → byte-identical XML. That property is what makes "dry run" mode (Section 6.5) trustworthy and what makes the connector unit-testable without a live Tally server.

### 6.3 Transport

Default transport is Tally's HTTP-XML server. The `server.mode` config flag allows `odbc` as an alternative path; in that case the connector enqueues an RQ job that a side-loader handles. We do not block the sync path on ODBC.

```python
class TallyConnector(PushConnector):
    id = "tally"

    def push(self, payload):
        xml = build_tally_xml(payload, self.ctx.config)
        if self.ctx.config["server"]["mode"] == "odbc":
            return self._enqueue_odbc(xml, payload["_idem"])
        return self._http_xml_post(xml, payload["_idem"])
```

### 6.4 Idempotency and retry

- The Accounts module supplies a stable `_idem` key derived from the invoice id and a retry counter.
- The connector persists every attempt in a `tally_push_attempts` table local to the connector subpackage: `(idem_key, request_xml_hash, response_xml, status, attempted_at)`.
- A push failure with `retryable=True` (network, 5xx) re-enqueues via the standard worker retry policy with exponential backoff capped at one hour.
- A push failure with `retryable=False` (mapping error, validation error from Tally) emits `acc.invoice.tally_push_failed` and stops; the Accounts UI shows the actionable error.
- The "voucher already exists" response from Tally is treated as success (idempotent).

### 6.5 Dry-run mode

`tally.push(payload, dry_run=True)` returns a `PushResult` with `ok=True`, no network call made, and the generated XML attached in a debug field. The human verification screen in Accounts uses this to show the accountant exactly what will hit Tally before they approve. This single feature has more impact on tenant trust than any other connector property.

## 7. Pull connectors — Shopify, Amazon, Flipkart

The three sales channels are *not* a single connector with branches. They are three separate `PullConnector` classes — each owns its auth, pagination, rate-limit, and quirk model — that yield events of the same shape.

### Common shape

```python
@registry.register
class ShopifyOrdersConnector(PullConnector):
    id = "shopify_orders"

    def pull(self, since):
        cursor = since or self._initial_since()
        for raw_order in self._iter_orders(updated_at_min=cursor):
            yield PullEvent(
                event_type="ops.order.received",
                external_id=str(raw_order["id"]),
                occurred_at=parse(raw_order["created_at"]),
                payload=normalize_shopify_order(raw_order),
            )
```

`normalize_shopify_order` produces the canonical `ops.order.received` payload. The Operations module subscribes to that event type and does not know whether it originated from Shopify, Amazon, Flipkart, or a manual entry.

### Scheduling

The platform scheduler triggers each enabled pull instance per its configured cadence (typical: every 5 minutes for orders). The runner code is generic:

```python
def run_pull(tenant_id, connector_id, instance_name):
    conn = registry.get(connector_id, tenant_id, instance_name)
    since = cursor_store.get(tenant_id, connector_id, instance_name)
    with health_record(conn):
        for event in conn.pull(since):
            event_bus.publish(event.event_type, event.payload, tenant_id=tenant_id)
            cursor_store.advance(tenant_id, connector_id, instance_name, event.occurred_at)
```

Channel quirks — Amazon's report-based vs order-list APIs, Flipkart's seller-id token rotation, Shopify's REST vs GraphQL preferences — live entirely inside their connector. The runner is one piece of code, regardless of channel count.

### Backfill

Initial pull uses the connector's `initial_since` (typically 90 days back, capped). A manual backfill is just `cursor_store.set(..., older_timestamp)` followed by a scheduled run; no special code path.

## 8. Gmail / Outlook

Email is *both* a push connector (outbound send) and a receive connector (inbound poll). They are two separate registrations: `gmail_send` and `gmail_inbound`, `outlook_send` and `outlook_inbound`. This is deliberate — they have different auth scopes, different failure modes, and a tenant may legitimately enable one without the other.

### OAuth

OAuth2 authorization-code flow is handled by the connector subpackage, not by a generic OAuth library wired into modules. The flow:

1. Settings UI calls `GET /api/v1/integrations/gmail_send/oauth/start?tenant_id=...` → connector returns authorize URL.
2. User completes Google consent → redirect lands on `GET /api/v1/integrations/gmail_send/oauth/callback`.
3. Connector exchanges code for tokens, writes encrypted `refresh_token` into `integration_credentials`.
4. On every `push`, the connector lazily refreshes the access token if expired.

Token refresh failures emit `integration.credentials.invalid` so the Settings UI can prompt re-auth.

### Outbound

```python
gmail = registry.get("gmail_send", tenant_id=tenant_id)
gmail.push({
    "to": ["customer@example.com"],
    "template_id": "cs.first_response.v1",
    "vars": {"customer_name": "...", "ticket_id": "..."},
})
```

Template rendering happens at the CS module level (templates are CS-owned data in `cs_templates`); the connector receives a fully-rendered MIME message and sends it.

### Inbound

The inbound connector polls IMAP at a configured cadence (default: 60 seconds) or, for Gmail, optionally subscribes to push notifications via Pub/Sub. Each new message yields a `cs.message.received` `PullEvent`. The CS module subscribes and creates or appends to a ticket.

## 9. WhatsApp Cloud API

The conversation runtime in `app/core/conversation/` is *not* an integration. It is the platform's intent-and-routing engine. The HTTP client that talks to Meta's Cloud API *is* a connector — and it is the canonical example of one piece of capability being split across the framework and a core service.

### Split of responsibilities

| Concern | Owner |
|---|---|
| Receiving the webhook, verifying signature | `whatsapp_webhook` connector |
| Translating a webhook into a normalized inbound message event | `whatsapp_webhook` connector |
| Mapping phone → principal, resolving intent, advancing workflows | `core/conversation` |
| Outbound message HTTP call, rate-limit handling, template lookup | `whatsapp` (push) connector |
| Token management for the WABA | `whatsapp` connector |
| Template message catalog (which templates exist, approval state) | `whatsapp` connector — synced from Meta on a schedule |

### Token & rate-limit handling

The WhatsApp connector owns:
- The system-user access token (long-lived) per tenant.
- Per-phone-number rate-limit windows (Meta's tiers: 1k, 10k, 100k messages/24h).
- A token bucket per phone number; when full, outbound calls are enqueued, not dropped.
- Detection of `131056` (rate hit) and `131048` (spam-rate) errors, mapped to `retryable=True` with backoff.

### Template governance

A free-form outbound message outside the 24-hour customer-care window must use an approved template. The connector enforces this: `push({"kind": "freeform", ...})` outside the window returns `ok=False, retryable=False, error="outside_window_use_template"`. The conversation runtime upstream is supposed to choose a template; this is the last-line check.

## 10. Webhook in/out

Generic webhooks are first-class connectors, not module-level concerns.

### `webhook_in` (receive)

Configuration per instance:
- A unique inbound URL: `/api/v1/integrations/webhook_in/{instance_token}`.
- A shared HMAC secret.
- A handler reference: a string id that maps to a registered handler function. The handler's job is to translate the inbound JSON into a `PullEvent` of a declared type.

Verifying inbound webhooks:

```python
class WebhookInConnector(ReceiveConnector):
    id = "webhook_in"

    def verify(self, headers, raw_body):
        expected = hmac.new(
            self.ctx.config["secret"].encode(),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
        provided = headers.get("X-Nyx-Signature", "")
        return hmac.compare_digest(expected, provided)

    def handle(self, headers, body):
        handler = handler_registry.get(self.ctx.config["handler_id"])
        yield from handler(body)
```

This lets a tenant accept inbound events from anything — a courier's status webhook, a payment gateway, a custom internal tool — with the same auth, observability, and event semantics as any first-class connector.

### `webhook_out` (push)

Subscribes to a configured set of event types. On each matching event, POSTs the event payload to the configured URL with an HMAC signature. Retry policy is the standard worker retry. Failures after max retries emit `integration.webhook_out.delivery_failed`.

This is how Nyx supports a tenant whose own systems want to react to Nyx events without us building a custom integration.

## 11. Credentials management

### At rest

All credentials are encrypted using AES-GCM with a single platform-wide key (the **KEK**, key-encryption key, stored in the deployment's secret store and never in the database or env-file mounted on app servers). The key is loaded once at startup and held in process memory.

The choice of a single platform key (vs per-tenant DEKs) is deliberate for v1: it is simpler, auditable, and adequate for a single-tenant-per-deployment model. Per-tenant DEKs are a future migration when we host multi-tenant.

### Rotation

`key_id` on `integration_credentials` allows multiple keys to coexist during rotation:

1. New key `k2` is loaded; both `k1` and `k2` are available.
2. A background job re-encrypts every credential under `k2`, updating `key_id`.
3. Once all rows are `k2`, `k1` is removed.

This is a one-line operational procedure run during a low-traffic window. The application keeps working throughout.

### What goes where

| Secret type | Where it lives | Where it doesn't |
|---|---|---|
| Platform KEK | Deployment secret store (mounted to memory at startup) | Database, env-file, repo |
| Per-tenant credentials (OAuth refresh tokens, Tally creds, etc.) | `integration_credentials`, encrypted | `.env`, source, logs |
| Webhook HMAC secrets | `integration_credentials`, encrypted | `.env` |
| Connector-wide API keys (none in v1) | n/a | n/a |

**No per-tenant credential is ever in an environment variable.** If a deployment ever requires that, the framework has failed.

### Logging hygiene

The framework provides a `redacted_call()` wrapper used by every connector. It strips Authorization headers, tokens, and any field marked secret in the connector's config schema before logging. Connectors that bypass this and `print` a token will be caught by code review; nothing else is going to save us if a developer is determined to log secrets.

## 12. Observability

Every connector call — push, pull, receive — is wrapped by the framework in a context manager that records to `integration_call_log`:

```sql
CREATE TABLE integration_call_log (
    id                  bigserial PRIMARY KEY,
    tenant_id           uuid NOT NULL,
    connector_id        text NOT NULL,
    instance_name       text NOT NULL,
    kind                text NOT NULL,            -- push | pull | receive | auth_test
    started_at          timestamptz NOT NULL,
    latency_ms          integer NOT NULL,
    ok                  boolean NOT NULL,
    status_code         integer,
    payload_bytes       integer,
    response_bytes      integer,
    error_class         text,
    error_message       text,
    correlation_id      text
);
CREATE INDEX ix_intg_call_log_tenant_connector_started
    ON integration_call_log (tenant_id, connector_id, started_at DESC);
```

A rollup table `integration_health` is updated on each call (last_ok_at, last_error_at, error_count_last_hour, p50/p95 latency over the last hour). The `Settings → Integrations → Health` page reads from `integration_health`, not from the raw log.

Calls older than 30 days are purged from `integration_call_log`; the rollup is retained indefinitely. This is a deliberate retention/cost trade-off, configurable per deployment.

**Tracing.** `correlation_id` flows from the originating module call through the connector and into the worker job for retries, so a single invoice push that retried four times appears as one connected sequence.

## 13. Failure isolation

The framework's worst-case behavior is the property that matters most operationally.

### Sync path: circuit-broken or worker-deferred

A module that calls `tally.push(...)` from a request handler must do so inside a circuit breaker:

```python
with breaker("tally", tenant_id):
    result = tally.push(payload)
```

When the breaker is open (recent failures > threshold), the call short-circuits to `result = PushResult(ok=False, retryable=True, error="circuit_open")` without touching the network. The module then enqueues the push to a worker and returns from the request immediately.

In practice, **Tally pushes never happen on the request path**. The Accounts module enqueues an RQ job; the worker does the connector call. The request returns in milliseconds regardless of Tally's responsiveness.

The same discipline applies to every push connector. The only sync external call we make is `auth_test` from the Settings UI — and that has a hard timeout of three seconds.

### Pull path: per-instance isolation

Each pull instance runs in its own worker job. A slow Amazon SP-API run does not delay a Shopify pull, even within the same tenant. Failed runs are recorded; consecutive failures past a threshold disable the instance and emit `integration.pull.disabled`.

### Receive path: queue, don't process inline

Inbound webhook handlers persist the raw request to `integration_inbound_buffer` and acknowledge `200 OK` immediately. A worker drains the buffer, calls `connector.handle()`, and publishes events. This protects against:
- A slow event-handler causing the external service to retry (webhook storms).
- A malformed payload taking down the webhook endpoint.
- A burst of webhooks overwhelming the event bus.

The buffer is the failure boundary. If event publishing fails, the buffer row stays and is retried; the external system never sees a 5xx.

## 14. Anti-goals

What the integration framework is explicitly **not**:

- **Not an iPaaS.** We are not Workato, Zapier, Tray, or n8n. We do not build a no-code integration builder that lets a tenant connect arbitrary SaaS A to arbitrary SaaS B. The set of connectors is curated and small; that is the entire value proposition.
- **No scraping.** If a service does not have an API, we do not integrate with it. We are willing to lose a deal over this.
- **No headless-browser-based integrations.** Selenium-driven workflows that simulate a human logging into a portal are explicitly out. They are unreliable, legally fraught, and operationally a nightmare.
- **No marketplace.** Connectors are first-party code in the Nyx repo. There is no plugin system, no third-party connector store, no signed binary loading. A third party who wants a connector contributes a PR.
- **No generic ETL.** We do not build a "sync any source to any destination" tool. Each connector exists because a specific module needs it for a specific event flow.
- **No connector versioning at the API surface.** Connectors evolve; the public method shapes (`push(payload)`, `pull(since)`) do not. Internal connector versions exist (`Connector.version`) but are an implementation detail.
- **No alternative auth flows per connector beyond what the vendor mandates.** We use OAuth2 where the vendor uses OAuth2, basic auth where mandated, API keys where typical. We do not invent SSO bridges or token-translation layers.

Saying no to all of these is what makes the framework small enough to actually maintain across five business modules without becoming the team's full-time job.

## 15. Where this document ends and others begin

- The **event types** that pull and receive connectors yield are defined in `docs/architecture/05-events.md`.
- The **scheduler** that drives pull cadence is documented in `docs/architecture/06-scheduler.md`.
- The **workflow actions** that *call* connectors (e.g. `send_whatsapp`, `push_to_tally`) are documented in `docs/architecture/04-workflows.md`.
- The **conversation runtime** that sits on top of the WhatsApp connector is documented in `docs/architecture/07-conversation.md`.

The integration framework is one capability. It must do its one job — uniform, swappable, fault-isolated, observable external I/O — and stay out of the way of everything else.
