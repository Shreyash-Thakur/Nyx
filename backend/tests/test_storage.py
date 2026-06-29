"""Storage service tests.

Covers BUG-1: the OCR worker must be able to read a stored file from a
synchronous context, including one that is already inside a running asyncio
event loop (the inline-queue path runs inside the request's event loop).
A previous implementation called ``run_until_complete`` on the running loop
and raised ``RuntimeError: This event loop is already running``.
"""
import asyncio
import uuid

from app.services import storage_service
from app.services.storage_service import StorageService


def test_read_sync_returns_saved_bytes(tmp_path, monkeypatch):
    monkeypatch.setattr(storage_service.settings, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(storage_service.settings, "STORAGE_BACKEND", "local")
    svc = StorageService()
    content = b"%PDF-1.4 fake invoice bytes"
    inv_id = uuid.uuid4()

    path, checksum = asyncio.run(svc.save(content, "x.pdf", inv_id))

    assert svc.read_sync(path) == content
    assert len(checksum) == 64  # sha256 hex


def test_read_sync_works_inside_running_event_loop(tmp_path, monkeypatch):
    """Reproduces BUG-1: reading storage from a sync call nested in a live loop."""
    monkeypatch.setattr(storage_service.settings, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(storage_service.settings, "STORAGE_BACKEND", "local")
    svc = StorageService()
    content = b"bytes read under a running loop"
    inv_id = uuid.uuid4()

    async def scenario() -> bytes:
        path, _ = await svc.save(content, "y.pdf", inv_id)
        # Synchronous read while the event loop is running — must not raise.
        return svc.read_sync(path)

    assert asyncio.run(scenario()) == content
