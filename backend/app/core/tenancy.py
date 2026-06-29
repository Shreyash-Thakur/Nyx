"""Tenancy primitives.

Per ADR-0008 the schema is tenant-aware from day one even though tenant
onboarding is deferred: every domain row carries a ``tenant_id`` so RBAC,
events and future modules are tenant-scoped from birth and no painful
backfill is needed later.

Until onboarding exists, everything lives under a single seeded default
tenant. ``ensure_default_tenant`` is idempotent.
"""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

DEFAULT_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000010")
DEFAULT_TENANT_SLUG = "default"


def ensure_default_tenant(db: Session):
    from app.models.tenant import Tenant

    tenant = db.get(Tenant, DEFAULT_TENANT_ID)
    if tenant is None:
        tenant = Tenant(
            id=DEFAULT_TENANT_ID,
            name="Default Tenant",
            slug=DEFAULT_TENANT_SLUG,
            is_active=True,
        )
        db.add(tenant)
        db.flush()
    return tenant
