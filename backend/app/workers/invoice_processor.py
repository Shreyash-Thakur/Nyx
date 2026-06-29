"""RQ job: OCR extraction for a single invoice.

Runs in the worker process (not the API process). Creates its own DB session.
"""
import traceback
import uuid
from datetime import datetime, timezone

from app.core.logging import configure_logging, get_logger
from app.database import SessionLocal
from app.models.processing_job import JobStatus, ProcessingJob
from app.services.ocr_service import OCRService
from app.services.storage_service import StorageService

configure_logging()
logger = get_logger(__name__)

_ocr_service = OCRService()
_storage_service = StorageService()


def process_invoice(invoice_id: str, job_id: str) -> dict:
    inv_uuid = uuid.UUID(invoice_id)
    job_uuid = uuid.UUID(job_id)

    db = SessionLocal()
    try:
        job = db.get(ProcessingJob, job_uuid)
        if not job:
            raise ValueError(f"ProcessingJob {job_id} not found")

        job.status = JobStatus.STARTED
        job.started_at = datetime.now(timezone.utc)
        job.attempt_count += 1
        db.commit()

        # Lazy import to avoid circular deps at module load time
        from app.repositories.invoice_repository import InvoiceRepository
        invoice_repo = InvoiceRepository(db)
        invoice = invoice_repo.get_or_raise(inv_uuid)

        logger.info("ocr_started", invoice_id=invoice_id, attempt=job.attempt_count)

        pdf_bytes = _storage_service.read_sync(invoice.storage_path)

        extracted = _ocr_service.extract_from_pdf(pdf_bytes)

        result_dict = {
            "invoice_number": extracted.invoice_number,
            "vendor_name": extracted.vendor_name,
            "invoice_date": extracted.invoice_date,
            "due_date": extracted.due_date,
            "subtotal": extracted.subtotal,
            "cgst_amount": extracted.cgst_amount,
            "sgst_amount": extracted.sgst_amount,
            "igst_amount": extracted.igst_amount,
            "total_tax": extracted.total_tax,
            "total_amount": extracted.total_amount,
            "currency": extracted.currency,
            "line_items": extracted.line_items,
            "ocr_confidence": extracted.confidence,
            "raw_ocr_text": extracted.raw_text,
        }

        from app.services.invoice_service import InvoiceService
        svc = InvoiceService(db)
        svc.apply_extracted_data(inv_uuid, result_dict, job_uuid)

        # Auto-trigger reconciliation if invoice_number extracted
        if extracted.invoice_number:
            from app.workers.queue import enqueue_reconciliation_job
            enqueue_reconciliation_job(invoice_id)

        logger.info("ocr_completed", invoice_id=invoice_id, confidence=extracted.confidence)
        return {"status": "completed", "confidence": extracted.confidence}

    except Exception as exc:
        logger.error("ocr_failed", invoice_id=invoice_id, error=str(exc))
        tb = traceback.format_exc()

        try:
            job = db.get(ProcessingJob, job_uuid)
            if job:
                job.status = JobStatus.FAILED
                job.error_message = str(exc)
                job.error_traceback = tb[:5000]
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
        except Exception:
            pass

        from app.services.invoice_service import InvoiceService
        try:
            svc = InvoiceService(db)
            svc.mark_failed(inv_uuid, job_uuid, str(exc))
        except Exception:
            pass

        raise
    finally:
        db.close()
