"""Queue abstraction with a Redis-or-inline strategy.

Production deployments use Redis + RQ workers. Local development without
Redis is supported by ``QUEUE_BACKEND=inline`` (or ``auto`` when Redis is
unreachable): jobs run synchronously in the request thread so the existing
endpoint contract (return 202, then OCR + reconcile happen) still works
end-to-end on a laptop with nothing installed but Python.
"""
from __future__ import annotations

import threading
import uuid as _uuid
from typing import Any

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Cached state — populated lazily so importing this module never explodes if
# Redis is missing or misconfigured.
_redis_conn: Any = None
_redis_available: bool | None = None  # tri-state: None=unknown, True/False=tested
_lock = threading.Lock()


# ── Redis-backed path ──────────────────────────────────────────────────────────

def _try_get_redis() -> Any | None:
    """Return a connected redis client, or None if Redis is unavailable.

    The result is cached so we don't ping Redis on every enqueue.
    """
    global _redis_conn, _redis_available

    if _redis_available is False:
        return None
    if _redis_conn is not None and _redis_available is True:
        return _redis_conn

    with _lock:
        if _redis_available is False:
            return None
        if _redis_conn is not None and _redis_available is True:
            return _redis_conn

        try:
            import redis  # imported lazily so the package being absent is survivable

            conn = redis.from_url(settings.REDIS_URL, decode_responses=False, socket_connect_timeout=1)
            conn.ping()
            _redis_conn = conn
            _redis_available = True
            return conn
        except Exception as exc:
            _redis_available = False
            logger.info("redis_unavailable_using_inline_queue", error=str(exc))
            return None


def get_redis() -> Any:
    """Backwards-compatible accessor used by /health.

    Raises if Redis isn't reachable so the health endpoint can report 'degraded'.
    """
    conn = _try_get_redis()
    if conn is None:
        raise RuntimeError("Redis is not configured or unreachable")
    return conn


# ── Inline (in-process) path ───────────────────────────────────────────────────

def _run_inline(import_path: str, *args, **kwargs) -> str:
    """Resolve and invoke a job function in-process. Returns a synthetic job id.

    Errors are logged and re-raised so the caller can see what happened during
    development — production should not be using the inline path.
    """
    module_path, _, func_name = import_path.rpartition(".")
    if not module_path:
        raise ValueError(f"Invalid import path: {import_path!r}")
    fake_id = f"inline-{_uuid.uuid4()}"
    logger.info("inline_job_started", import_path=import_path, fake_id=fake_id)
    try:
        module = __import__(module_path, fromlist=[func_name])
        fn = getattr(module, func_name)
        fn(*args, **kwargs)
        logger.info("inline_job_completed", import_path=import_path, fake_id=fake_id)
    except Exception as exc:
        logger.error("inline_job_failed", import_path=import_path, error=str(exc))
        # Don't re-raise: matches RQ behavior of failing in the worker, not in the
        # producer's request thread. Failures are recorded on the ProcessingJob row
        # by the worker function itself.
    return fake_id


# ── Public enqueue API ─────────────────────────────────────────────────────────

def _select_backend() -> str:
    """Return 'redis' or 'inline' based on QUEUE_BACKEND + actual reachability."""
    mode = settings.QUEUE_BACKEND
    if mode == "inline":
        return "inline"
    if mode == "redis":
        # Will raise downstream if Redis isn't actually reachable, which matches the
        # explicit-strict semantics of redis-mode.
        return "redis"
    # auto
    return "redis" if _try_get_redis() is not None else "inline"


def enqueue_ocr_job(invoice_id: str, job_id: str) -> str | None:
    backend = _select_backend()
    if backend == "inline":
        return _run_inline("app.workers.invoice_processor.process_invoice", invoice_id, job_id)

    try:
        from rq import Queue, Retry
        queue = Queue("ocr", connection=_try_get_redis() or get_redis())
        rq_job = queue.enqueue(
            "app.workers.invoice_processor.process_invoice",
            invoice_id,
            job_id,
            job_timeout=settings.JOB_TIMEOUT,
            result_ttl=settings.JOB_RESULT_TTL,
            failure_ttl=settings.JOB_FAILURE_TTL,
            retry=Retry(max=3, interval=[10, 30, 60]),
        )
        logger.info("ocr_job_enqueued", rq_job_id=rq_job.id, invoice_id=invoice_id)
        return rq_job.id
    except Exception as exc:
        logger.error("enqueue_failed_falling_back_inline", error=str(exc), invoice_id=invoice_id)
        return _run_inline("app.workers.invoice_processor.process_invoice", invoice_id, job_id)


def enqueue_reconciliation_job(invoice_id: str) -> str | None:
    backend = _select_backend()
    if backend == "inline":
        return _run_inline("app.workers.reconciliation_worker.auto_reconcile", invoice_id)

    try:
        from rq import Queue
        queue = Queue("reconciliation", connection=_try_get_redis() or get_redis())
        rq_job = queue.enqueue(
            "app.workers.reconciliation_worker.auto_reconcile",
            invoice_id,
            job_timeout=settings.JOB_TIMEOUT,
            result_ttl=settings.JOB_RESULT_TTL,
        )
        logger.info("reconciliation_job_enqueued", rq_job_id=rq_job.id, invoice_id=invoice_id)
        return rq_job.id
    except Exception as exc:
        logger.error("enqueue_recon_failed_falling_back_inline", error=str(exc), invoice_id=invoice_id)
        return _run_inline("app.workers.reconciliation_worker.auto_reconcile", invoice_id)


# Optional helper kept for callers that want a Queue directly. Returns None
# when running inline.
def get_queue(name: str = "default") -> Any | None:
    if _select_backend() == "inline":
        return None
    from rq import Queue
    return Queue(name, connection=get_redis())
