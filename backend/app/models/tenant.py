import uuid

from sqlalchemy import Boolean, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db_types import GUID
from app.core.tenancy import DEFAULT_TENANT_ID
from app.models.base import BaseModel


class Tenant(BaseModel):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        return f"<Tenant {self.slug}>"


class TenantMixin:
    """Adds a ``tenant_id`` to every tenant-scoped domain table.

    Defaults to the seeded default tenant so single-tenant operation (and
    existing rows) work before tenant onboarding lands. No DB-level foreign
    key: tenant integrity is enforced at the application layer (ADR-0004),
    which also keeps the migration portable across SQLite and Postgres.
    """

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        default=DEFAULT_TENANT_ID,
        server_default=text(f"'{DEFAULT_TENANT_ID}'"),
        nullable=False,
        index=True,
    )
