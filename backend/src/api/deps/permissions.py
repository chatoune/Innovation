"""Permission checking dependencies for protected routes."""

from collections.abc import Callable

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps.auth import get_current_user
from src.api.deps.database import get_db
from src.api.middleware.errors import AuthorizationError
from src.schemas.auth import CurrentUser
from src.services.permission import PermissionService


def require_permission(permission_code: str) -> Callable:
    """Dependency factory that requires a specific permission.

    Usage:
        @router.get("/admin")
        async def admin_endpoint(
            _: None = Depends(require_permission("admin:all"))
        ):
            ...
    """
    async def permission_checker(
        current_user: CurrentUser = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> None:
        service = PermissionService(db)
        has_permission = await service.user_has_permission(
            current_user.id,
            permission_code,
        )
        if not has_permission:
            raise AuthorizationError(
                f"Permission required: {permission_code}"
            )

    return permission_checker


def require_any_permission(*permission_codes: str) -> Callable:
    """Dependency factory that requires any of the specified permissions.

    Usage:
        @router.get("/users")
        async def users_endpoint(
            _: None = Depends(require_any_permission("users:read", "admin:all"))
        ):
            ...
    """
    async def permission_checker(
        current_user: CurrentUser = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> None:
        service = PermissionService(db)
        has_permission = await service.user_has_any_permission(
            current_user.id,
            list(permission_codes),
        )
        if not has_permission:
            raise AuthorizationError(
                f"One of these permissions required: {', '.join(permission_codes)}"
            )

    return permission_checker


def require_all_permissions(*permission_codes: str) -> Callable:
    """Dependency factory that requires all of the specified permissions.

    Usage:
        @router.delete("/users/{id}")
        async def delete_user(
            _: None = Depends(require_all_permissions("users:read", "users:delete"))
        ):
            ...
    """
    async def permission_checker(
        current_user: CurrentUser = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> None:
        service = PermissionService(db)
        has_permission = await service.user_has_all_permissions(
            current_user.id,
            list(permission_codes),
        )
        if not has_permission:
            raise AuthorizationError(
                f"All these permissions required: {', '.join(permission_codes)}"
            )

    return permission_checker


class PermissionChecker:
    """Class-based permission checker for more complex scenarios."""

    def __init__(self, permission_code: str):
        self.permission_code = permission_code

    async def __call__(
        self,
        current_user: CurrentUser = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> bool:
        """Check if user has the required permission.

        Returns True if user has permission, raises AuthorizationError otherwise.
        """
        service = PermissionService(db)
        has_permission = await service.user_has_permission(
            current_user.id,
            self.permission_code,
        )
        if not has_permission:
            raise AuthorizationError(
                f"Permission required: {self.permission_code}"
            )
        return True
