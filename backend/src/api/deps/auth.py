"""Authentication dependencies for protected routes."""

from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps.database import get_db
from src.api.middleware.errors import AuthenticationError
from src.core.security import decode_token, verify_token_type
from src.models.user import User
from src.schemas.auth import CurrentUser
from src.services.audit import AuditService


async def get_token_from_header(
    authorization: str | None = Header(None, alias="Authorization"),
) -> str:
    """Extract bearer token from Authorization header."""
    if authorization is None:
        raise AuthenticationError("Authorization header missing")

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise AuthenticationError("Invalid authorization header format")

    return parts[1]


async def get_current_user(
    token: Annotated[str, Depends(get_token_from_header)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CurrentUser:
    """Dependency that returns the current authenticated user.

    Usage:
        @router.get("/protected")
        async def protected_route(
            current_user: CurrentUser = Depends(get_current_user)
        ):
            ...
    """
    from sqlalchemy import select

    from src.services.permission import PermissionService

    payload = decode_token(token)
    if payload is None:
        raise AuthenticationError("Invalid or expired token")

    if not verify_token_type(payload, "access"):
        raise AuthenticationError("Invalid token type")

    user_id = payload.get("sub")
    if user_id is None:
        raise AuthenticationError("Invalid token payload")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise AuthenticationError("User not found")

    if not user.is_active:
        raise AuthenticationError("User account is inactive")

    # Get effective permissions
    permission_service = PermissionService(db)
    permissions = await permission_service.get_user_permissions(user.id)

    return CurrentUser(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        last_login=user.last_login,
        permissions=list(permissions),
    )


async def get_current_active_user(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CurrentUser:
    """Dependency that ensures the current user is active."""
    if not current_user.is_active:
        raise AuthenticationError("Inactive user")
    return current_user


async def get_current_superuser(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CurrentUser:
    """Dependency that ensures the current user is a superuser."""
    from src.api.middleware.errors import AuthorizationError

    if not current_user.is_superuser:
        raise AuthorizationError("Superuser access required")
    return current_user


async def get_audit_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AuditService:
    """Dependency that provides audit service."""
    return AuditService(db)


# Type aliases for cleaner dependency injection
CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]
ActiveUserDep = Annotated[CurrentUser, Depends(get_current_active_user)]
SuperuserDep = Annotated[CurrentUser, Depends(get_current_superuser)]
DbDep = Annotated[AsyncSession, Depends(get_db)]
AuditDep = Annotated[AuditService, Depends(get_audit_service)]
