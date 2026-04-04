from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from financeops.db.base import Base, UUIDBase, utc_now


class UserRole(str, enum.Enum):
    super_admin = "super_admin"
    platform_owner = "platform_owner"
    platform_admin = "platform_admin"
    platform_support = "platform_support"
    finance_leader = "finance_leader"
    finance_team = "finance_team"
    director = "director"
    entity_user = "entity_user"
    auditor = "auditor"
    hr_manager = "hr_manager"
    employee = "employee"
    read_only = "read_only"


class IamUser(UUIDBase):
    """
    Platform user. Belongs to exactly one tenant.
    totp_secret is stored AES-256-GCM encrypted.
    """
    __tablename__ = "iam_users"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role_enum"),
        nullable=False,
        default=UserRole.read_only,
    )
    # AES-256-GCM encrypted TOTP secret (base64 stored)
    totp_secret_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    force_password_change: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    force_mfa_setup: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    terms_accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    terms_version_accepted: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )
    invite_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    invite_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    invite_accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    display_scale_override: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        default=None,
    )

    # Relationships
    sessions: Mapped[list["IamSession"]] = relationship(
        "IamSession", back_populates="user", lazy="noload"
    )


class IamSession(UUIDBase):
    """
    Tracks active refresh token sessions for a user.
    revoked_at is set when the session is invalidated (logout / rotation).
    """
    __tablename__ = "iam_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    refresh_token_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    device_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user: Mapped["IamUser"] = relationship("IamUser", back_populates="sessions", lazy="noload")
