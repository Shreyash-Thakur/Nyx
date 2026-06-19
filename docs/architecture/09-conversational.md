# 09 — The Conversational Layer

This document specifies the Conversational Runtime: the subsystem that lets warehouse staff, dispatch supervisors, accountants, and founders drive Nyx through WhatsApp. It is the most opinionated part of the platform and the single capability that decides whether Nyx is adopted or shelved in an Indian SME.

This is a UI document. It is not an integration document. The WhatsApp Cloud API is an HTTP detail; what we describe here is how a `DONE` reply from a warehouse picker becomes a state transition in the same workflow engine that a button click on the Next.js dashboard drives.

---

## 1. Why WhatsApp is a primary UI

In a 60-person warehouse in Bhiwandi, the floor staff own one device: a sub-₹15k Android phone on a Jio prepaid plan. That phone runs WhatsApp, a UPI app, YouTube, and not much else. Asking that operator to log into a web dashboard — to remember a username, choose a password, hold a session, navigate a sidebar, find the right SKU, click a button — is a UX claim no Indian SME has ever won.

The operator already lives in WhatsApp. Their supervisor coordinates dispatch through WhatsApp groups. Their family is on WhatsApp. The keyboard is muscle memory. Voice notes are how they prefer to communicate. The single behaviour we can rely on is: *they will read and reply to a WhatsApp message that names them or their task*.

Every ERP we compete with treats WhatsApp as an output channel — a place to dump notifications that are also visible on the dashboard the operator never opens. We invert that. The dashboard is the audit and configuration surface for office staff. WhatsApp is the operational surface for the floor. The same business action — "task #451 complete" — must work identically whether it originates from a Next.js click or a one-word WhatsApp reply.

This has consequences that cascade through the rest of the platform:

- The workflow engine cannot have UI-specific branches. A workflow advancing on `TaskCompleted` does not know or care whether the event originated from web or WhatsApp.
- The RBAC layer cannot care which UI a request came from. `can(user, "complete", task, scope)` is the same check.
- The audit log must record the *channel of origin* as metadata, but the *effect* is identical.
- The task model has to be designed for one-word replies, not for rich forms.

This is what we mean by *WhatsApp is a UI, not an integration*. If a feature only works via the dashboard, that feature does not exist for half our users.

---

## 2. End-to-end flow

```
              ┌────────────────────────────────────┐
              │     WhatsApp Cloud API (Meta)      │
              └──────────────────┬─────────────────┘
                                 │ HTTPS POST
                                 ▼
              ┌────────────────────────────────────┐
              │  /webhook/whatsapp  (FastAPI)      │
              │  - signature verification          │
              │  - dedup by wa_message_id          │
              │  - ack 200 fast, enqueue for proc  │
              └──────────────────┬─────────────────┘
                                 │ enqueue (Redis / RQ)
                                 ▼
              ┌────────────────────────────────────┐
              │       Conversation Runtime         │
              │                                    │
              │  1. authenticate by phone          │
              │     → principal (user_id, tenant)  │
              │  2. resolve context — which open   │
              │     pending_prompts is this user   │
              │     attached to?                   │
              │  3. intent parser (rule-based)     │
              │     → matched intent OR fall-thru  │
              │  4. RBAC check                     │
              │     can(user, action, resource)    │
              │  5. invoke action                  │
              │     → workflow.advance(...)        │
              │     OR direct service call         │
              │  6. emit events                    │
              │     → event bus                    │
              │  7. generate templated outbound    │
              └──────────────────┬─────────────────┘
                                 │
                                 ▼
              ┌────────────────────────────────────┐
              │    WhatsApp Connector (outbound)   │
              │  - template lookup per locale      │
              │  - variable substitution           │
              │  - per-phone rate limit            │
              │  - retry on 5xx / network          │
              │  - record wa_message_id            │
              └──────────────────┬─────────────────┘
                                 │ HTTPS POST
                                 ▼
                       WhatsApp Cloud API
```

Two boundaries to internalise:

1. **Webhook is dumb.** Verify, dedup, enqueue, 200. The webhook handler does not parse intent, does not touch business state, does not call modules. If it crashed mid-flight, Meta retries and dedup absorbs it.
2. **Runtime owns the conversation; modules own their domain.** The runtime decides *what the user said*. It never decides *what the business should do*. That is the workflow engine's job, parameterised by the module's workflow definition.

---

## 3. Principal resolution

A phone number is **not** a user. A phone number is a *channel address*. The mapping from phone number → user is explicit, claimed, verified, and revocable.

### Claiming a number

A user in the web dashboard goes to their profile and adds a phone number. The system sends an OTP via WhatsApp (using a pre-approved `phone_claim_otp` template). The user replies with the 6-digit code on WhatsApp itself — proving they control the handset and read messages on it. Only on successful OTP match is the `identity_phone_claims` row marked verified.

