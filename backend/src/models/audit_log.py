"""Audit log model for tracking system events."""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import GUID, Base, JSONType


class AuditAction(str, Enum):
    """Audit event action types."""

    # Authentication events
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGOUT = "logout"
    PASSWORD_CHANGE = "password_change"
    FIDO2_REGISTER = "fido2_register"
    FIDO2_AUTH = "fido2_auth"

    # User management
    USER_CREATE = "user_create"
    USER_UPDATE = "user_update"
    USER_DELETE = "user_delete"
    USER_LOCK = "user_lock"
    USER_UNLOCK = "user_unlock"

    # Role management
    ROLE_CREATE = "role_create"
    ROLE_UPDATE = "role_update"
    ROLE_DELETE = "role_delete"
    ROLE_ASSIGN = "role_assign"
    ROLE_REVOKE = "role_revoke"

    # Data operations
    DATA_IMPORT = "data_import"
    DATA_EXPORT = "data_export"


class AuditLog(Base):
    """Audit log table for compliance and security tracking."""

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    resource_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    resource_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    ip_address: Mapped[str | None] = mapped_column(
        String(45),  # Supports IPv6
        nullable=True,
    )
    user_agent: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
    )
    details: Mapped[dict | None] = mapped_column(
        JSONType(),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="success",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
