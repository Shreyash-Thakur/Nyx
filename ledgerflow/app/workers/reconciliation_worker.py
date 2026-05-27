"""RQ job: automatic reconciliation triggered after OCR extraction."""
import uuid

from app.core.logging import configure_logging, get_logger
from app.database import SessionLocal
from app.models.invoice import InvoiceStatus
from app.repositories.invoice_repository import InvoiceRepository

configure_logging()
logger = get_logger(__name__)


def auto_reconcile(invoice_id: str) -> dict:
    inv_uuid = uuid.UUID(invoice_id)
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

        # System user is represented by None (system action)
        from app.services.reconciliation_service import ReconciliationService
        from app.schemas.reconciliation import ReconciliationRequest

        svc = ReconciliationService(db)

        class _SystemUser:
            id = uuid.UUID("00000000-0000-0000-0000-000000000001")
            role = "system"

        record = svc.reconcile(
            ReconciliationRequest(
                invoice_id=inv_uuid,
                reference_document_type="auto",
                notes="Automatically triggered after OCR extraction",
            ),
            _SystemUser(),  # type: ignore[arg-type]
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
        db.close()
