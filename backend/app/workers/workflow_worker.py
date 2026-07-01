"""RQ job: advance the ``invoice_post_extraction`` workflow (ADR-0003).

Replaces the old bespoke ``reconciliation_worker.auto_reconcile`` job. Before
this, the real pipeline never called the workflow engine at all -- it was
built, tested, and then bypassed by a second, nearly-identical hand-written
path (a worker function that also checked invoice status, fetched the system
user, and called ``ReconciliationService.reconcile`` directly). The workflow
engine's ``accounts.reconcile_invoice`` action already does exactly that; this
worker is now the only thing that decides what happens after OCR extraction,
and it decides it by running the workflow, not by re-implementing the logic.
"""
import uuid

from sqlalchemy.orm import Session

from app.core.logging import configure_logging, get_logger
from app.core.workflow.actions import action_registry, build_invoice_post_extraction
from app.core.workflow.engine import WorkflowRunner
from app.database import SessionLocal
from app.repositories.invoice_repository import InvoiceRepository

configure_logging()
logger = get_logger(__name__)


def run_invoice_post_extraction(invoice_id: str, db: Session | None = None) -> dict:
    """Advance the post-extraction workflow for one invoice.

    ``db`` is injectable so the job logic can be tested against a session; in
    production it is omitted and the worker owns its own session.
    """
    inv_uuid = uuid.UUID(invoice_id)
    own_session = db is None
    if db is None:
        db = SessionLocal()
    try:
        invoice = InvoiceRepository(db).get_or_raise(inv_uuid)

        instance = WorkflowRunner(action_registry).run(
            db,
            build_invoice_post_extraction(),
            context={"invoice_id": invoice_id, "status": invoice.status.value},
            tenant_id=invoice.tenant_id,
        )
        db.commit()

        logger.info(
            "invoice_post_extraction_done",
            invoice_id=invoice_id,
            workflow_status=instance.status,
            current_step=instance.current_step,
        )
        return {"workflow_status": instance.status, "context": instance.context}
    except Exception as exc:
        logger.error("invoice_post_extraction_failed", invoice_id=invoice_id, error=str(exc))
        raise
    finally:
        if own_session:
            db.close()
