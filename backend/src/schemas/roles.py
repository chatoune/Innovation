"""Role and permission Pydantic schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class PermissionBase(BaseModel):
    """Base permission schema."""

    code: str = Field(..., description="Unique permission code")
    name: str = Field(..., description="Display name")
    description: str | None = Field(None, description="Permission description")
    category: str = Field(default="general", description="Permission category")


class PermissionCreate(PermissionBase):
    """Schema for creating a permission."""

    pass


class PermissionResponse(PermissionBase):
    """Permission response schema."""

    id: uuid.UUID = Field(..., description="Permission ID")
    created_at: datetime = Field(..., description="Creation timestamp")

    model_config = {"from_attributes": True}


class RoleBase(BaseModel):
    """Base role schema."""

    name: str = Field(..., min_length=1, max_length=100, description="Role name")
    description: str | None = Field(None, max_length=500, description="Role description")


class RoleCreate(RoleBase):
    """Schema for creating a role."""

    permission_ids: list[uuid.UUID] = Field(
        default_factory=list,
        description="List of permission IDs to assign",
    )


class RoleUpdate(BaseModel):
    """Schema for updating a role."""

    name: str | None = Field(None, min_length=1, max_length=100, description="Role name")
    description: str | None = Field(None, max_length=500, description="Role description")


class RoleResponse(RoleBase):
    """Role response schema."""

    id: uuid.UUID = Field(..., description="Role ID")
    is_system: bool = Field(..., description="Whether this is a system role")
    permissions: list[PermissionResponse] = Field(
        default_factory=list,
        description="Permissions assigned to this role",
    )
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = {"from_attributes": True}


class RoleListResponse(BaseModel):
    """Role list response schema."""

    id: uuid.UUID = Field(..., description="Role ID")
    name: str = Field(..., description="Role name")
    description: str | None = Field(None, description="Role description")
    is_system: bool = Field(..., description="Whether this is a system role")
    permission_count: int = Field(..., description="Number of permissions")
    user_count: int = Field(..., description="Number of users with this role")

    model_config = {"from_attributes": True}


class PermissionAssignment(BaseModel):
    """Schema for assigning permissions to a role."""

    permission_ids: list[uuid.UUID] = Field(
        ...,
        description="List of permission IDs to assign (replaces existing)",
    )


class UserRoleAssignment(BaseModel):
    """Schema for assigning roles to a user."""

    role_ids: list[uuid.UUID] = Field(
        ...,
        description="List of role IDs to assign (replaces existing)",
    )
