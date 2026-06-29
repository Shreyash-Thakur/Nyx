"""RQ job: automatic reconciliation triggered after OCR extraction."""
import uuid

from sqlalchemy.orm import Session

from app.core.logging import configure_logging, get_logger
from app.core.system import ensure_system_user
from app.database import SessionLocal
from app.models.invoice import InvoiceStatus
from app.repositories.invoice_repository import InvoiceRepository

configure_logging()
logger = get_logger(__name__)


def auto_reconcile(invoice_id: str, db: Session | None = None) -> dict:
    """Reconcile an invoice on behalf of the system principal.

    ``db`` is injectable so the job logic can be tested against a session;
    in production it is omitted and the worker owns its own session.
    """
    inv_uuid = uuid.UUID(invoice_id)
    own_session = db is None
    if db is None:
        db = SessionLocal()
    try:
        invoice_repo = InvoiceRepository(db)
        invoice = invoice_repo.get_or_raise(inv_uuid)

        if invoice.status not in (InvoiceStatus.EXTRACTED, InvoiceStatus.VALIDATED):
            logger.info(
                "auto_reconcile_skipped",
                invoice_id=invoice_id,
                status=invoice.status.value,
            )
            return {"status": "skipped", "reason": invoice.status.value}

        from app.schemas.reconciliation import ReconciliationRequest
        from app.services.reconciliation_service import ReconciliationService

        system_user = ensure_system_user(db)
        svc = ReconciliationService(db)

        record = svc.reconcile(
            ReconciliationRequest(
                invoice_id=inv_uuid,
                reference_document_type="auto",
                notes="Automatically triggered after OCR extraction",
            ),
            system_user,
        )

        logger.info(
            "auto_reconcile_done",
            invoice_id=invoice_id,
            status=record.status.value,
            confidence=record.confidence_score,
        )
        return {"status": record.status.value, "confidence": record.confidence_score}

    except Exception as exc:
        logger.error("auto_reconcile_failed", invoice_id=invoice_id, error=str(exc))
        raise
    finally:
        if own_session:
            db.close()
