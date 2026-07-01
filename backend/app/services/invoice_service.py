import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.core.events import DomainEvent, event_bus
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.invoice import Invoice, InvoiceStatus, PaymentStatus
from app.models.invoice_item import InvoiceItem
from app.models.processing_job import JobStatus, JobType, ProcessingJob
from app.models.user import User
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
        existing = self.invoice_repo.get_by_checksum(checksum, current_user.tenant_id)
        if existing and existing.status != InvoiceStatus.FAILED:
            raise ConflictError(
                f"Duplicate file detected. Existing invoice ID: {existing.id}"
            )

        invoice = Invoice(
            id=invoice_id,
            tenant_id=current_user.tenant_id,
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
            tenant_id=invoice.tenant_id,
            job_type=JobType.OCR_EXTRACTION,
        )
        self.db.add(job)
        self.db.flush()
        self.db.refresh(job)

        event_bus.publish(
            self.db,
            DomainEvent(
                name="invoice.uploaded",
                aggregate_type="invoice",
                aggregate_id=invoice.id,
                actor_id=current_user.id,
                tenant_id=invoice.tenant_id,
                payload={
                    "description": f"Invoice uploaded: {invoice.original_filename}",
                    "filename": invoice.original_filename,
                    "checksum": checksum,
                    "size_bytes": len(content),
                },
            ),
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

    def get_detail(self, invoice_id: uuid.UUID, tenant_id: uuid.UUID) -> Invoice:
        invoice = self.invoice_repo.get_with_items(invoice_id, tenant_id)
        if not invoice:
            raise NotFoundError("Invoice", str(invoice_id))
        return invoice

    def list(
        self,
        filters: InvoiceFilter,
        tenant_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Invoice], int]:
        offset = (page - 1) * page_size
        return self.invoice_repo.filter_paginated(
            filters, tenant_id=tenant_id, limit=page_size, offset=offset
        )

    def update(self, invoice_id: uuid.UUID, payload: InvoiceUpdate, current_user: User) -> Invoice:
        invoice = self.invoice_repo.get_for_tenant_or_raise(invoice_id, current_user.tenant_id)
        changed: dict = {}

        for field_name, value in payload.model_dump(exclude_none=True).items():
            if getattr(invoice, field_name) != value:
                setattr(invoice, field_name, value)
                changed[field_name] = str(value)

        if changed:
            self.invoice_repo.save(invoice)
            event_bus.publish(
                self.db,
                DomainEvent(
                    name="invoice.updated",
                    aggregate_type="invoice",
                    aggregate_id=invoice.id,
                    actor_id=current_user.id,
                    tenant_id=invoice.tenant_id,
                    payload={
                        "description": f"Invoice updated: {invoice_id}",
                        "changed_fields": changed,
                    },
                ),
            )
            self.db.commit()

        return invoice

    def approve(self, invoice_id: uuid.UUID, current_user: User) -> Invoice:
        invoice = self.invoice_repo.get_for_tenant_or_raise(invoice_id, current_user.tenant_id)
        if invoice.status != InvoiceStatus.PENDING_APPROVAL:
            raise ValidationError(
                f"Invoice is not pending approval (current status: {invoice.status})"
            )

        # A distinct status from VALIDATED/EXTRACTED: the gate step's `when`
        # only matches those two, so re-running the workflow after approval
        # doesn't immediately re-trigger the same gate and flip the invoice
        # straight back to pending_approval.
        invoice.status = InvoiceStatus.APPROVED
        self.invoice_repo.save(invoice)
        event_bus.publish(
            self.db,
            DomainEvent(
                name="invoice.approved",
                aggregate_type="invoice",
                aggregate_id=invoice.id,
                actor_id=current_user.id,
                tenant_id=invoice.tenant_id,
                payload={
                    "description": f"Invoice {invoice_id} approved by {current_user.email}",
                },
            ),
        )
        self.db.commit()

        # The gate parked the workflow at pending_approval; re-run it now that
        # the invoice is validated again so reconciliation actually happens.
        from app.workers.queue import enqueue_post_extraction_workflow_job
        enqueue_post_extraction_workflow_job(str(invoice.id))

        self.db.refresh(invoice)
        return invoice

    def reject(self, invoice_id: uuid.UUID, reason: str, current_user: User) -> Invoice:
        invoice = self.invoice_repo.get_for_tenant_or_raise(invoice_id, current_user.tenant_id)
        if invoice.status != InvoiceStatus.PENDING_APPROVAL:
            raise ValidationError(
                f"Invoice is not pending approval (current status: {invoice.status})"
            )

        invoice.status = InvoiceStatus.REJECTED
        invoice.extraction_notes = reason
        self.invoice_repo.save(invoice)
        event_bus.publish(
            self.db,
            DomainEvent(
                name="invoice.rejected",
                aggregate_type="invoice",
                aggregate_id=invoice.id,
                actor_id=current_user.id,
                tenant_id=invoice.tenant_id,
                payload={
                    "description": f"Invoice {invoice_id} rejected by {current_user.email}: {reason}",
                    "reason": reason,
                },
            ),
        )
        self.db.commit()
        self.db.refresh(invoice)
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

        # Associate with vendor (tenant-scoped: never cross-match another
        # tenant's vendor of the same name)
        if extracted.get("vendor_name"):
            vendor = self.vendor_repo.find_by_name(extracted["vendor_name"], invoice.tenant_id)
            if vendor:
                invoice.vendor_id = vendor.id

        # Persist line items
        for item_data in extracted.get("line_items", []):
            item = InvoiceItem(
                invoice_id=invoice.id,
                tenant_id=invoice.tenant_id,
                description=item_data.get("description", ""),
                line_total=Decimal(item_data["line_total"]) if item_data.get("line_total") else None,
                sequence_number=item_data.get("sequence_number", 0),
            )
            self.db.add(item)

        invoice.status = InvoiceStatus.EXTRACTED
        if job:
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc)
            job.result = {"fields_extracted": len(extracted)}

        event_bus.publish(
            self.db,
            DomainEvent(
                name="invoice.extracted",
                aggregate_type="invoice",
                aggregate_id=invoice.id,
                tenant_id=invoice.tenant_id,
                payload={
                    "description": f"OCR extraction completed for invoice {invoice_id}",
                    "confidence": extracted.get("ocr_confidence"),
                },
            ),
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
            job.status = JobStatus.FAILED
            job.error_message = error
            job.completed_at = datetime.now(timezone.utc)
        tenant_id = invoice.tenant_id if invoice else (job.tenant_id if job else None)
        if tenant_id is not None:
            event_bus.publish(
                self.db,
                DomainEvent(
                    name="invoice.processing_failed",
                    aggregate_type="invoice",
                    aggregate_id=invoice_id,
                    tenant_id=tenant_id,
                    payload={
                        "description": f"Processing failed: {error[:200]}",
                        "error": error[:200],
                    },
                ),
            )
        self.db.commit()
