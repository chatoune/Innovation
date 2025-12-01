"""User management routes."""

import uuid

from fastapi import APIRouter, Depends, Query, Request

from src.api.deps.auth import AuditDep, CurrentUserDep, DbDep
from src.api.deps.permissions import require_permission
from src.models.permission import PermissionCode
from src.schemas.roles import UserRoleAssignment
from src.schemas.users import (
    PasswordReset,
    UserCreate,
    UserDetailResponse,
    UserListResponse,
    UserResponse,
    UserRoleResponse,
    UserUpdate,
)
from src.services.user import UserService

router = APIRouter()


@router.get("", response_model=UserListResponse)
async def list_users(
    request: Request,
    db: DbDep,
    current_user: CurrentUserDep,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    search: str | None = Query(None, description="Search by email or name"),
    is_active: bool | None = Query(None, description="Filter by active status"),
    _: None = Depends(require_permission(PermissionCode.USERS_READ)),
) -> UserListResponse:
    """List users with pagination and filtering."""
    service = UserService(db)
    return await service.list_users(
        page=page,
        page_size=page_size,
        search=search,
        is_active=is_active,
    )


@router.post("", response_model=UserDetailResponse, status_code=201)
async def create_user(
    request: Request,
    user_data: UserCreate,
    db: DbDep,
    audit: AuditDep,
    current_user: CurrentUserDep,
    _: None = Depends(require_permission(PermissionCode.USERS_CREATE)),
) -> UserDetailResponse:
    """Create a new user."""
    service = UserService(db, audit)
    user = await service.create_user(
        data=user_data,
        request=request,
        created_by=current_user.id,
    )
    return UserDetailResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        failed_attempts=user.failed_attempts,
        locked_until=user.locked_until,
        last_login=user.last_login,
        created_at=user.created_at,
        updated_at=user.updated_at,
        roles=[UserRoleResponse(id=r.id, name=r.name, description=r.description) for r in user.roles],
    )


@router.get("/{user_id}", response_model=UserDetailResponse)
async def get_user(
    user_id: uuid.UUID,
    db: DbDep,
    current_user: CurrentUserDep,
    _: None = Depends(require_permission(PermissionCode.USERS_READ)),
) -> UserDetailResponse:
    """Get user details by ID."""
    from src.api.middleware.errors import NotFoundError

    service = UserService(db)
    user = await service.get_user_by_id(user_id)
    if user is None:
        raise NotFoundError(f"User with ID {user_id} not found")

    return UserDetailResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        failed_attempts=user.failed_attempts,
        locked_until=user.locked_until,
        last_login=user.last_login,
        created_at=user.created_at,
        updated_at=user.updated_at,
        roles=[UserRoleResponse(id=r.id, name=r.name, description=r.description) for r in user.roles],
    )


@router.patch("/{user_id}", response_model=UserDetailResponse)
async def update_user(
    request: Request,
    user_id: uuid.UUID,
    user_data: UserUpdate,
    db: DbDep,
    audit: AuditDep,
    current_user: CurrentUserDep,
    _: None = Depends(require_permission(PermissionCode.USERS_UPDATE)),
) -> UserDetailResponse:
    """Update user details."""
    service = UserService(db, audit)
    user = await service.update_user(
        user_id=user_id,
        data=user_data,
        request=request,
        updated_by=current_user.id,
    )
    return UserDetailResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        failed_attempts=user.failed_attempts,
        locked_until=user.locked_until,
        last_login=user.last_login,
        created_at=user.created_at,
        updated_at=user.updated_at,
        roles=[UserRoleResponse(id=r.id, name=r.name, description=r.description) for r in user.roles],
    )


@router.post("/{user_id}/deactivate", response_model=UserResponse)
async def deactivate_user(
    request: Request,
    user_id: uuid.UUID,
    db: DbDep,
    audit: AuditDep,
    current_user: CurrentUserDep,
    _: None = Depends(require_permission(PermissionCode.USERS_UPDATE)),
) -> UserResponse:
    """Deactivate a user account."""
    service = UserService(db, audit)
    user = await service.deactivate_user(
        user_id=user_id,
        request=request,
        deactivated_by=current_user.id,
    )
    return UserResponse.model_validate(user)


@router.post("/{user_id}/reactivate", response_model=UserResponse)
async def reactivate_user(
    request: Request,
    user_id: uuid.UUID,
    db: DbDep,
    audit: AuditDep,
    current_user: CurrentUserDep,
    _: None = Depends(require_permission(PermissionCode.USERS_UPDATE)),
) -> UserResponse:
    """Reactivate a user account."""
    service = UserService(db, audit)
    user = await service.reactivate_user(
        user_id=user_id,
        request=request,
        reactivated_by=current_user.id,
    )
    return UserResponse.model_validate(user)


@router.post("/{user_id}/unlock", response_model=UserResponse)
async def unlock_user(
    request: Request,
    user_id: uuid.UUID,
    db: DbDep,
    audit: AuditDep,
    current_user: CurrentUserDep,
    _: None = Depends(require_permission(PermissionCode.USERS_UPDATE)),
) -> UserResponse:
    """Unlock a locked user account."""
    service = UserService(db, audit)
    user = await service.unlock_user(
        user_id=user_id,
        request=request,
        unlocked_by=current_user.id,
    )
    return UserResponse.model_validate(user)


@router.get("/{user_id}/roles", response_model=list[UserRoleResponse])
async def get_user_roles(
    user_id: uuid.UUID,
    db: DbDep,
    current_user: CurrentUserDep,
    _: None = Depends(require_permission(PermissionCode.USERS_READ)),
) -> list[UserRoleResponse]:
    """Get roles assigned to a user."""
    service = UserService(db)
    roles = await service.get_user_roles(user_id)
    return [UserRoleResponse(id=r.id, name=r.name, description=r.description) for r in roles]


@router.put("/{user_id}/roles", response_model=UserDetailResponse)
async def assign_user_roles(
    request: Request,
    user_id: uuid.UUID,
    assignment: UserRoleAssignment,
    db: DbDep,
    audit: AuditDep,
    current_user: CurrentUserDep,
    _: None = Depends(require_permission(PermissionCode.USERS_UPDATE)),
) -> UserDetailResponse:
    """Assign roles to a user (replaces existing)."""
    service = UserService(db, audit)
    user = await service.assign_roles(
        user_id=user_id,
        role_ids=assignment.role_ids,
        request=request,
        assigned_by=current_user.id,
    )
    return UserDetailResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        failed_attempts=user.failed_attempts,
        locked_until=user.locked_until,
        last_login=user.last_login,
        created_at=user.created_at,
        updated_at=user.updated_at,
        roles=[UserRoleResponse(id=r.id, name=r.name, description=r.description) for r in user.roles],
    )


@router.post("/{user_id}/reset-password", response_model=UserResponse)
async def reset_user_password(
    request: Request,
    user_id: uuid.UUID,
    password_data: PasswordReset,
    db: DbDep,
    audit: AuditDep,
    current_user: CurrentUserDep,
    _: None = Depends(require_permission(PermissionCode.USERS_UPDATE)),
) -> UserResponse:
    """Reset a user's password (admin action)."""
    service = UserService(db, audit)
    user = await service.reset_password(
        user_id=user_id,
        new_password=password_data.new_password,
        request=request,
        reset_by=current_user.id,
    )
    return UserResponse.model_validate(user)
