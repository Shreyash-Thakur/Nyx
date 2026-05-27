"""Redis connection and RQ queue setup."""
import redis
from rq import Queue

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_redis_conn: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _redis_conn
    if _redis_conn is None:
        _redis_conn = redis.from_url(settings.REDIS_URL, decode_responses=False)
    return _redis_conn


def get_queue(name: str = "default") -> Queue:
    return Queue(name, connection=get_redis())


def enqueue_ocr_job(invoice_id: str, job_id: str) -> str | None:
    try:
        queue = get_queue("ocr")
        rq_job = queue.enqueue(
            "app.workers.invoice_processor.process_invoice",
            invoice_id,
            job_id,
            job_timeout=settings.JOB_TIMEOUT,
            result_ttl=settings.JOB_RESULT_TTL,
            failure_ttl=settings.JOB_FAILURE_TTL,
            retry=__import__("rq", fromlist=["Retry"]).Retry(max=3, interval=[10, 30, 60]),
        )
        logger.info("ocr_job_enqueued", rq_job_id=rq_job.id, invoice_id=invoice_id)
        return rq_job.id
    except Exception as exc:
        logger.error("enqueue_failed", error=str(exc), invoice_id=invoice_id)
        return None


def enqueue_reconciliation_job(invoice_id: str) -> str | None:
    try:
        queue = get_queue("reconciliation")
        rq_job = queue.enqueue(
            "app.workers.reconciliation_worker.auto_reconcile",
            invoice_id,
            job_timeout=settings.JOB_TIMEOUT,
            result_ttl=settings.JOB_RESULT_TTL,
        )
        logger.info("reconciliation_job_enqueued", rq_job_id=rq_job.id, invoice_id=invoice_id)
        return rq_job.id
    except Exception as exc:
        logger.error("enqueue_reconciliation_failed", error=str(exc))
        return None