A single user may claim multiple numbers (personal phone + warehouse handset shared with no one). Different numbers can have different channel preferences (e.g., the warehouse handset receives operational prompts; the personal number receives founder approval prompts).

Conversely, **one phone number maps to exactly one verified user at a time**. If a user leaves the company, their phone claim is revoked; the same number can later be claimed by someone else.

### Schema (lives in `app/core/identity/`)

```sql
-- A claim is a mapping from a phone number to a user, verified or pending.
CREATE TABLE identity_phone_claims (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       BIGINT NOT NULL REFERENCES tenants(id),
    user_id         BIGINT NOT NULL REFERENCES users(id),
    phone_e164      TEXT   NOT NULL,          -- always normalised, e.g. +919876543210
    label           TEXT,                      -- "personal", "warehouse-A"
    verified        BOOLEAN NOT NULL DEFAULT FALSE,
    verified_at     TIMESTAMPTZ,
    revoked_at      TIMESTAMPTZ,
    channel_prefs   JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, phone_e164) WHERE revoked_at IS NULL AND verified = TRUE
);

CREATE INDEX idx_phone_claims_lookup
    ON identity_phone_claims (phone_e164)
    WHERE revoked_at IS NULL AND verified = TRUE;
```

The partial unique index enforces the "one active verified claim per number" rule at the database level.

### Resolution algorithm

```python
def resolve_principal(phone_e164: str) -> Principal | UnknownSender:
    row = db.execute(
        select(IdentityPhoneClaim)
        .where(
            IdentityPhoneClaim.phone_e164 == phone_e164,
            IdentityPhoneClaim.verified.is_(True),
            IdentityPhoneClaim.revoked_at.is_(None),
        )
    ).scalar_one_or_none()

    if row is None:
        return UnknownSender(phone=phone_e164)

    return Principal(
        user_id=row.user_id,
        tenant_id=row.tenant_id,
        phone_e164=row.phone_e164,
        claim_id=row.id,
    )
```

An `UnknownSender` falls through to a separate code path (§13). No state mutation, no workflow advance, ever happens for an unknown sender. **We do not trust the phone number to be the principal until a claim is verified.**

---

## 4. The pending-prompt model

This is the single most important data structure in the conversational layer. Without it, `DONE` is ambiguous: which task is the user completing? The web UI doesn't have this problem because a button click carries its target as a query parameter. WhatsApp doesn't carry that context — the user types one word into the same chat thread that also holds yesterday's tasks.

A `pending_prompt` is a row that says *"we sent this user an outbound message that expects a reply of a particular shape, and here is the workflow context that reply will advance."*

### Schema (lives in `app/core/conversation/`)

```sql
CREATE TABLE conversations (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       BIGINT NOT NULL REFERENCES tenants(id),
    user_id         BIGINT NOT NULL REFERENCES users(id),
    phone_e164      TEXT   NOT NULL,
    channel         TEXT   NOT NULL DEFAULT 'whatsapp',  -- whatsapp | sms (future)
    locale          TEXT   NOT NULL DEFAULT 'en-IN',
    last_inbound_at TIMESTAMPTZ,
    last_outbound_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, user_id, phone_e164, channel)
);

CREATE TABLE conversation_messages (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       BIGINT NOT NULL REFERENCES tenants(id),
    conversation_id BIGINT NOT NULL REFERENCES conversations(id),
    direction       TEXT NOT NULL,             -- inbound | outbound
    wa_message_id   TEXT,                      -- Meta's id; unique for dedup
    body            TEXT,                      -- raw text (post-normalisation kept separately)
    body_normalized TEXT,                      -- lower, stripped, no emojis
    template_id     BIGINT,                    -- non-null on outbound template sends
    matched_prompt_id BIGINT REFERENCES conversation_pending_prompts(id),
    matched_intent  TEXT,                      -- e.g. "DONE", "APPROVE", "ISSUE", "FREE_TEXT"
    classifier_label TEXT,                     -- LLM-assigned label (issue category, etc.)
    classifier_confidence NUMERIC(4,3),
    status          TEXT NOT NULL,             -- received | processed | failed | duplicate
    error           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (wa_message_id)
);

CREATE INDEX idx_conv_messages_conv ON conversation_messages (conversation_id, created_at DESC);

CREATE TABLE conversation_pending_prompts (
    id                     BIGSERIAL PRIMARY KEY,
    tenant_id              BIGINT NOT NULL REFERENCES tenants(id),
    conversation_id        BIGINT NOT NULL REFERENCES conversations(id),
    user_id                BIGINT NOT NULL REFERENCES users(id),

    -- what shape of reply do we accept?
    expects                TEXT   NOT NULL,    -- "done_or_issue" | "approve_reject"
                                               -- | "free" | "issue" | "yesno" | "number"

    -- what does this prompt represent?
    workflow_instance_id   BIGINT,             -- if attached to a workflow step
    task_id                BIGINT,             -- if attached to a task
    resource_kind          TEXT,               -- "invoice" | "dispatch" | "transfer" | ...
    resource_id            BIGINT,

    outbound_message_id    BIGINT NOT NULL REFERENCES conversation_messages(id),

    status                 TEXT   NOT NULL DEFAULT 'open',
                                               -- open | answered | expired | cancelled
    answered_message_id    BIGINT REFERENCES conversation_messages(id),
    answered_at            TIMESTAMPTZ,

    expires_at             TIMESTAMPTZ NOT NULL,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_pending_prompts_open
    ON conversation_pending_prompts (user_id, status, expires_at)
    WHERE status = 'open';
```

