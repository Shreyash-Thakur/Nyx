"""Health/readiness endpoint (Priority 8: production readiness).

The default zero-dependency deployment runs the inline queue with no Redis.
The health check must report 'healthy' in that configuration -- otherwise a
readiness probe would take a perfectly good inline deployment out of rotation.
"""


def test_health_is_healthy_on_inline_backend_without_redis(client):
    """conftest sets QUEUE_BACKEND=inline and no reachable Redis."""
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "healthy"
    assert body["checks"]["database"] == "ok"
    assert body["checks"]["queue_backend"] == "inline"
    assert "not required" in body["checks"]["redis"]


def test_health_reports_degraded_when_redis_required_but_down(client, monkeypatch):
    """In explicit redis mode, an unreachable Redis is a real degradation."""
    import app.workers.queue as queue
    from app.config import settings

    monkeypatch.setattr(settings, "QUEUE_BACKEND", "redis")

    def _boom():
        raise RuntimeError("redis down")

    monkeypatch.setattr(queue, "get_redis", _boom)

    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["checks"]["queue_backend"] == "redis"
