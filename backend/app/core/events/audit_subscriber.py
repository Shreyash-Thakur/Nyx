"""Audit log as an event-bus subscriber (TD-6).

Before this, every audit-worthy state change was written twice: once as a
direct ``audit_repo.log()`` call and once as a ``DomainEvent`` publish, with
no relationship between the two beyond "someone remembered to add both."
That is exactly the drift TD-6 warned about — the two logs could (and did)
diverge, since only three of nine audit call sites also published an event.

Audit is now a ``"*"`` subscriber: every event on the bus is inspected, and
events with a known audit mapping produce exactly one ``AuditLog`` row. The
event log and the audit trail are now two views over the same write.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.events.bus import DomainEvent, event_bus
from app.models.audit_log import AuditEventType
from app.repositories.audit_repository import AuditRepository

# Not every domain event is audit-worthy by name alone (and not every event
# type has been migrated to carry a human description yet); unmapped events
# are silently skipped rather than guessed at.
EVENT_TO_AUDIT_TYPE: dict[str, AuditEventType] = {
    "invoice.uploaded": AuditEventType.INVOICE_UPLOADED,
    "invoice.extracted": AuditEventType.INVOICE_PROCESSING_COMPLETED,
    "invoice.updated": AuditEventType.INVOICE_UPDATED,
    "invoice.processing_failed": AuditEventType.INVOICE_PROCESSING_FAILED,
    "invoice.duplicate_detected": AuditEventType.INVOICE_DUPLICATE_DETECTED,
    "invoice.approval_required": AuditEventType.INVOICE_APPROVAL_REQUIRED,
    "invoice.approved": AuditEventType.INVOICE_APPROVED,
    "invoice.rejected": AuditEventType.INVOICE_REJECTED,
    "reconciliation.completed": AuditEventType.RECONCILIATION_STARTED,
    "reconciliation.resolved": AuditEventType.RECONCILIATION_RESOLVED,
    "vendor.created": AuditEventType.VENDOR_CREATED,
    "vendor.updated": AuditEventType.VENDOR_UPDATED,
    "user.logged_in": AuditEventType.USER_LOGIN,
    "user.created": AuditEventType.USER_CREATED,
    "user.password_changed": AuditEventType.PASSWORD_CHANGED,
}


def on_any_event(event: DomainEvent, db: Session) -> None:
    audit_type = EVENT_TO_AUDIT_TYPE.get(event.name)
    if audit_type is None:
        return

    payload = dict(event.payload or {})
    description = payload.pop("description", event.name)
    ip_address = payload.pop("ip_address", None)
    invoice_id = event.aggregate_id if event.aggregate_type == "invoice" else None

    AuditRepository(db).log(
        audit_type,
        description,
        tenant_id=event.tenant_id,
        user_id=event.actor_id,
        invoice_id=invoice_id,
        extra_data=payload or None,
        ip_address=ip_address,
    )


_registered = False


def register() -> None:
    """Subscribe the audit handler to every event. Idempotent: calling it more
    than once (e.g. multiple app reloads sharing the process-wide bus) does
    not create duplicate audit rows per event."""
    global _registered
    if _registered:
        return
    event_bus.subscribe("*", on_any_event)
    _registered = True
