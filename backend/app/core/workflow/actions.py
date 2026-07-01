"""Built-in workflow actions and the canonical Accounts workflow.

This is the first step of migrating the invoice lifecycle off hand-chained
service calls and onto declarative steps (roadmap W2). The reconcile action
reuses the existing ReconciliationService and the system principal, so it
behaves identically to the auto-reconcile worker.
"""
from __future__ import annotations

import uuid
from typing import Callable

from app.config import settings
from app.core.system import ensure_system_user
from app.core.workflow.engine import ActionRegistry, WorkflowDefinition, WorkflowStep

action_registry = ActionRegistry()


@action_registry.register("accounts.check_approval_gate")
def check_approval_gate(params: dict, ctx: dict, db) -> dict:
    """Hold the invoice at PENDING_APPROVAL instead of reconciling it if its
    amount exceeds the founder-approval threshold (Priority 1: human approval
    step). Setting ``status`` in the returned context is what makes the
    ``reconcile`` step's ``when`` clause skip -- no change to the condition
    language needed."""
    from app.core.events import DomainEvent, event_bus
    from app.models.invoice import Invoice, InvoiceStatus

    invoice_id = uuid.UUID(str(ctx["invoice_id"]))
    invoice = db.get(Invoice, invoice_id)
    threshold = settings.FOUNDER_APPROVAL_THRESHOLD_INR

    if invoice.total_amount is None or float(invoice.total_amount) <= threshold:
        return {}

    invoice.status = InvoiceStatus.PENDING_APPROVAL
    db.flush()
    event_bus.publish(
        db,
        DomainEvent(
            name="invoice.approval_required",
            aggregate_type="invoice",
            aggregate_id=invoice.id,
            tenant_id=invoice.tenant_id,
            payload={
                "description": (
                    f"Invoice {invoice.invoice_number or invoice.id} requires approval "
                    f"(amount {invoice.total_amount} > threshold {threshold})"
                ),
                "amount": str(invoice.total_amount),
                "threshold": threshold,
            },
        ),
    )
    return {"status": InvoiceStatus.PENDING_APPROVAL.value}


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
    """After OCR: gate high-value invoices behind approval, then reconcile."""
    return WorkflowDefinition(
        name="invoice_post_extraction",
        steps=[
            WorkflowStep(
                id="check_approval_gate",
                action="accounts.check_approval_gate",
                when={"field": "status", "in": ["extracted", "validated"]},
            ),
            WorkflowStep(
                id="reconcile",
                action="accounts.reconcile_invoice",
                when={"field": "status", "in": ["extracted", "validated", "approved"]},
            ),
        ],
    )


# Looked up by workflow_name (WorkflowInstance.workflow_name) so a failed
# instance can be retried without the caller needing to know which builder
# function produced its definition.
WORKFLOW_DEFINITIONS: dict[str, Callable[[], WorkflowDefinition]] = {
    "invoice_post_extraction": build_invoice_post_extraction,
}
