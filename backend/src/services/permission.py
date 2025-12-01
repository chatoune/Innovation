"""Permission service for RBAC."""

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.permission import Permission
from src.models.role import Role
from src.models.user import User


class PermissionService:
    """Service for permission management and checking."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_permissions(self, user_id: uuid.UUID) -> set[str]:
        """Get all effective permissions for a user (union of all role permissions).

        Args:
            user_id: User ID to get permissions for

        Returns:
            Set of permission codes
        """
        result = await self.db.execute(
            select(User)
            .where(User.id == user_id)
            .options(
                selectinload(User.roles).selectinload(Role.permissions)
            )
        )
        user = result.scalar_one_or_none()

        if user is None:
            return set()

        # Superusers have all permissions
        if user.is_superuser:
            return {"*"}

        # Union of all permissions from all roles
        permissions: set[str] = set()
        for role in user.roles:
            for permission in role.permissions:
                permissions.add(permission.code)

        return permissions

    async def user_has_permission(
        self,
        user_id: uuid.UUID,
        permission_code: str,
    ) -> bool:
        """Check if user has a specific permission.

        Args:
            user_id: User ID to check
            permission_code: Permission code to check for

        Returns:
            True if user has the permission
        """
        permissions = await self.get_user_permissions(user_id)

        # Superusers have all permissions (indicated by "*")
        if "*" in permissions:
            return True

        return permission_code in permissions

    async def user_has_any_permission(
        self,
        user_id: uuid.UUID,
        permission_codes: list[str],
    ) -> bool:
        """Check if user has any of the specified permissions.

        Args:
            user_id: User ID to check
            permission_codes: List of permission codes (any match = True)

        Returns:
            True if user has any of the permissions
        """
        permissions = await self.get_user_permissions(user_id)

        if "*" in permissions:
            return True

        return bool(permissions.intersection(permission_codes))

    async def user_has_all_permissions(
        self,
        user_id: uuid.UUID,
        permission_codes: list[str],
    ) -> bool:
        """Check if user has all of the specified permissions.

        Args:
            user_id: User ID to check
            permission_codes: List of permission codes (all must match)

        Returns:
            True if user has all of the permissions
        """
        permissions = await self.get_user_permissions(user_id)

        if "*" in permissions:
            return True

        return set(permission_codes).issubset(permissions)

    async def get_all_permissions(self) -> Sequence[Permission]:
        """Get all available permissions."""
        result = await self.db.execute(
            select(Permission).order_by(Permission.category, Permission.code)
        )
        return result.scalars().all()

    async def get_permission_by_code(self, code: str) -> Permission | None:
        """Get permission by code."""
        result = await self.db.execute(
            select(Permission).where(Permission.code == code)
        )
        return result.scalar_one_or_none()

    async def get_permissions_by_ids(
        self,
        permission_ids: list[uuid.UUID],
    ) -> Sequence[Permission]:
        """Get permissions by their IDs."""
        result = await self.db.execute(
            select(Permission).where(Permission.id.in_(permission_ids))
        )
        return result.scalars().all()
