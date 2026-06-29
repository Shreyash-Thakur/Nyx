import io
import uuid

import pytest


SAMPLE_PDF = b"%PDF-1.4 1 0 obj<</Type /Catalog>> endobj"


class TestInvoiceUpload:
    def test_upload_success(self, client, admin_user, auth_headers, mocker):
        mocker.patch(
            "app.services.invoice_service.enqueue_ocr_job",
            return_value=str(uuid.uuid4()),
        )
        mocker.patch(
            "app.services.storage_service.StorageService.save",
            return_value=("invoices/2025/05/test.pdf", "abc123"),
        )
        resp = client.post(
            "/api/v1/invoices",
            files={"file": ("test_invoice.pdf", io.BytesIO(SAMPLE_PDF), "application/pdf")},
            headers=auth_headers,
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["original_filename"] == "test_invoice.pdf"
        assert data["status"] in ("uploaded", "queued")

    def test_upload_wrong_type(self, client, admin_user, auth_headers):
        resp = client.post(
            "/api/v1/invoices",
            files={"file": ("malware.exe", io.BytesIO(b"MZ..."), "application/octet-stream")},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_upload_unauthenticated(self, client):
        resp = client.post(
            "/api/v1/invoices",
            files={"file": ("test.pdf", io.BytesIO(SAMPLE_PDF), "application/pdf")},
        )
        assert resp.status_code == 401


class TestInlinePipelineStatus:
    def test_status_not_clobbered_after_inline_processing(
        self, client, admin_user, auth_headers, db, mocker
    ):
        """BUG-4: in inline mode the worker advances the invoice to EXTRACTED
        synchronously during enqueue; upload() must not then overwrite it with
        QUEUED."""
        from app.models.invoice import Invoice, InvoiceStatus

        mocker.patch(
            "app.services.invoice_service.StorageService.save",
            return_value=("invoices/2026/06/x/t.pdf", "deadbeefchecksum"),
        )

        def fake_enqueue(invoice_id, job_id):
            inv = db.get(Invoice, uuid.UUID(invoice_id))
            inv.status = InvoiceStatus.EXTRACTED
            db.commit()
            return f"inline-{job_id}"

        mocker.patch(
            "app.services.invoice_service.enqueue_ocr_job", side_effect=fake_enqueue
        )

        resp = client.post(
            "/api/v1/invoices",
            files={"file": ("t.pdf", io.BytesIO(SAMPLE_PDF), "application/pdf")},
            headers=auth_headers,
        )
        assert resp.status_code == 202
        assert resp.json()["status"] == "extracted"


class TestInvoiceList:
    def test_list_empty(self, client, admin_user, auth_headers):
        resp = client.get("/api/v1/invoices", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data

    def test_list_pagination_bounds(self, client, admin_user, auth_headers):
        resp = client.get("/api/v1/invoices?page=0", headers=auth_headers)
        assert resp.status_code == 422

        resp = client.get("/api/v1/invoices?page_size=200", headers=auth_headers)
        assert resp.status_code == 422


class TestInvoiceGet:
    def test_get_not_found(self, client, admin_user, auth_headers):
        resp = client.get(f"/api/v1/invoices/{uuid.uuid4()}", headers=auth_headers)
        assert resp.status_code == 404
