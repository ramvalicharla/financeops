from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from financeops.db.base import Base, FinancialBase, UUIDBase, utc_now


class TenantType(str, enum.Enum):
    direct = "direct"
    ca_firm = "ca_firm"
    enterprise_group = "enterprise_group"


class TenantStatus(str, enum.Enum):
    active = "active"
    suspended = "suspended"
    pending = "pending"


class WorkspaceStatus(str, enum.Enum):
    active = "active"
    suspended = "suspended"


class IamTenant(FinancialBase):
    """
    Multi-tenant root entity. Every resource belongs to a tenant.
    Inherits from FinancialBase: id, tenant_id, chain_hash, previous_hash, created_at.
    Note: tenant_id here is self-referential (the tenant's own ID).
    """
    __tablename__ = "iam_tenants"

    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        default=lambda: f"tenant-{uuid.uuid4().hex[:8]}",
    )
    tenant_type: Mapped[TenantType] = mapped_column(
        Enum(TenantType, name="tenant_type_enum"), nullable=False
    )
    parent_tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_tenants.id", ondelete="SET NULL"),
        nullable=True,
    )
    country: Mapped[str] = mapped_column(String(2), nullable=False)  # ISO 3166-1 alpha-2
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    status: Mapped[TenantStatus] = mapped_column(
        Enum(TenantStatus, name="tenant_status_enum"),
        nullable=False,
        default=TenantStatus.active,
    )
    is_platform_tenant: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    default_display_scale: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'LAKHS'"),
    )
    default_currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        server_default=text("'INR'"),
    )
    number_format_locale: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'en-IN'"),
    )

    # Relationships
    workspaces: Mapped[list["IamWorkspace"]] = relationship(
        "IamWorkspace", back_populates="tenant", lazy="noload"
    )


class IamWorkspace(UUIDBase):
    """
    Workspace within a tenant. Used for scoping financial data.
    """
    __tablename__ = "iam_workspaces"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[WorkspaceStatus] = mapped_column(
        Enum(WorkspaceStatus, name="workspace_status_enum"),
        nullable=False,
        default=WorkspaceStatus.active,
    )

    # Relationships
    tenant: Mapped["IamTenant"] = relationship(
        "IamTenant", back_populates="workspaces", lazy="noload"
    )
