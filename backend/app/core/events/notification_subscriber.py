"""In-app notifications as event-bus subscribers.

The minimal notification engine: no email/WhatsApp channel (real external
integrations, out of scope here), just an in-app row created for the right
recipient(s) when specific events fire. Unlike the audit subscriber this is
deliberately NOT a wildcard subscription -- only a curated set of events are
notification-worthy, and each has a different recipient rule.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.events.bus import DomainEvent, event_bus
from app.models.invoice import Invoice
from app.models.notification import Notification
from app.models.user import User, UserRole


def _notify(db: Session, *, tenant_id, user_id, title: str, body: str, event_name: str, invoice_id=None) -> None:
    db.add(
        Notification(
            tenant_id=tenant_id,
            user_id=user_id,
            title=title,
            body=body,
            event_name=event_name,
            invoice_id=invoice_id,
        )
    )


def _admins_for_tenant(db: Session, tenant_id) -> list[User]:
    return list(
        db.scalars(
            select(User).where(User.tenant_id == tenant_id, User.role == UserRole.ADMIN)
        ).all()
    )


def _verifiers_for_tenant(db: Session, tenant_id) -> list[User]:
    """Users who can act on the verification queue: accountants do the data
    entry, admins can do anything. Mirrors the INVOICE_WRITE permission."""
    return list(
        db.scalars(
            select(User).where(
                User.tenant_id == tenant_id,
                User.role.in_((UserRole.ADMIN, UserRole.ACCOUNTANT)),
            )
        ).all()
    )


def on_invoice_needs_verification(event: DomainEvent, db: Session) -> None:
    body = (event.payload or {}).get("description", event.name)
    for user in _verifiers_for_tenant(db, event.tenant_id):
        _notify(
            db, tenant_id=event.tenant_id, user_id=user.id,
            title="Invoice needs verification", body=body,
            event_name=event.name, invoice_id=event.aggregate_id,
        )


def on_invoice_approval_required(event: DomainEvent, db: Session) -> None:
    body = (event.payload or {}).get("description", event.name)
    for admin in _admins_for_tenant(db, event.tenant_id):
        _notify(
            db, tenant_id=event.tenant_id, user_id=admin.id,
            title="Invoice needs your approval", body=body,
            event_name=event.name, invoice_id=event.aggregate_id,
        )


def on_reconciliation_completed(event: DomainEvent, db: Session) -> None:
    if (event.payload or {}).get("status") != "discrepancy":
        return
    body = (event.payload or {}).get("description", event.name)
    for admin in _admins_for_tenant(db, event.tenant_id):
        _notify(
            db, tenant_id=event.tenant_id, user_id=admin.id,
            title="Reconciliation discrepancy found", body=body,
            event_name=event.name, invoice_id=event.aggregate_id,
        )


def on_invoice_rejected(event: DomainEvent, db: Session) -> None:
    invoice = db.get(Invoice, event.aggregate_id) if event.aggregate_id else None
    if invoice is None:
        return
    body = (event.payload or {}).get("description", event.name)
    _notify(
        db, tenant_id=event.tenant_id, user_id=invoice.uploaded_by,
        title="Your invoice was rejected", body=body,
        event_name=event.name, invoice_id=invoice.id,
    )


_registered = False


def register() -> None:
    """Idempotent: safe to call more than once against the shared process-wide
    bus without creating duplicate notifications per event."""
    global _registered
    if _registered:
        return
    event_bus.subscribe("invoice.needs_verification", on_invoice_needs_verification)
    event_bus.subscribe("invoice.approval_required", on_invoice_approval_required)
    event_bus.subscribe("reconciliation.completed", on_reconciliation_completed)
    event_bus.subscribe("invoice.rejected", on_invoice_rejected)
    _registered = True
