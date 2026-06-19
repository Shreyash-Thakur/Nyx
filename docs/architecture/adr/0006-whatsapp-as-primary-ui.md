# ADR 0006 — WhatsApp as a primary UI, not a notification channel

**Status:** Accepted
**Date:** 2026-06-19

## Context

Operational staff in Indian SMEs — warehouse pickers, delivery coordinators, junior accountants — do not log into web dashboards. They live on WhatsApp. Every existing ERP either ignores this reality or treats WhatsApp as a one-way notification channel ("your order has shipped"). Both options leave a coordination gap that gets filled with private WhatsApp groups, spreadsheets, and undocumented norms.

## Decision

Treat WhatsApp as a **primary user interface**, equivalent in capability and authority to the web dashboard. A warehouse picker should be able to do their entire day's work without opening a browser. The same workflows, same RBAC, same audit trail.

## What this means concretely

- An action triggered by a WhatsApp message goes through the same `can()` check as a web request.
- Outbound messages from the platform register a `pending_prompt`; inbound replies match against open prompts, never against generic NLU.
- The intent layer is rule-based for deterministic actions (`DONE`, `APPROVE`, `REJECT`, `HELP`, `ISSUE`, `CANCEL`). LLMs are used only for free-text classification when no rule matches and the prompt allows free input. See ADR 0007.
- Every message in and out is persisted; the conversation log is the operational record.
- Workflows decide per-task whether to surface via WhatsApp, web, or both, based on the assignee's channel preferences.

## Why

1. **Reality.** This is how Indian SME operations already work. The choice is between supporting it natively or losing the workflow into private chats we can't observe.
2. **Adoption.** Telling a warehouse picker to "use the dashboard" is the moment Nyx loses. Telling them to "reply DONE on WhatsApp" requires zero training.
3. **Auditability.** The current spreadsheet-and-WhatsApp world has zero audit trail. Bringing those interactions through Nyx creates one.
4. **Differentiation.** Most ERPs targeting Indian SMEs treat WhatsApp as bolt-on. Treating it as primary is a defensible product position.

## Consequences

**Positive:**
- The conversational runtime is one of two interface layers; the other (web) is its peer.
- The pending-prompt model gives us a stateful conversation without LLM-level context tracking.
- Compliance-friendly: every state-changing message has an audit row tied to a user principal.

**Negative:**
- Meta's WhatsApp Cloud API constraints — template pre-approval, 24h conversation windows, rate limits — impose real operational discipline. Mitigation: a small fixed set of generic templates seeded early.
- Phone-to-user mapping is a security-critical step. Mitigation: OTP claim, audit on every change, ability to revoke.
- We can't ship purely with web in mind; every workflow has to think about its WhatsApp surface too. Mitigation: workflows declare `surface: [web, whatsapp]` in their definition.

## Why this is interview-valuable

The architectural answer to "how do you support WhatsApp?" is usually one of:
- "We send notifications." Boring, common, low-skill.
- "We have a chatbot." Wrong — chatbots without conversation state and proper authz are demo toys.

Our answer:
- The conversation runtime is a UI peer to the web. It resolves principals from phones via claim+OTP. Inbound messages match against open `pending_prompts` to disambiguate intents. Rule-based for deterministic actions; bounded LLM classification for free text. Every state mutation goes through the same RBAC and writes the same audit row. The workflow engine doesn't know or care which interface triggered the step.

That answer is closer to "we built a real product" than "we have a WhatsApp integration."

## Rejected alternatives

**WhatsApp as notification only.** Rejected; misses the entire value of the interface.

**A separate "bot" persona with its own access model.** Rejected; security nightmare and creates a second authz path that drifts from the web one.

**Open-NLU chatbot on inbound (LLM understands free-form messages and takes actions).** Rejected. Slow, expensive, unreliable, and unsafe for deterministic operations. LLMs touch only the fuzzy classification fallback.

**Telegram / Signal / SMS instead.** WhatsApp has the install base in India that the others don't. We may add Telegram as a second channel later; SMS is fallback for OTPs only.
