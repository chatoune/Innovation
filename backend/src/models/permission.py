"""Permission model for RBAC."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import GUID, Base, TimestampMixin

if TYPE_CHECKING:
    from src.models.role import Role


class Permission(Base, TimestampMixin):
    """Permission model representing a specific action."""

    __tablename__ = "permissions"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,
    )
    code: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    category: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="general",
        index=True,
    )

    # Relationships
    roles: Mapped[list[Role]] = relationship(
        "Role",
        secondary="role_permissions",
        back_populates="permissions",
    )

    def __repr__(self) -> str:
        return f"<Permission {self.code}>"


# Pre-defined permission codes
class PermissionCode:
    """Standard permission codes for the application."""

    # User management
    USERS_READ = "users:read"
    USERS_CREATE = "users:create"
    USERS_UPDATE = "users:update"
    USERS_DELETE = "users:delete"

    # Role management
    ROLES_READ = "roles:read"
    ROLES_CREATE = "roles:create"
    ROLES_UPDATE = "roles:update"
    ROLES_DELETE = "roles:delete"

    # Data import
    IMPORT_READ = "import:read"
    IMPORT_CREATE = "import:create"
    IMPORT_DELETE = "import:delete"

    # Audit logs
    AUDIT_READ = "audit:read"

    # Admin (superuser-only)
    ADMIN_ALL = "admin:all"
