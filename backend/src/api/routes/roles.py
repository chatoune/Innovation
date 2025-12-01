"""Role and permission management routes."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from src.api.deps.auth import CurrentUserDep, DbDep
from src.api.deps.permissions import require_permission
from src.api.middleware.errors import ConflictError, NotFoundError
from src.models.permission import Permission, PermissionCode
from src.models.role import Role
from src.models.user_roles import UserRole
from src.schemas.roles import (
    PermissionAssignment,
    PermissionResponse,
    RoleCreate,
    RoleListResponse,
    RoleResponse,
    RoleUpdate,
)
from src.services.permission import PermissionService

router = APIRouter()


@router.get("/permissions", response_model=list[PermissionResponse])
async def list_permissions(
    db: DbDep,
    _: CurrentUserDep,
    __: None = Depends(require_permission(PermissionCode.ROLES_READ)),
) -> list[Permission]:
    """List all available permissions."""
    service = PermissionService(db)
    return list(await service.get_all_permissions())


@router.get("", response_model=list[RoleListResponse])
async def list_roles(
    db: DbDep,
    _: CurrentUserDep,
    __: None = Depends(require_permission(PermissionCode.ROLES_READ)),
) -> list[RoleListResponse]:
    """List all roles with permission and user counts."""
    # Get roles with permission counts
    result = await db.execute(
        select(Role).options(selectinload(Role.permissions))
    )
    roles = result.scalars().all()

    # Get user counts per role
    user_count_result = await db.execute(
        select(UserRole.role_id, func.count(UserRole.user_id).label("count"))
        .group_by(UserRole.role_id)
    )
    user_counts = {row.role_id: row.count for row in user_count_result}

    return [
        RoleListResponse(
            id=role.id,
            name=role.name,
            description=role.description,
            is_system=role.is_system,
            permission_count=len(role.permissions),
            user_count=user_counts.get(role.id, 0),
        )
        for role in roles
    ]


@router.post("", response_model=RoleResponse, status_code=201)
async def create_role(
    role_data: RoleCreate,
    db: DbDep,
    _: CurrentUserDep,
    __: None = Depends(require_permission(PermissionCode.ROLES_CREATE)),
) -> Role:
    """Create a new role."""
    # Check for duplicate name
    existing = await db.execute(
        select(Role).where(Role.name == role_data.name)
    )
    if existing.scalar_one_or_none():
        raise ConflictError(f"Role '{role_data.name}' already exists")

    # Get permissions if provided
    permissions = []
    if role_data.permission_ids:
        service = PermissionService(db)
        permissions = list(await service.get_permissions_by_ids(role_data.permission_ids))

    # Create role
    role = Role(
        name=role_data.name,
        description=role_data.description,
        is_system=False,
        permissions=permissions,
    )
    db.add(role)
    await db.flush()

    # Reload with relationships
    await db.refresh(role, ["permissions"])
    return role


@router.get("/{role_id}", response_model=RoleResponse)
async def get_role(
    role_id: uuid.UUID,
    db: DbDep,
    _: CurrentUserDep,
    __: None = Depends(require_permission(PermissionCode.ROLES_READ)),
) -> Role:
    """Get a role by ID."""
    result = await db.execute(
        select(Role)
        .where(Role.id == role_id)
        .options(selectinload(Role.permissions))
    )
    role = result.scalar_one_or_none()

    if role is None:
        raise NotFoundError(f"Role with ID {role_id} not found")

    return role


@router.patch("/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: uuid.UUID,
    role_data: RoleUpdate,
    db: DbDep,
    _: CurrentUserDep,
    __: None = Depends(require_permission(PermissionCode.ROLES_UPDATE)),
) -> Role:
    """Update a role."""
    result = await db.execute(
        select(Role)
        .where(Role.id == role_id)
        .options(selectinload(Role.permissions))
    )
    role = result.scalar_one_or_none()

    if role is None:
        raise NotFoundError(f"Role with ID {role_id} not found")

    if role.is_system:
        raise ConflictError("Cannot modify system roles")

    # Check for duplicate name if changing
    if role_data.name and role_data.name != role.name:
        existing = await db.execute(
            select(Role).where(Role.name == role_data.name)
        )
        if existing.scalar_one_or_none():
            raise ConflictError(f"Role '{role_data.name}' already exists")
        role.name = role_data.name

    if role_data.description is not None:
        role.description = role_data.description

    await db.flush()
    await db.refresh(role, ["permissions"])
    return role


@router.delete("/{role_id}", status_code=204)
async def delete_role(
    role_id: uuid.UUID,
    db: DbDep,
    _: CurrentUserDep,
    __: None = Depends(require_permission(PermissionCode.ROLES_DELETE)),
) -> None:
    """Delete a role (cascades to user assignments per spec)."""
    result = await db.execute(
        select(Role).where(Role.id == role_id)
    )
    role = result.scalar_one_or_none()

    if role is None:
        raise NotFoundError(f"Role with ID {role_id} not found")

    if role.is_system:
        raise ConflictError("Cannot delete system roles")

    await db.delete(role)
    await db.flush()


@router.put("/{role_id}/permissions", response_model=RoleResponse)
async def update_role_permissions(
    role_id: uuid.UUID,
    assignment: PermissionAssignment,
    db: DbDep,
    _: CurrentUserDep,
    __: None = Depends(require_permission(PermissionCode.ROLES_UPDATE)),
) -> Role:
    """Update permissions assigned to a role (replaces existing)."""
    result = await db.execute(
        select(Role)
        .where(Role.id == role_id)
        .options(selectinload(Role.permissions))
    )
    role = result.scalar_one_or_none()

    if role is None:
        raise NotFoundError(f"Role with ID {role_id} not found")

    if role.is_system:
        raise ConflictError("Cannot modify system role permissions")

    # Get new permissions
    service = PermissionService(db)
    permissions = list(await service.get_permissions_by_ids(assignment.permission_ids))

    # Replace permissions
    role.permissions = permissions
    await db.flush()
    await db.refresh(role, ["permissions"])
    return role
