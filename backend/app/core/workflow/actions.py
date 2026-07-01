"""Built-in workflow actions and the canonical Accounts workflow.

This is the first step of migrating the invoice lifecycle off hand-chained
service calls and onto declarative steps (roadmap W2). The reconcile action
reuses the existing ReconciliationService and the system principal, so it
behaves identically to the auto-reconcile worker.
"""
from __future__ import annotations

import uuid

from app.core.system import ensure_system_user
from app.core.workflow.engine import ActionRegistry, WorkflowDefinition, WorkflowStep

action_registry = ActionRegistry()


@action_registry.register("accounts.reconcile_invoice")
def reconcile_invoice(params: dict, ctx: dict, db) -> dict:
    """Reconcile the invoice named in ``ctx['invoice_id']`` as the system user."""
    from app.schemas.reconciliation import ReconciliationRequest
    from app.services.reconciliation_service import ReconciliationService

    invoice_id = uuid.UUID(str(ctx["invoice_id"]))
    system_user = ensure_system_user(db)
    record = ReconciliationService(db).reconcile(
        ReconciliationRequest(
            invoice_id=invoice_id,
            reference_document_type="workflow",
            notes="Reconciled by invoice_post_extraction workflow",
        ),
        system_user,
    )
    return {"reconciliation_status": record.status.value}


def build_invoice_post_extraction() -> WorkflowDefinition:
    """After OCR: reconcile the invoice (only once it is actually extracted)."""
    return WorkflowDefinition(
        name="invoice_post_extraction",
        steps=[
            WorkflowStep(
                id="reconcile",
                action="accounts.reconcile_invoice",
                when={"field": "status", "in": ["extracted", "validated"]},
            ),
        ],
    )
