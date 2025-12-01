"""Authentication-related Pydantic schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    """Login request schema."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=1, description="User password")


class AuthResponse(BaseModel):
    """Authentication response schema."""

    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration in seconds")


class RefreshRequest(BaseModel):
    """Token refresh request schema."""

    refresh_token: str = Field(..., description="JWT refresh token")


class CurrentUser(BaseModel):
    """Current authenticated user schema."""

    id: uuid.UUID = Field(..., description="User unique identifier")
    email: EmailStr = Field(..., description="User email address")
    full_name: str | None = Field(None, description="User full name")
    is_active: bool = Field(..., description="Whether user account is active")
    is_superuser: bool = Field(..., description="Whether user is a superuser")
    last_login: datetime | None = Field(None, description="Last login timestamp")
    permissions: list[str] = Field(
        default_factory=list,
        description="Effective permissions (union of all role permissions)",
    )

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    """User creation schema (for admin use)."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, description="User password")
    full_name: str | None = Field(None, description="User full name")
    is_active: bool = Field(default=True, description="Whether user is active")
    is_superuser: bool = Field(default=False, description="Whether user is superuser")


class PasswordChange(BaseModel):
    """Password change request schema."""

    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, description="New password")
