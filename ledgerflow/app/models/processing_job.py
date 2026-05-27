import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.invoice import Invoice


class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


class JobType(str, enum.Enum):
    OCR_EXTRACTION = "ocr_extraction"
    DATA_VALIDATION = "data_validation"
    RECONCILIATION = "reconciliation"


class ProcessingJob(BaseModel):
    __tablename__ = "processing_jobs"

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    job_type: Mapped[JobType] = mapped_column(
        Enum(JobType, name="job_type"),
        nullable=False,
        index=True,
    )
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status"),
        default=JobStatus.QUEUED,
        nullable=False,
        index=True,
    )

    rq_job_id: Mapped[str | None] = mapped_column(String(200), unique=True, nullable=True, index=True)

    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_traceback: Mapped[str | None] = mapped_column(Text, nullable=True)

    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="processing_jobs")

    def __repr__(self) -> str:
        return f"<ProcessingJob {self.job_type} [{self.status}] attempt={self.attempt_count}>"
