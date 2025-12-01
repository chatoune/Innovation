"""User management service."""

import uuid
from collections.abc import Sequence

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.middleware.errors import ConflictError, NotFoundError
from src.core.security import hash_password
from src.models.audit_log import AuditAction
from src.models.role import Role
from src.models.user import User
from src.schemas.users import UserCreate, UserListItem, UserListResponse, UserUpdate
from src.services.audit import AuditService


class UserService:
    """Service for user management operations."""

    def __init__(self, db: AsyncSession, audit: AuditService | None = None):
        self.db = db
        self.audit = audit

    async def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        """Get user by ID with roles loaded."""
        result = await self.db.execute(
            select(User)
            .where(User.id == user_id)
            .options(selectinload(User.roles))
        )
        return result.scalar_one_or_none()

    async def get_user_by_email(self, email: str) -> User | None:
        """Get user by email."""
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def list_users(
        self,
        page: int = 1,
        page_size: int = 20,
        search: str | None = None,
        is_active: bool | None = None,
    ) -> UserListResponse:
        """List users with pagination."""
        # Base query
        query = select(User).options(selectinload(User.roles))

        # Apply filters
        if search:
            query = query.where(
                User.email.ilike(f"%{search}%") | User.full_name.ilike(f"%{search}%")
            )
        if is_active is not None:
            query = query.where(User.is_active == is_active)

        # Get total count
        count_query = select(func.count(User.id))
        if search:
            count_query = count_query.where(
                User.email.ilike(f"%{search}%") | User.full_name.ilike(f"%{search}%")
            )
        if is_active is not None:
            count_query = count_query.where(User.is_active == is_active)

        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size).order_by(User.created_at.desc())

        result = await self.db.execute(query)
        users = result.scalars().all()

        # Convert to response
        items = [
            UserListItem(
                id=user.id,
                email=user.email,
                full_name=user.full_name,
                is_active=user.is_active,
                is_superuser=user.is_superuser,
                role_count=len(user.roles),
                last_login=user.last_login,
            )
            for user in users
        ]

        total_pages = (total + page_size - 1) // page_size

        return UserListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    async def create_user(
        self,
        data: UserCreate,
        request: Request | None = None,
        created_by: uuid.UUID | None = None,
    ) -> User:
        """Create a new user."""
        # Check for duplicate email
        existing = await self.get_user_by_email(data.email)
        if existing:
            raise ConflictError(f"User with email '{data.email}' already exists")

        # Get roles if specified
        roles = []
        if data.role_ids:
            result = await self.db.execute(
                select(Role).where(Role.id.in_(data.role_ids))
            )
            roles = list(result.scalars().all())

        # Create user
        user = User(
            email=data.email,
            password_hash=hash_password(data.password),
            full_name=data.full_name,
            is_active=data.is_active,
            is_superuser=data.is_superuser,
            roles=roles,
        )
        self.db.add(user)
        await self.db.flush()

        # Audit log
        if self.audit and request:
            await self.audit.log_from_request(
                request,
                AuditAction.USER_CREATE,
                user_id=created_by,
                resource_type="user",
                resource_id=str(user.id),
                details={"email": user.email},
            )

        await self.db.refresh(user, ["roles"])
        return user

    async def update_user(
        self,
        user_id: uuid.UUID,
        data: UserUpdate,
        request: Request | None = None,
        updated_by: uuid.UUID | None = None,
    ) -> User:
        """Update a user."""
        user = await self.get_user_by_id(user_id)
        if user is None:
            raise NotFoundError(f"User with ID {user_id} not found")

        changes = {}

        # Check for duplicate email if changing
        if data.email and data.email != user.email:
            existing = await self.get_user_by_email(data.email)
            if existing:
                raise ConflictError(f"User with email '{data.email}' already exists")
            changes["email"] = {"from": user.email, "to": data.email}
            user.email = data.email

        if data.full_name is not None and data.full_name != user.full_name:
            changes["full_name"] = {"from": user.full_name, "to": data.full_name}
            user.full_name = data.full_name

        if data.is_active is not None and data.is_active != user.is_active:
            changes["is_active"] = {"from": user.is_active, "to": data.is_active}
            user.is_active = data.is_active

        if data.is_superuser is not None and data.is_superuser != user.is_superuser:
            changes["is_superuser"] = {"from": user.is_superuser, "to": data.is_superuser}
            user.is_superuser = data.is_superuser

        await self.db.flush()

        # Audit log
        if self.audit and request and changes:
            await self.audit.log_from_request(
                request,
                AuditAction.USER_UPDATE,
                user_id=updated_by,
                resource_type="user",
                resource_id=str(user.id),
                details={"changes": changes},
            )

        await self.db.refresh(user, ["roles"])
        return user

    async def deactivate_user(
        self,
        user_id: uuid.UUID,
        request: Request | None = None,
        deactivated_by: uuid.UUID | None = None,
    ) -> User:
        """Deactivate a user account."""
        user = await self.get_user_by_id(user_id)
        if user is None:
            raise NotFoundError(f"User with ID {user_id} not found")

        if not user.is_active:
            raise ConflictError("User is already deactivated")

        user.is_active = False
        await self.db.flush()

        # Audit log
        if self.audit and request:
            await self.audit.log_from_request(
                request,
                AuditAction.USER_UPDATE,
                user_id=deactivated_by,
                resource_type="user",
                resource_id=str(user.id),
                details={"action": "deactivate"},
            )

        return user

    async def reactivate_user(
        self,
        user_id: uuid.UUID,
        request: Request | None = None,
        reactivated_by: uuid.UUID | None = None,
    ) -> User:
        """Reactivate a user account."""
        user = await self.get_user_by_id(user_id)
        if user is None:
            raise NotFoundError(f"User with ID {user_id} not found")

        if user.is_active:
            raise ConflictError("User is already active")

        user.is_active = True
        await self.db.flush()

        # Audit log
        if self.audit and request:
            await self.audit.log_from_request(
                request,
                AuditAction.USER_UPDATE,
                user_id=reactivated_by,
                resource_type="user",
                resource_id=str(user.id),
                details={"action": "reactivate"},
            )

        return user

    async def unlock_user(
        self,
        user_id: uuid.UUID,
        request: Request | None = None,
        unlocked_by: uuid.UUID | None = None,
    ) -> User:
        """Unlock a locked user account."""
        user = await self.get_user_by_id(user_id)
        if user is None:
            raise NotFoundError(f"User with ID {user_id} not found")

        if user.locked_until is None:
            raise ConflictError("User account is not locked")

        user.locked_until = None
        user.failed_attempts = 0
        await self.db.flush()

        # Audit log
        if self.audit and request:
            await self.audit.log_from_request(
                request,
                AuditAction.USER_UNLOCK,
                user_id=unlocked_by,
                resource_type="user",
                resource_id=str(user.id),
            )

        return user

    async def get_user_roles(self, user_id: uuid.UUID) -> Sequence[Role]:
        """Get roles assigned to a user."""
        user = await self.get_user_by_id(user_id)
        if user is None:
            raise NotFoundError(f"User with ID {user_id} not found")
        return user.roles

    async def assign_roles(
        self,
        user_id: uuid.UUID,
        role_ids: list[uuid.UUID],
        request: Request | None = None,
        assigned_by: uuid.UUID | None = None,
    ) -> User:
        """Assign roles to a user (replaces existing)."""
        user = await self.get_user_by_id(user_id)
        if user is None:
            raise NotFoundError(f"User with ID {user_id} not found")

        # Get new roles
        result = await self.db.execute(
            select(Role).where(Role.id.in_(role_ids))
        )
        new_roles = list(result.scalars().all())

        old_role_ids = {str(r.id) for r in user.roles}
        new_role_ids = {str(r.id) for r in new_roles}

        user.roles = new_roles
        await self.db.flush()

        # Audit log
        if self.audit and request:
            await self.audit.log_from_request(
                request,
                AuditAction.ROLE_ASSIGN,
                user_id=assigned_by,
                resource_type="user",
                resource_id=str(user.id),
                details={
                    "added": list(new_role_ids - old_role_ids),
                    "removed": list(old_role_ids - new_role_ids),
                },
            )

        await self.db.refresh(user, ["roles"])
        return user

    async def reset_password(
        self,
        user_id: uuid.UUID,
        new_password: str,
        request: Request | None = None,
        reset_by: uuid.UUID | None = None,
    ) -> User:
        """Reset user password (admin action)."""
        user = await self.get_user_by_id(user_id)
        if user is None:
            raise NotFoundError(f"User with ID {user_id} not found")

        user.password_hash = hash_password(new_password)
        await self.db.flush()

        # Audit log
        if self.audit and request:
            await self.audit.log_from_request(
                request,
                AuditAction.PASSWORD_CHANGE,
                user_id=reset_by,
                resource_type="user",
                resource_id=str(user.id),
                details={"action": "admin_reset"},
            )

        return user
