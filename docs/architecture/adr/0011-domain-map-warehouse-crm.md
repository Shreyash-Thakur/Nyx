# ADR 0011 — Domain map revision: Warehouse split from Inventory; CRM admitted as a narrow customer registry

**Status:** Accepted
**Date:** 2026-07-08
**Amends:** `00-vision.md` non-goals (CRM entry) · `02-modules.md` module roster

## Context

The original module roster had five business modules: Accounts, Operations,
Inventory, Customer Service, Founder Intelligence. Two pressures emerged as
the platform scope firmed up:

1. **Inventory conflated two bounded contexts.** *Stock truth* (quantities,
   reservations, thresholds — consumed by Operations in milliseconds) and
   *physical work* (transfers, picking, WhatsApp `DONE` confirmations —
   performed by warehouse staff over hours) have different users, different
   consistency needs, and different interfaces. The original `inv_transfers` +
   `inv_warehouses` + task-routing design was already Warehouse-shaped code
   wearing an Inventory prefix.
2. **Customer identity had no owner.** Operations receives customers inside
   order payloads; Customer Service had its own `cs_customers`. Two modules
   each owning a partial customer is the textbook path to identity drift —
   and the vision's blanket "no CRM" non-goal was blocking the fix, because
   the non-goal conflated *customer identity* with *sales-pipeline CRM*.

## Decision

1. **Split Warehouse (`whs_`) out of Inventory (`inv_`).**
   - Inventory keeps: SKUs, stock levels, the append-only movement ledger,
     reservations, reorder thresholds. It owns **state**.
   - Warehouse takes: warehouse master data, transfers (+ items), pick tasks,
     floor-issue capture. It owns **work**.
   - The contract between them is events only: Warehouse completes a transfer
     → `whs.transfer.completed` → Inventory records the movement. Neither
     writes the other's tables.
2. **Admit CRM (`crm_`) as a customer registry, and nothing more.**
   - CRM owns customer identity (`crm_customers`), channel-identity links,
     rule-based segments, notes, and the cross-module timeline.
   - `cs_customers` from the original CS design is superseded; CS and
     Operations reference `crm_customers.id`.
   - **The vision non-goal is narrowed, not repealed:** lead capture, sales
     pipeline, deal stages, marketing automation, and campaign sends remain
     permanently out of scope. A tenant who wants a funnel gets an
     integration to a real CRM, not scope creep here.

## Consequences

**Positive:** each domain has one owner for each concept — quantities
(Inventory), physical work (Warehouse), customer identity (CRM); the
WhatsApp-task showcase (transfers, picking) lives in one module built around
that interaction; identity dedup/merge logic exists once.

**Negative:** seven business modules instead of five — more folders, more
event types, and one more chance to draw a boundary wrong. Mitigated by the
boundary rules being written down (`DOMAIN_MODEL.md` §3–4, §6) and by build
order: Inventory + Warehouse are built together in one milestone, so the seam
is tested the day it exists.

**Documentation debt accepted:** `00-vision.md` and `02-modules.md` still show
the five-module roster and the blanket CRM non-goal. They are amended by this
ADR and by `DOMAIN_MODEL.md` rather than edited in place — original documents
record what was decided then; ADRs record how decisions changed.
`DOMAIN_MODEL.md` is authoritative for the domain map.

## Rejected alternatives

**Keep transfers inside Inventory.** Rejected — the module would own both a
millisecond-latency availability API and hour-scale human task flows; its
`__init__.py` interface and its failure modes stop being coherent.

**A full CRM module (pipeline, campaigns).** Rejected, permanently. It is a
different product, it dilutes the ops-platform focus, and it is the explicit
scope-death scenario the vision warns about.

**Customer identity inside Customer Service.** Rejected — Operations meets a
customer (first order) before CS does (first complaint); identity must sit
below both.

**A `party` model in core (customers + vendors unified).** Rejected as
over-abstraction: vendors are Accounts-shaped, customers are CRM-shaped, and
nothing in the roadmap needs them unified.
