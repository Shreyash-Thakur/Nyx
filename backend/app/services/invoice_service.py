import uuid
from decimal import Decimal

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.audit_log import AuditEventType
from app.models.invoice import Invoice, InvoiceStatus, PaymentStatus
from app.models.invoice_item import InvoiceItem
from app.models.processing_job import JobType, ProcessingJob
from app.models.user import User
from app.repositories.audit_repository import AuditRepository
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.vendor_repository import VendorRepository
from app.schemas.invoice import InvoiceFilter, InvoiceUpdate
from app.services.storage_service import StorageService
from app.workers.queue import enqueue_ocr_job

logger = get_logger(__name__)

ALLOWED_CONTENT_TYPES = {"application/pdf", "image/png", "image/jpeg", "image/tiff"}


class InvoiceService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.invoice_repo = InvoiceRepository(db)
        self.vendor_repo = VendorRepository(db)
        self.audit_repo = AuditRepository(db)
        self.storage = StorageService()

    async def upload(self, file: UploadFile, current_user: User) -> Invoice:
        content_type = file.content_type or "application/pdf"
        if content_type not in ALLOWED_CONTENT_TYPES:
            raise ValidationError(f"Unsupported file type: {content_type}")

        content = await file.read()
        if len(content) > settings.max_upload_bytes:
            raise ValidationError(
                f"File too large: {len(content)} bytes (max {settings.MAX_UPLOAD_SIZE_MB}MB)"
            )
        if len(content) == 0:
            raise ValidationError("Uploaded file is empty")

        invoice_id = uuid.uuid4()
        storage_path, checksum = await self.storage.save(
            content, file.filename or "invoice.pdf", invoice_id, content_type
        )

        # Idempotency: reject identical file already in system
        existing = self.invoice_repo.get_by_checksum(checksum)
        if existing and existing.status != InvoiceStatus.FAILED:
            raise ConflictError(
                f"Duplicate file detected. Existing invoice ID: {existing.id}"
            )

        invoice = Invoice(
            id=invoice_id,
            original_filename=file.filename or "invoice.pdf",
            storage_path=storage_path,
            file_size_bytes=len(content),
            content_type=content_type,
            checksum=checksum,
            status=InvoiceStatus.UPLOADED,
            uploaded_by=current_user.id,
        )
        self.invoice_repo.save(invoice)

        job = ProcessingJob(
            invoice_id=invoice.id,
            job_type=JobType.OCR_EXTRACTION,
        )
        self.db.add(job)
        self.db.flush()
        self.db.refresh(job)

        self.audit_repo.log(
            AuditEventType.INVOICE_UPLOADED,
            f"Invoice uploaded: {invoice.original_filename}",
            user_id=current_user.id,
            invoice_id=invoice.id,
            extra_data={"size_bytes": len(content), "checksum": checksum},
        )
        # Mark queued and commit BEFORE dispatch so the job row is visible to the
        # worker. In inline mode the job runs synchronously during dispatch and
        # advances the invoice itself, so we must not write status afterwards.
        invoice.status = InvoiceStatus.QUEUED
        self.db.commit()

        rq_id = enqueue_ocr_job(str(invoice.id), str(job.id))
        if rq_id:
            # Targeted column update: never clobber fields the (inline) worker
            # may have written to the same job row on another session.
            self.db.query(ProcessingJob).filter(ProcessingJob.id == job.id).update(
                {ProcessingJob.rq_job_id: rq_id}
            )
            self.db.commit()

        # Reflect whatever state the inline worker advanced the invoice to.
        self.db.refresh(invoice)
        logger.info("invoice_uploaded", invoice_id=str(invoice.id), filename=invoice.original_filename)
        return invoice

    def get_detail(self, invoice_id: uuid.UUID) -> Invoice:
        invoice = self.invoice_repo.get_with_items(invoice_id)
        if not invoice:
            raise NotFoundError("Invoice", str(invoice_id))
        return invoice

    def list(
        self,
        filters: InvoiceFilter,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Invoice], int]:
        offset = (page - 1) * page_size
        return self.invoice_repo.filter_paginated(filters, limit=page_size, offset=offset)

    def update(self, invoice_id: uuid.UUID, payload: InvoiceUpdate, current_user: User) -> Invoice:
        invoice = self.invoice_repo.get_or_raise(invoice_id)
        changed: dict = {}

        for field_name, value in payload.model_dump(exclude_none=True).items():
            if getattr(invoice, field_name) != value:
                setattr(invoice, field_name, value)
                changed[field_name] = str(value)

        if changed:
            self.invoice_repo.save(invoice)
            self.audit_repo.log(
                AuditEventType.INVOICE_UPDATED,
                f"Invoice updated: {invoice_id}",
                user_id=current_user.id,
                invoice_id=invoice.id,
                extra_data={"changed_fields": changed},
            )
            self.db.commit()

        return invoice

    def apply_extracted_data(
        self,
        invoice_id: uuid.UUID,
        extracted: dict,
        job_id: uuid.UUID,
    ) -> Invoice:
        """Called by the RQ worker after OCR completes."""
        invoice = self.invoice_repo.get_or_raise(invoice_id)
        job = self.db.get(ProcessingJob, job_id)

        for field_name in (
            "invoice_number", "invoice_date", "due_date",
            "subtotal", "cgst_amount", "sgst_amount", "igst_amount",
            "total_tax", "total_amount", "currency",
            "ocr_confidence", "raw_ocr_text",
        ):
            if field_name in extracted and extracted[field_name] is not None:
                setattr(invoice, field_name, extracted[field_name])

        # Associate with vendor
        if extracted.get("vendor_name"):
            vendor = self.vendor_repo.find_by_name(extracted["vendor_name"])
            if vendor:
                invoice.vendor_id = vendor.id

        # Persist line items
        for item_data in extracted.get("line_items", []):
            item = InvoiceItem(
                invoice_id=invoice.id,
                description=item_data.get("description", ""),
                line_total=Decimal(item_data["line_total"]) if item_data.get("line_total") else None,
                sequence_number=item_data.get("sequence_number", 0),
            )
            self.db.add(item)

        invoice.status = InvoiceStatus.EXTRACTED
        if job:
            from datetime import datetime, timezone
            job.status = __import__("app.models.processing_job", fromlist=["JobStatus"]).JobStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc)
            job.result = {"fields_extracted": len(extracted)}

        self.audit_repo.log(
            AuditEventType.INVOICE_PROCESSING_COMPLETED,
            f"OCR extraction completed for invoice {invoice_id}",
            invoice_id=invoice.id,
            extra_data={"confidence": extracted.get("ocr_confidence")},
        )
        self.db.commit()
        return invoice

    def mark_failed(self, invoice_id: uuid.UUID, job_id: uuid.UUID, error: str) -> None:
        invoice = self.invoice_repo.get(invoice_id)
        job = self.db.get(ProcessingJob, job_id)
        if invoice:
            invoice.status = InvoiceStatus.FAILED
            invoice.extraction_notes = error
        if job:
            from datetime import datetime, timezone
            from app.models.processing_job import JobStatus
            job.status = JobStatus.FAILED
            job.error_message = error
            job.completed_at = datetime.now(timezone.utc)
        self.audit_repo.log(
            AuditEventType.INVOICE_PROCESSING_FAILED,
            f"Processing failed: {error[:200]}",
            invoice_id=invoice_id,
        )
        self.db.commit()
