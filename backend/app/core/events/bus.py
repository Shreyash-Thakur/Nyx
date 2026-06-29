"""In-process event bus with a durable event log (ADR-0002).

``publish`` persists the event row in the caller's session (a transactional
outbox: the event commits atomically with the state change that produced it),
then notifies in-process subscribers synchronously. Subscriber failures are
isolated and logged so one bad handler cannot break the publisher or the other
handlers.

The second tier from ADR-0002 — async Redis fan-out for cross-process handlers
— is deferred; the durable log makes it a later, additive change (a relay that
reads unprocessed event rows).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Callable

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.tenancy import DEFAULT_TENANT_ID

logger = get_logger(__name__)

WILDCARD = "*"


@dataclass
class DomainEvent:
    name: str
    aggregate_type: str | None = None
    aggregate_id: uuid.UUID | None = None
    actor_id: uuid.UUID | None = None
    tenant_id: uuid.UUID = DEFAULT_TENANT_ID
    payload: dict | None = None


Handler = Callable[[DomainEvent, Session], None]


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[Handler]] = {}

    def subscribe(self, event_name: str, handler: Handler) -> None:
        """Register a handler for an event name, or ``"*"`` for all events."""
        self._subscribers.setdefault(event_name, []).append(handler)

    def reset(self) -> None:
        self._subscribers.clear()

    def publish(self, db: Session, event: DomainEvent):
        """Persist the event in the caller's transaction, then dispatch.

        Returns the persisted Event row. The caller is responsible for the
        surrounding commit so the event and the state change land together.
        """
        from app.models.event import Event

        row = Event(
            tenant_id=event.tenant_id,
            name=event.name,
            aggregate_type=event.aggregate_type,
            aggregate_id=event.aggregate_id,
            actor_id=event.actor_id,
            payload=event.payload,
        )
        db.add(row)
        db.flush()

        for key in (event.name, WILDCARD):
            for handler in self._subscribers.get(key, []):
                try:
                    handler(event, db)
                except Exception as exc:  # isolate subscriber failures
                    logger.error(
                        "event_handler_failed",
                        event_name=event.name,
                        handler=getattr(handler, "__name__", repr(handler)),
                        error=str(exc),
                    )
        return row


# Process-wide singleton used by services. Tests that exercise bus mechanics
# construct their own EventBus() so subscriptions don't leak across tests.
event_bus = EventBus()
