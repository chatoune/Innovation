"""Audit logging service for tracking system events."""

import uuid
from datetime import UTC, datetime

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.audit_log import AuditAction, AuditLog


class AuditService:
    """Service for creating audit log entries."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def log(
        self,
        action: AuditAction | str,
        *,
        user_id: uuid.UUID | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        details: dict | None = None,
        status: str = "success",
        error_message: str | None = None,
    ) -> AuditLog:
        """Create an audit log entry.

        Args:
            action: The action being logged (from AuditAction enum or string)
            user_id: ID of the user performing the action
            resource_type: Type of resource affected (e.g., "user", "role")
            resource_id: ID of the affected resource
            ip_address: Client IP address
            user_agent: Client user agent string
            details: Additional details as JSON
            status: Status of the action ("success" or "failure")
            error_message: Error message if status is "failure"

        Returns:
            The created AuditLog entry
        """
        action_str = action.value if isinstance(action, AuditAction) else action

        audit_log = AuditLog(
            timestamp=datetime.now(UTC),
            user_id=user_id,
            action=action_str,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details,
            status=status,
            error_message=error_message,
        )

        self.db.add(audit_log)
        await self.db.flush()

        return audit_log

    async def log_from_request(
        self,
        request: Request,
        action: AuditAction | str,
        *,
        user_id: uuid.UUID | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        details: dict | None = None,
        status: str = "success",
        error_message: str | None = None,
    ) -> AuditLog:
        """Create an audit log entry extracting request metadata.

        Automatically extracts IP address and user agent from the request.

        Args:
            request: FastAPI request object
            action: The action being logged
            user_id: ID of the user performing the action
            resource_type: Type of resource affected
            resource_id: ID of the affected resource
            details: Additional details as JSON
            status: Status of the action
            error_message: Error message if status is "failure"

        Returns:
            The created AuditLog entry
        """
        # Extract client IP (handle proxied requests)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            ip_address = forwarded.split(",")[0].strip()
        else:
            ip_address = request.client.host if request.client else None

        user_agent = request.headers.get("User-Agent")

        return await self.log(
            action,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details,
            status=status,
            error_message=error_message,
        )


async def get_audit_service(db: AsyncSession) -> AuditService:
    """Factory function to create AuditService instance."""
    return AuditService(db)
