"""Event bus foundation (ADR-0002).

In-process synchronous bus backed by a durable, replayable ``events`` table.
publish() persists the event in the caller's transaction (transactional
outbox) and then notifies in-process subscribers; a failing subscriber must
not break the publisher or other subscribers.
"""
import uuid

from app.core.events.bus import DomainEvent, EventBus
from app.models.event import Event


def test_publish_persists_event_row(db):
    bus = EventBus()
    ev = DomainEvent(
        name="test.created",
        aggregate_type="thing",
        aggregate_id=uuid.uuid4(),
        payload={"k": "v"},
    )

    bus.publish(db, ev)
    db.commit()

    rows = db.query(Event).filter(Event.name == "test.created").all()
    assert len(rows) == 1
    assert rows[0].payload == {"k": "v"}
    assert rows[0].aggregate_type == "thing"


def test_publish_notifies_matching_and_wildcard_subscribers(db):
    bus = EventBus()
    seen = []
    bus.subscribe("test.created", lambda e, s: seen.append(("exact", e.name)))
    bus.subscribe("*", lambda e, s: seen.append(("wildcard", e.name)))
    bus.subscribe("other.event", lambda e, s: seen.append(("nomatch", e.name)))

    bus.publish(db, DomainEvent(name="test.created"))

    assert ("exact", "test.created") in seen
    assert ("wildcard", "test.created") in seen
    assert ("nomatch", "test.created") not in seen


def test_failing_subscriber_is_isolated(db):
    bus = EventBus()
    calls = []

    def boom(e, s):
        raise RuntimeError("subscriber blew up")

    bus.subscribe("test.created", boom)
    bus.subscribe("test.created", lambda e, s: calls.append("ran"))

    # Must not raise, and the second subscriber must still run.
    row = bus.publish(db, DomainEvent(name="test.created"))
    db.commit()

    assert calls == ["ran"]
    assert db.get(Event, row.id) is not None


def test_upload_emits_invoice_uploaded_event(db, admin_user, mocker):
    """Integration: the invoice upload flow writes a durable domain event."""
    import asyncio

    mocker.patch(
        "app.services.invoice_service.StorageService.save",
        return_value=("invoices/2026/06/x/t.pdf", "checksum-evt"),
    )
    mocker.patch("app.services.invoice_service.enqueue_ocr_job", return_value=None)

    from app.services.invoice_service import InvoiceService

    class _Up:
        filename = "t.pdf"
        content_type = "application/pdf"

        async def read(self):
            return b"%PDF-1.4 x"

    inv = asyncio.run(InvoiceService(db).upload(_Up(), admin_user))

    events = db.query(Event).filter(Event.aggregate_id == inv.id).all()
    names = {e.name for e in events}
    assert "invoice.uploaded" in names
