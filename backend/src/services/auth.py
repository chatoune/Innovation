"""Authentication service with login, logout, and token management."""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.security import (
    check_needs_rehash,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
    verify_token_type,
)
from src.models.audit_log import AuditAction
from src.models.user import User
from src.schemas.auth import AuthResponse, CurrentUser
from src.services.audit import AuditService


class AuthService:
    """Service for authentication operations."""

    def __init__(self, db: AsyncSession, audit: AuditService):
        self.db = db
        self.audit = audit

    async def get_user_by_email(self, email: str) -> User | None:
        """Get user by email address."""
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        """Get user by ID."""
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    def is_account_locked(self, user: User) -> bool:
        """Check if user account is locked."""
        if user.locked_until is None:
            return False
        return datetime.now(UTC) < user.locked_until

    async def lock_account(self, user: User) -> None:
        """Lock user account after failed attempts."""
        user.locked_until = datetime.now(UTC) + timedelta(
            minutes=settings.LOCKOUT_DURATION_MINUTES
        )
        await self.db.flush()

    async def reset_failed_attempts(self, user: User) -> None:
        """Reset failed login attempts after successful login."""
        user.failed_attempts = 0
        user.locked_until = None
        await self.db.flush()

    async def increment_failed_attempts(self, user: User) -> bool:
        """Increment failed login attempts. Returns True if account is now locked."""
        user.failed_attempts += 1
        if user.failed_attempts >= settings.MAX_LOGIN_ATTEMPTS:
            await self.lock_account(user)
            return True
        await self.db.flush()
        return False

    async def login(
        self,
        email: str,
        password: str,
        request: Request,
        response: Response,
    ) -> AuthResponse | None:
        """Authenticate user and return tokens.

        Returns None if authentication fails.
        Raises AccountLockedError if account is locked.
        """
        from src.api.middleware.errors import AccountLockedError, AuthenticationError

        user = await self.get_user_by_email(email)

        # Log attempt even if user doesn't exist (prevent enumeration)
        if user is None:
            await self.audit.log_from_request(
                request,
                AuditAction.LOGIN_FAILURE,
                details={"email": email, "reason": "user_not_found"},
                status="failure",
            )
            raise AuthenticationError("Invalid email or password")

        # Check if account is locked
        if self.is_account_locked(user):
            await self.audit.log_from_request(
                request,
                AuditAction.LOGIN_FAILURE,
                user_id=user.id,
                details={"reason": "account_locked"},
                status="failure",
            )
            raise AccountLockedError(
                f"Account is locked. Try again after {user.locked_until}"
            )

        # Check if account is inactive
        if not user.is_active:
            await self.audit.log_from_request(
                request,
                AuditAction.LOGIN_FAILURE,
                user_id=user.id,
                details={"reason": "account_inactive"},
                status="failure",
            )
            raise AuthenticationError("Account is inactive")

        # Verify password
        if not verify_password(password, user.password_hash):
            locked = await self.increment_failed_attempts(user)
            await self.audit.log_from_request(
                request,
                AuditAction.LOGIN_FAILURE,
                user_id=user.id,
                details={
                    "reason": "invalid_password",
                    "failed_attempts": user.failed_attempts,
                    "account_locked": locked,
                },
                status="failure",
            )
            if locked:
                raise AccountLockedError(
                    f"Account locked due to too many failed attempts. Try again after {user.locked_until}"
                )
            raise AuthenticationError("Invalid email or password")

        # Check if password needs rehashing
        if check_needs_rehash(user.password_hash):
            user.password_hash = hash_password(password)

        # Reset failed attempts and update last login
        await self.reset_failed_attempts(user)
        user.last_login = datetime.now(UTC)
        await self.db.flush()

        # Create tokens
        token_data = {"sub": str(user.id), "email": user.email}
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)

        # Set refresh token in HTTPOnly cookie
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=settings.ENVIRONMENT == "production",
            samesite="lax",
            max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
            path="/api/auth",
        )

        # Log successful login
        await self.audit.log_from_request(
            request,
            AuditAction.LOGIN_SUCCESS,
            user_id=user.id,
            status="success",
        )

        return AuthResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def logout(
        self,
        user_id: uuid.UUID,
        request: Request,
        response: Response,
    ) -> None:
        """Logout user by clearing refresh token cookie."""
        # Clear refresh token cookie
        response.delete_cookie(
            key="refresh_token",
            path="/api/auth",
        )

        # Log logout
        await self.audit.log_from_request(
            request,
            AuditAction.LOGOUT,
            user_id=user_id,
            status="success",
        )

    async def refresh_tokens(
        self,
        refresh_token: str,
        response: Response,
    ) -> AuthResponse | None:
        """Refresh access token using refresh token."""
        from src.api.middleware.errors import AuthenticationError

        # Decode and validate refresh token
        payload = decode_token(refresh_token)
        if payload is None:
            raise AuthenticationError("Invalid refresh token")

        if not verify_token_type(payload, "refresh"):
            raise AuthenticationError("Invalid token type")

        # Get user
        user_id = uuid.UUID(payload["sub"])
        user = await self.get_user_by_id(user_id)

        if user is None or not user.is_active:
            raise AuthenticationError("User not found or inactive")

        # Create new tokens
        token_data = {"sub": str(user.id), "email": user.email}
        access_token = create_access_token(token_data)
        new_refresh_token = create_refresh_token(token_data)

        # Update refresh token cookie
        response.set_cookie(
            key="refresh_token",
            value=new_refresh_token,
            httponly=True,
            secure=settings.ENVIRONMENT == "production",
            samesite="lax",
            max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
            path="/api/auth",
        )

        return AuthResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def get_current_user(self, token: str) -> CurrentUser | None:
        """Get current user from access token."""
        from src.api.middleware.errors import AuthenticationError

        payload = decode_token(token)
        if payload is None:
            raise AuthenticationError("Invalid access token")

        if not verify_token_type(payload, "access"):
            raise AuthenticationError("Invalid token type")

        user_id = uuid.UUID(payload["sub"])
        user = await self.get_user_by_id(user_id)

        if user is None or not user.is_active:
            raise AuthenticationError("User not found or inactive")

        return CurrentUser.model_validate(user)
