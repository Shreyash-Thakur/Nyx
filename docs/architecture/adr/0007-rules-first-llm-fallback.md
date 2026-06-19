# ADR 0007 — Rule-based intents in the action path; LLM only as fallback for fuzzy text

**Status:** Accepted
**Date:** 2026-06-19

## Context

The conversational layer must convert inbound messages into platform actions. The temptation — and a common architecture in 2026 — is to put an LLM at the front and let it "understand" everything. This is wrong for our use case.

## Decision

Deterministic actions are matched by **rules** (normalized keyword + intent registry against the user's open `pending_prompts`). LLMs are invoked only when:

1. The pending prompt explicitly accepts free text (e.g., issue description), AND
2. No rule matches.

LLM outputs are classifications into a small **fixed taxonomy** (e.g., issue → `out_of_stock | damaged | wrong_sku | other`) with a confidence score. Below threshold goes to a human triage queue.

LLMs are never asked to decide *which action to take*. They are only asked to *categorize input* that will then drive a deterministic rule.

## Why

| Concern | Rule path | LLM path |
|---|---|---|
| Latency | <10ms | 500–2000ms |
| Cost | ~₹0 | ~₹0.05/msg |
| Reliability | 100% | ~95% on classified taxonomy |
| Auditability | Trivial — show the regex / token match | Hard — model output is opaque |
| Reproducibility | Deterministic | Non-deterministic across model versions |
| Safety on critical actions | Bounded by registry | Unbounded surface |

For `APPROVE` on a ₹2L invoice, none of the LLM-path numbers are acceptable. For "the box arrived dented," none of the rule-path numbers (other than zero coverage) work. So we split the path by *kind of input*, not by *kind of model*.

## What this looks like in practice

Inbound flow:

```
1. Normalize: lowercase, strip emojis, trim.
2. Lookup user's open pending_prompts (most recent first).
3. For each prompt's allowed intents, attempt rule match against tokens.
   - Reserved global intents: HELP, STATUS, CANCEL
   - Prompt-specific intents: DONE, ISSUE, APPROVE, REJECT, MORE, ...
4. On rule match → invoke action, audit, respond.
5. On no rule match:
   - If prompt allows free text (issue / note / description):
       → invoke LLM classifier with the prompt's taxonomy
       → if confidence ≥ threshold: invoke action with the classified label
       → else: park in human triage queue, respond "we got your message, will get back"
   - Else: respond "didn't understand; reply HELP for options"
```

## Consequences

**Positive:**
- 95%+ of operational messages never touch an LLM. They are free, fast, reliable.
- LLM usage is auditable: we log the prompt, the chosen label, the confidence, the model version. Replaying is possible.
- We can swap the LLM (GPT to Claude to open weights) without touching the action path.
- Cost predictability — LLM bill is bounded by the volume of fuzzy free-text inputs, which is small.

**Negative:**
- More work upfront — we maintain an intent registry per prompt kind. Mitigation: the registry is tiny (single-digit intents per prompt type) and the rules are easy to test.
- An ambiguous message that rule-doesn't-match but is in the taxonomy still gets handled by LLM — minor cost.

## Anti-patterns we explicitly reject

- **"Function calling" loop where the LLM picks an action.** Rejected. Indirect, slow, expensive, hard to audit, and the failure modes are exactly the ones our SME customers least want to debug.
- **LLM-generated outbound messages for transactional sends.** Rejected. WhatsApp templates are pre-approved by Meta; LLM-generated text would fail policy and our auditability requirement.
- **LLM-as-intent-extractor on every inbound.** Rejected — pure waste of latency and money for messages that say "DONE."
- **A general-purpose chatbot persona.** Rejected. We have specific workflows; we don't need a chat.

## Where LLMs *do* earn their keep

- Fuzzy classification fallback (above).
- Founder-facing summarization in the daily snapshot (already a small surface).
- Routing suggestions for unclassified tickets in CS.
- Maybe — eventually — a "search-the-platform" natural-language query helper in the web UI. Defer until basics are solid.

## Migration path

If model quality and cost change dramatically (cheap deterministic LLMs), we could relax the boundary: e.g., let an LLM handle multi-turn confirmation in places where rule paths get long. The architecture allows it because intents are a registry — we add an LLM-backed intent resolver as another strategy without replacing the action layer.

The current decision optimizes for **today's** reliability/cost/auditability trade-off, not a hypothetical future one.

## Rejected alternatives

**LLM-first with rule-based fallback.** The inverse of our choice. Rejected because the common case (DONE / APPROVE / DONE) is the deterministic one, and there's no scenario where running an LLM on those messages is better.

**No LLM at all, ever.** Considered. Rejected because issue-description classification at our volume is genuinely useful and the cost is tiny.

**Train a small custom classifier instead of using a hosted LLM.** Future option. Not the right place to spend Week-4 effort.
