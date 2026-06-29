"""Audit endpoint.

Regression for the audit response schema: the column was renamed
metadata -> extra_data, but the response model still declared `metadata`,
which made Pydantic read SQLAlchemy's MetaData attribute and error whenever
the result set was non-empty.
"""


def test_audit_list_serializes_rows(client, admin_user, auth_headers):
    # The admin_token fixture performs a login, which writes a USER_LOGIN row.
    resp = client.get("/api/v1/audit", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert "extra_data" in body["items"][0]


def test_audit_requires_authentication(client):
    resp = client.get("/api/v1/audit")
    assert resp.status_code == 401
