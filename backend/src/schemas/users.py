"""User management Pydantic schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    """Base user schema."""

    email: EmailStr = Field(..., description="User email address")
    full_name: str | None = Field(None, description="User full name")


class UserCreate(UserBase):
    """Schema for creating a user."""

    password: str = Field(..., min_length=8, description="User password")
    is_active: bool = Field(default=True, description="Whether user is active")
    is_superuser: bool = Field(default=False, description="Whether user is superuser")
    role_ids: list[uuid.UUID] = Field(
        default_factory=list,
        description="List of role IDs to assign",
    )


class UserUpdate(BaseModel):
    """Schema for updating a user."""

    email: EmailStr | None = Field(None, description="User email address")
    full_name: str | None = Field(None, description="User full name")
    is_active: bool | None = Field(None, description="Whether user is active")
    is_superuser: bool | None = Field(None, description="Whether user is superuser")


class UserResponse(UserBase):
    """User response schema."""

    id: uuid.UUID = Field(..., description="User ID")
    is_active: bool = Field(..., description="Whether user is active")
    is_superuser: bool = Field(..., description="Whether user is superuser")
    failed_attempts: int = Field(..., description="Failed login attempts")
    locked_until: datetime | None = Field(None, description="Account locked until")
    last_login: datetime | None = Field(None, description="Last login timestamp")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = {"from_attributes": True}


class UserListItem(BaseModel):
    """User list item schema (minimal data)."""

    id: uuid.UUID = Field(..., description="User ID")
    email: EmailStr = Field(..., description="User email")
    full_name: str | None = Field(None, description="User full name")
    is_active: bool = Field(..., description="Whether user is active")
    is_superuser: bool = Field(..., description="Whether user is superuser")
    role_count: int = Field(default=0, description="Number of assigned roles")
    last_login: datetime | None = Field(None, description="Last login timestamp")

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    """Paginated user list response."""

    items: list[UserListItem] = Field(..., description="List of users")
    total: int = Field(..., description="Total number of users")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Items per page")
    total_pages: int = Field(..., description="Total number of pages")


class UserRoleResponse(BaseModel):
    """User role assignment response."""

    id: uuid.UUID = Field(..., description="Role ID")
    name: str = Field(..., description="Role name")
    description: str | None = Field(None, description="Role description")

    model_config = {"from_attributes": True}


class UserDetailResponse(UserResponse):
    """Detailed user response with roles."""

    roles: list[UserRoleResponse] = Field(
        default_factory=list,
        description="Assigned roles",
    )

    model_config = {"from_attributes": True}


class PasswordReset(BaseModel):
    """Admin password reset schema."""

    new_password: str = Field(..., min_length=8, description="New password")