### Lifecycle

1. A module (e.g. Operations) creates a task and asks the runtime to surface it via WhatsApp.
2. The runtime renders an outbound template, sends it, and inserts a `conversation_pending_prompts` row with `status='open'` and `expires_at = now() + interval '24 hours'` (Cloud API's session window).
3. Inbound message arrives. The runtime queries open prompts for that user, ordered by `created_at DESC`, picks the most recent unexpired one whose `expects` shape matches the parsed intent.
4. On match: the prompt is marked `answered`, the matched intent is dispatched to the workflow engine or service, and an outbound confirmation is sent.
5. If no open prompt matches: the message is either treated as a global command (`HELP`, `STATUS`, `CANCEL`) or, if the user has any open prompt, replied to with disambiguation help.
6. A prompt expires when `expires_at < now()`. A background job (`expire_pending_prompts`) flips status to `expired` and may optionally send a chase or close the underlying task.

### Why "most recent unexpired wins"

In practice, a warehouse picker has at most 2–3 open prompts in flight. The most recent is by far the most likely target. We do not attempt clever disambiguation in v1 (no "reply with task #" because we cannot trust operators to read task numbers). If the operator answers a stale prompt, they get a friendly "this task is no longer open — your latest open task is #X". Better than a wrong state transition.

---

## 5. Intent parser

The intent parser is rule-based, deterministic, and dumb. That is the whole point. `DONE`, `APPROVE`, `REJECT` are business-critical actions; they cannot depend on an LLM's mood, latency, or token budget.

### Pipeline

```
raw text  →  tokenize  →  normalize  →  match registry  →  intent | fallthrough
```

- **Tokenize**: split on whitespace; keep punctuation for emoji-stripping; preserve numbers (`50` matters for partial-quantity replies).
- **Normalize**: lowercase, strip emojis, strip zero-width characters, collapse whitespace, trim. Hindi/Hinglish tokens are preserved as-is (we do not transliterate in v1; the registry contains common Hinglish synonyms).
- **Match**: against the registry filtered by the current pending prompt's `expects`.

### Intent registry (illustrative)

```python
INTENTS_BY_EXPECTS = {
    "done_or_issue": [
        Intent("DONE",   patterns=["done", "ok", "complete", "completed", "ho gaya",
                                   "hogya", "kar diya", "ready", "✅"]),
        Intent("ISSUE",  patterns=["issue", "problem", "dikkat", "samasya",
                                   "not done", "nahi", "no"]),
    ],
    "approve_reject": [
        Intent("APPROVE", patterns=["approve", "approved", "yes", "ok", "haan",
                                    "✅", "👍"]),
        Intent("REJECT",  patterns=["reject", "rejected", "no", "nahi", "❌",
                                    "👎"]),
    ],
    "yesno": [
        Intent("YES", patterns=["yes", "y", "haan", "ha"]),
        Intent("NO",  patterns=["no", "n", "nahi"]),
    ],
    # number, free, issue handled specially
}

# Always-on global intents, matched before pending-prompt routing.
GLOBAL_INTENTS = [
    Intent("HELP",   patterns=["help", "madad", "?"]),
    Intent("STATUS", patterns=["status", "my tasks", "task list"]),
    Intent("CANCEL", patterns=["cancel", "stop", "abort"]),
]
```

### Match algorithm

```python
def parse_intent(message: ConversationMessage, prompt: PendingPrompt | None) -> ParsedIntent:
    text = normalize(message.body)

    # Global first — these always work regardless of context.
    for intent in GLOBAL_INTENTS:
        if intent.matches(text):
            return ParsedIntent(kind="global", name=intent.name)

    if prompt is None:
        return ParsedIntent(kind="orphan", name=None, raw=text)

    candidates = INTENTS_BY_EXPECTS.get(prompt.expects, [])
    for intent in candidates:
        if intent.matches(text):
            return ParsedIntent(kind="matched", name=intent.name, prompt=prompt)

    # Fallthrough — only allowed for free-form expects.
    if prompt.expects in ("free", "issue"):
        return ParsedIntent(kind="fallthrough_llm", prompt=prompt, raw=text)

    return ParsedIntent(kind="unmatched", prompt=prompt, raw=text)
```

`unmatched` for a structured prompt triggers a polite "I expected `DONE` or `ISSUE`. Reply `HELP` for options." The user is never left guessing.

---

## 6. LLM classifier (fallback only)

The LLM is invoked **only** when the intent parser returns `fallthrough_llm`. That happens for prompts whose `expects` is `free` or `issue` — cases where the user is explaining something in natural language, not selecting from a menu.

The classifier does one thing: map free text to a small fixed taxonomy. It does not generate actions. It does not write to the database. Its output is a (label, confidence) pair that the runtime then uses as routing information.

### Example taxonomies

```python
ISSUE_TAXONOMY = [
    "out_of_stock",
    "damaged_goods",
    "wrong_sku",
    "partial_quantity",
    "address_issue",
    "courier_unavailable",
    "other",
]

# For customer service inbound free-text:
TICKET_TAXONOMY = [
    "order_status",
    "delivery_delay",
    "return_request",
    "refund_query",
    "product_defect",
    "other",
]
```

### Output schema

```json
{
    "label": "partial_quantity",
    "confidence": 0.86,
    "rationale": "user reports 8 units available against expected 50"
}
```

The rationale is stored on the message for audit and debugging; it never drives behaviour.

### Confidence threshold

A per-tenant config (`conversation.classifier.min_confidence`, default `0.65`) decides what happens below threshold:

- **>= threshold**: label is accepted, runtime proceeds (e.g., create an incident with that category).
- **< threshold**: message is routed to a human triage queue (`cs_triage_queue` or `ops_triage_queue` depending on context) and the user receives a generic "Thanks, we've flagged this for review" reply.

The classifier is one of perhaps three places in Nyx where an LLM is invoked. The other two are summarization (founder daily digest) and KPI narrative (founder insights). All three are out of any latency-critical path. A classifier failure or timeout falls back to human triage — never to "make something up".

---

## 7. Outbound message templates

The WhatsApp Cloud API is strict: outside a 24-hour conversation window (i.e., 24h after the last user inbound), only pre-approved templates can be sent. This is a Meta policy, not a Nyx choice, and it shapes how the outbound side is designed.

### Template registry

```sql
CREATE TABLE conversation_templates (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       BIGINT NOT NULL REFERENCES tenants(id),
    key             TEXT   NOT NULL,            -- e.g. "task_dispatch_v1"
    locale          TEXT   NOT NULL,            -- "en-IN", "hi-IN"
    wa_template_name TEXT NOT NULL,             -- the Meta-approved template name
    wa_namespace    TEXT NOT NULL,
    body_skeleton   TEXT NOT NULL,              -- with {{1}}, {{2}} placeholders
    expects         TEXT NOT NULL,              -- the pending_prompt expects shape
    expires_after_seconds INT NOT NULL DEFAULT 86400,
    UNIQUE (tenant_id, key, locale)
);
```

### Templating engine

Outbound rendering is a two-step process:

1. **Resolve template**: `(tenant_id, key, user.locale) → conversation_templates row`. If locale-specific row is missing, fall back to `en-IN`.
2. **Bind variables**: ordered substitution of `{{1}}, {{2}}, ...` from the action's payload. Variable names are validated against the template's declared parameters at registration time (config-store check).

```python
def render_template(key: str, locale: str, vars: list[str]) -> RenderedMessage:
    tpl = registry.get(tenant_id=ctx.tenant_id, key=key, locale=locale)
    if tpl is None:
        tpl = registry.get(tenant_id=ctx.tenant_id, key=key, locale="en-IN")
    if tpl is None:
        raise TemplateNotFound(key=key)
    body = bind(tpl.body_skeleton, vars)
    return RenderedMessage(
        wa_template_name=tpl.wa_template_name,
        wa_namespace=tpl.wa_namespace,
        body=body,
        expects=tpl.expects,
        expires_after_seconds=tpl.expires_after_seconds,
    )
```

### Free-form vs template

If the last inbound from the user was within 24 hours, the connector is allowed to send a free-form text message (e.g., the "Confirmed." reply after a `DONE`). The runtime tracks `conversations.last_inbound_at` for this decision. If we are outside the window, we must use a template — and if no template fits the message, the message is dropped (with an error log) rather than sent in a way Meta will reject.

---

## 8. Conversation state model (consolidated)

The three tables in §4 together with `identity_phone_claims` in §3 and `conversation_templates` in §7 form the complete state. Key invariants:

- **Conversations are per (tenant_id, user_id, phone_e164, channel).** A user with two phones has two conversations. Messages are not shared across them.
- **Messages are append-only.** Nothing in the codebase updates `conversation_messages` after insert except for setting `status`, `matched_prompt_id`, and classifier fields — all set during initial processing and never revised.
- **`pending_prompts` is the only mutable conversation-side table** beyond `status` columns, and even there the mutations are state-machine transitions: `open → answered`, `open → expired`, `open → cancelled`.
- **Every outbound message that expects a reply creates exactly one pending prompt.** Outbound messages that don't expect a reply (daily summary, "Confirmed.") create none.
- **An inbound message that successfully matches a prompt sets `conversation_messages.matched_prompt_id` and flips the prompt to `answered`.** These two updates happen in one transaction.

### Where it lives

```
app/core/conversation/
├── models.py         # the three tables above
├── webhook.py        # POST /webhook/whatsapp — dumb, fast, idempotent
├── runtime.py        # the main loop: principal → context → intent → action → outbound
├── intent.py         # rule-based parser + intent registry
├── classifier.py     # LLM fallback (optional)
├── outbound.py       # template render + connector send
├── prompts.py        # pending_prompt CRUD and expiry job
└── routes.py         # GET /conversations/{user_id}, admin debugging UI
```

The WhatsApp HTTP client itself lives in `app/core/integrations/whatsapp/` and is the only place that knows about Meta's API shape. The runtime depends on it through an interface (`WhatsAppConnector.send(...)`); swapping in Gupshup or Twilio later means replacing one file.

---

## 9. Worked examples

These are the four canonical traces. The rest of the platform's WhatsApp interactions are variations on these.

### 9.1 Stock transfer task — happy path

**Setup**: Operations creates a transfer task #451 for SKU `NM-WLT-BR-01`, 50 units, Mumbai → Bangalore, assigned to user Ramesh (warehouse picker).

**T+0** — Operations service creates the task and emits `task.created`. A workflow subscribed to that event for the `stock_transfer` workflow type advances to step "notify picker" whose action is `send_whatsapp_prompt`:

```python
runtime.send_prompt(
    user_id=ramesh.id,
    template_key="task_transfer_v1",
    vars=["451", "50", "NM-WLT-BR-01", "Mumbai", "Bangalore"],
    pending_prompt=PromptSpec(
        expects="done_or_issue",
        workflow_instance_id=wf.id,
        task_id=451,
        resource_kind="transfer",
        resource_id=transfer.id,
    ),
)
```

**Outbound** rendered from `task_transfer_v1@en-IN`:
> *Task #451 — transfer 50 units of NM-WLT-BR-01 from Mumbai to Bangalore.*
> *Reply DONE when complete or ISSUE if you have a problem.*

A `pending_prompt` row is inserted with `expects='done_or_issue'`, `expires_at = now() + 24h`.

**T+47m** — Ramesh replies `done`. Webhook fires.

1. Webhook verifies signature, dedups by `wa_message_id`, enqueues, returns 200.
2. Runtime picks up the job.
3. `resolve_principal("+919812345678")` → `Principal(user_id=ramesh.id, tenant_id=1)`.
4. Open prompts for ramesh: `[prompt_for_task_451]`. Most recent unexpired wins.
5. `parse_intent("done", prompt)` → `Intent(name="DONE", kind="matched")`.
6. RBAC: `can(ramesh, "complete", task_451)` → yes (he is the assignee).
7. Action: `tasks.complete(task_id=451, by=ramesh.id, source="whatsapp")`.
8. Operations emits `task.completed`. The workflow engine subscribes to that event for instance `wf.id`, advances to step "update inventory", which emits `inv.transfer.completed`. Inventory subscribes to that event, decrements Mumbai stock by 50, increments Bangalore stock by 50, emits `inv.stock.adjusted` twice. Audit log subscribes to all of them.
9. Workflow's final step is `send_whatsapp_confirmation` (no expected reply).

**Outbound** (free-form, within 24h window):
> *Confirmed. Task #451 complete. Mumbai stock decreased by 50; Bangalore stock increased by 50.*

No new `pending_prompt` is created. The conversation thread for Ramesh now has 2 messages; his task list has one fewer open item.

Total LLM calls: **zero**. This is the path that runs thousands of times a day.

### 9.2 Stock transfer task — issue path

**Setup**: same as above. Ramesh has the same outbound prompt.

**T+47m** — Ramesh replies `only 8 units available`.

1–4. Same as 9.1 up to prompt resolution.
5. `parse_intent("only 8 units available", prompt)` → no exact rule match for `done_or_issue`. Because `expects="done_or_issue"`, NOT `free`/`issue`, the parser returns `unmatched`.

Wait — this is a design choice point. In v1 we treat `done_or_issue` as strict (must reply DONE or ISSUE). The path is:

- Runtime replies: *"I expected DONE or ISSUE. If there is a problem, reply ISSUE first, then describe."*
- Ramesh replies `issue`.
- Runtime matches `ISSUE`. It marks the original prompt answered with intent `ISSUE`. The workflow advances to step "collect issue details" which sends a new prompt with `expects='issue'`:

  > *Got it. Please describe the issue in one message.*

- Ramesh replies `only 8 units available`.
- This time `expects='issue'`, the rule parser sees no fixed-intent match, and falls through to the LLM classifier.

6. Classifier output: `{label: "partial_quantity", confidence: 0.91, rationale: "user reports 8 of expected 50 available"}`.
7. Confidence ≥ threshold → accepted. Runtime calls `incidents.create(...)` (the incidents service in Operations) with category `partial_quantity` and references to task #451 and transfer record.
8. Operations emits `ops.incident.created`. A workflow subscribed to that event for the `partial_quantity` category creates a task for the ops head ("Ramesh reported only 8 of 50 units available for transfer #T-219") and routes it via WhatsApp.
9. Outbound to Ramesh (free-form, in window):
   > *Reported. Ops will reach out shortly. Task #451 paused.*

   The original task is set to `status='blocked'`, not `complete`. The workflow does not advance the inventory step.

LLM calls in this flow: **one**, and it was a classifier with structured output, not a generator. If the classifier had returned confidence 0.4, the incident would still have been created (because we always record the user's report) but with category `unclassified` and routed to a human triage queue.

### 9.3 Founder approval

**Setup**: Accounts has a workflow `founder_approval_required` that fires when an invoice's amount exceeds ₹2,00,000 (configured per tenant). Invoice INV-1029 for ₹2,40,000 is uploaded, OCR'd, reconciled, and ready for Tally push — pending founder approval.

**T+0** — Workflow fires action `send_whatsapp_prompt` to the founder (user Anjali):

Template `invoice_approval_v1@en-IN`:
> *Approve invoice INV-1029 from Vendor "ABC Distributors" for ₹2,40,000?*
> *Reply APPROVE or REJECT.*

`pending_prompt` inserted with `expects='approve_reject'`, `resource_kind='invoice'`, `resource_id=1029`.

**T+12m** — Anjali replies `Approve`.

1. Webhook → enqueue → runtime.
2. Principal: Anjali, tenant 1.
3. Open prompts for Anjali: `[prompt_for_invoice_1029]`.
4. Parse intent: `APPROVE`.
5. **RBAC check is critical here.** `can(anjali, "approve_invoice_over_threshold", invoice_1029, scope=tenant_1)` — yes, Anjali has the `founder` role which holds this permission. If a non-founder were to send `APPROVE` for the same prompt (because they shared a phone, somehow), the RBAC check fails and the action does not execute. We log an authz failure event.
6. Action: `acc.invoice_service.approve(invoice_id=1029, approver=anjali.id, channel="whatsapp")`.
7. Accounts emits `acc.invoice.approved`. The workflow advances; the Tally push action is enqueued.
8. Outbound (free-form):
   > *Approved. Tally push queued for INV-1029.*

When Tally push completes (separate workflow), Anjali receives a final outbound:
> *INV-1029 posted to Tally as voucher V-8842.*

That confirmation is sent via template if outside the 24h window — most likely the case for a founder who replies once and goes back to their day.

### 9.4 Daily summary

**Setup**: at 09:00 IST every business day, the Founder Intelligence module's `daily_snapshot` job runs. The job assembles KPIs (orders yesterday, dispatch SLA hit rate, pending approvals, revenue vs 7-day avg, top alerts) and asks the LLM summarizer to render a 4-bullet WhatsApp digest.

**Outbound** (template `daily_digest_v1`, no expected reply):
> *Good morning. Yesterday: 142 orders (+8% vs avg), 96% on-time dispatch, 3 invoices awaiting your approval, 1 SKU below reorder (NM-WLT-BR-01: 12 units in Bangalore).*

No `pending_prompt` is created. If Anjali wants details, she opens the dashboard or types `STATUS` (which would be a global intent route to a longer text response).

LLM call here: **one**, summarization, offline, with full retry budget. Failure path: send a fixed-format non-LLM digest with raw numbers instead. The user always gets *something*.

---

## 10. Connector vs runtime separation

These are two distinct concerns and live in two different folders, by design.

### Runtime (`app/core/conversation/`)

Owns:
- Conversation state (the three tables in §4)
- Principal resolution
- Pending prompt lifecycle
- Intent parsing
- Classifier orchestration
- The main inbound → action loop
- Outbound template selection (which template, with what vars, when)

Knows:
- The workflow engine API
- The RBAC service
- The audit log
- The notifications service
- The integrations registry (so it can ask for *a* WhatsApp connector)

Does **not** know:
- HTTP, Meta API quirks, rate limit headers, retry policy details, signature algorithm specifics

### Connector (`app/core/integrations/whatsapp/`)

Owns:
- HTTPS client for Meta Cloud API
- Bearer token rotation
- Webhook signature verification helper (used by the runtime's webhook handler)
- Per-phone outbound rate limiting (5 messages / second / phone, conservative)
- Retry on 5xx, 429, network errors with exponential backoff
- Template send vs free-form send routing at the HTTP level
- `wa_message_id` capture from API responses

Knows nothing about:
- Tasks, workflows, invoices, RBAC, principals, prompts
- What a `DONE` is or means

The runtime depends on the connector through a small interface:

```python
class WhatsAppConnector(Protocol):
    def send_template(
        self,
        to_phone_e164: str,
        template_name: str,
        namespace: str,
        variables: list[str],
        locale: str,
    ) -> SendResult: ...

    def send_text(
        self,
        to_phone_e164: str,
        body: str,
    ) -> SendResult: ...

    def verify_webhook_signature(self, raw_body: bytes, header: str) -> bool: ...
```

**Modules never touch either of these directly.** A module creates a task; the task system (with the user's channel preferences in mind) asks the runtime to surface it; the runtime decides the template and the prompt shape; the connector sends the bytes. This indirection is what lets us add Gupshup or replace WhatsApp with SMS for tier-2 cities later, without any module changing a line.

---

## 11. Rate limits, idempotency, dedup

### Inbound dedup

Meta retries webhook deliveries on any non-200 response, or on no response within ~10 seconds. We must assume duplicates. The dedup key is `wa_message_id` — Meta's globally unique id for each inbound. `conversation_messages.wa_message_id` has a `UNIQUE` constraint, and the runtime inserts the row before doing any other work. A duplicate insert raises `IntegrityError`, the runtime swallows it, sets `status='duplicate'` on the existing row only if not already set, and returns 200.

This means the webhook handler is idempotent by construction: receiving the same message twice produces the same end state and zero duplicate side effects.

### Outbound rate limits

Per Meta documentation, business-initiated messages have tier-based daily limits and a soft per-recipient burst limit. Empirically, we never want to send more than 5 messages/second to a single phone (it looks like spam to the recipient regardless of whether Meta allows it). The connector enforces this with a per-phone token bucket in Redis (`wa:ratelimit:<phone_e164>`).

For platform-wide bursts (e.g., the daily 9am digest to 200 users), the outbound worker pool processes the send queue at a configurable global rate.

### Outbound idempotency

Every outbound send carries a `client_send_id` (we generate a UUID before calling the connector). The connector ensures: if the same `client_send_id` is sent twice (because of a worker crash + retry), only one Meta API call is made — the second attempt looks up the prior `wa_message_id` from a short-lived Redis key (`wa:send:<client_send_id>` → `wa_message_id`, TTL 1 hour).

### Workflow advance idempotency

The workflow engine has its own idempotency: `workflow.advance(instance_id, event_id)` is keyed on `(instance_id, event_id)`. Replaying a `task.completed` event does not double-advance. This combines with the conversation-side dedup to give us end-to-end at-least-once delivery with at-most-once effect.

---

## 12. Security

### Webhook signature verification

Meta signs webhook payloads with HMAC-SHA256 using the app secret, in the `X-Hub-Signature-256` header. The webhook handler verifies this on every request before doing anything else. A signature failure returns 401 and increments a metric — never a 200, never an enqueue.

### Principal binding before mutation

No action that mutates state runs without a verified principal. The runtime's main loop has exactly one place where it dispatches actions (step 5 in §2), and that place requires a `Principal` (not `UnknownSender`). Compile-time and code-review enforced.

### Phone number is never trusted to be a user

Two layers of defence:
1. The `identity_phone_claims` table is the only way a phone becomes a user. No "auto-create user from new phone number" shortcut exists.
2. Even if a claim is verified, the RBAC layer always re-checks permissions at the moment of action. A user who has been demoted yesterday cannot approve an invoice via WhatsApp today, even though their phone claim is still valid.

### OTP claim flow

The OTP is 6 digits, expires in 5 minutes, single-use, and rate-limited to 3 attempts per 24h per (user, phone). After 3 failures, the claim attempt is locked and requires admin intervention. OTP send and verify events go through the audit log.

### Reuse / takeover protection

When a phone claim is revoked (employee leaves), all open `pending_prompts` for that user are marked `cancelled` and a new outbound is **not** sent to the number explaining why (we don't want to leak that the user has been terminated). If the same number is later claimed by a different user, the old conversation row is archived; a new conversation is created. No messages cross the boundary.

### Personally identifiable information

Conversation message bodies are PII. Database backups are encrypted at rest. Access to `conversation_messages` from the admin UI requires `conversation.read` permission, audit-logged on every view. We do not export raw message bodies to analytics; aggregates only.

---

## 13. Failure modes

### WhatsApp Cloud API is down

The outbound queue absorbs the failure. The connector retries with exponential backoff (1s, 2s, 4s, ..., capped at 5m). After 6 attempts without success, the outbound is marked `failed` and a notification is raised to the ops on-call channel (in-app, not WhatsApp). Inbound is unaffected — Meta will queue and replay webhooks when our endpoint recovers.

A circuit breaker tracks consecutive failures across all outbound to all users. When tripped, new outbounds are stored as `pending_dispatch` instead of being attempted; an admin alert fires; the breaker resets after a half-open probe succeeds.

### Reply to an expired prompt

User replies to a 2-day-old prompt. `expires_at < now()`. The runtime:
1. Inserts the inbound message as usual (so we have the audit trail).
2. Finds no open matching prompt.
3. Checks: does this user have *any* current open prompt? If yes, replies with: *"That task is no longer open. Your current open task is #X — reply DONE or ISSUE."* If no: *"That task is no longer open. No current tasks for you. Reply STATUS to see your queue."*

The expired prompt remains `expired`. The user is never silently ignored.

### Unknown sender

A message arrives from a phone with no verified claim. The runtime:
1. Inserts the inbound message with `conversation_id=NULL` (no conversation is created for unknown senders).
2. Logs an `identity.unknown_sender` event.
3. Optionally — per tenant config — replies with a fixed message: *"This number is not registered with the system. Please contact your administrator."*
4. Optionally — per tenant config — creates a low-priority ticket for the security team to review.

No state mutation in any module. Ever.

### Classifier timeout or error

If the LLM classifier returns an error or times out (configured budget: 8 seconds), the runtime proceeds as if the result was `(label="other", confidence=0.0)`. The message is routed to human triage. The user receives the generic "flagged for review" reply. We never block the conversation pipeline on an LLM call.

### Outbound template not approved

If a template required by the runtime is not registered (or Meta has not approved it), the send fails immediately with `TemplateNotFound`. The pending prompt is **not** created (it would orphan otherwise). An alert fires; a fallback action (in-app notification + email) is taken if the workflow defines one.

### Pending prompt orphan

A pending prompt is "orphaned" if its workflow instance was cancelled or its task was deleted while the prompt was open. A nightly job (`cleanup_orphan_prompts`) scans for prompts whose referenced resource is gone and marks them `cancelled`. If the user replies in the meantime, the runtime checks the referenced resource at match time and degrades to the expired-prompt path if needed.

---

## 14. Anti-goals

These are deliberate refusals. Each one is a feature someone will ask for. Each one is also how the conversational layer goes from useful to unusable.

- **No chatbot-style open conversations.** A user cannot ask "what's the stock of NM-WLT-BR-01?" and get a freeform answer. Stock queries happen on the dashboard, or via a structured `STATUS` global command with predefined output. Open-ended Q&A is unbounded scope and a vector for hallucination.
- **No AI-driven "do anything by typing".** We will not parse "transfer 50 units to Bangalore" and have it become a transfer. Workflow initiation happens from the dashboard or from a module's automation rules. The WhatsApp UI is for *responding to* prompts, not for *initiating* arbitrary state changes.
- **No in-WhatsApp dashboards or reports beyond the canned daily summary.** Founders who want details open the dashboard. The 9am digest is the only push.
- **No group chat support in v1.** All prompts and replies are 1:1. Group chats break the principal model — Meta does not give us a verified per-message sender mapping that we can trust against our claim table. Future versions may support read-only broadcast groups, but never action-bearing group replies.
- **No voice note transcription in v1.** Operators do send voice notes. We acknowledge receipt ("Got it — please reply DONE or ISSUE in text") and store the audio file ref for human review. Treating a 30-second Hindi voice note as an authoritative `DONE` would require a transcription stack that we will not own.
- **No emojis as primary intent signals.** We accept emojis as synonyms (✅ → DONE, 👍 → APPROVE) but never as the sole indicator. The rule registry treats them as match patterns, not as the canonical name.
- **No "the AI noticed something" inbound.** The classifier categorizes user-provided free text. It does not roam, summarize, or surface things proactively in the chat thread. Proactive insights live on the dashboard.
- **No multi-turn dialogue beyond two turns.** A prompt expects one reply. If clarification is needed, that's a second prompt — a new row in `conversation_pending_prompts`. We do not maintain hidden conversation state across more than two exchanges. Anything that needs three turns belongs in the dashboard.

---

## 15. Summary

The conversational layer is a thin, deterministic, audited UI that maps inbound WhatsApp messages to the same workflow engine and RBAC system the dashboard uses. Its correctness rests on four ideas:

1. **Phone claims, not phone trust** — a number is a channel; the principal is the user it is bound to.
2. **Pending prompts, not free dialogue** — every reply has a known target, registered before it can arrive.
3. **Rules first, LLM only for fuzz** — `DONE`, `APPROVE`, `REJECT` are regex matches; LLMs categorize free text and nothing else.
4. **Runtime owns conversation, connector owns HTTP** — and modules touch neither.

If those four hold, an operator on a Jio phone in Bhiwandi runs the warehouse without ever opening a browser, and the system records every state transition with the same audit fidelity as a click on a dashboard in Mumbai. That is the bet.
