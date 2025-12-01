"""Error handling middleware and exception handlers."""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError


class AppException(Exception):
    """Base application exception."""

    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        error_code: str | None = None,
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or "APP_ERROR"
        super().__init__(message)


class AuthenticationError(AppException):
    """Authentication failed."""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="AUTH_ERROR",
        )


class AuthorizationError(AppException):
    """Authorization failed - insufficient permissions."""

    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            error_code="AUTHZ_ERROR",
        )


class NotFoundError(AppException):
    """Resource not found."""

    def __init__(self, message: str = "Resource not found"):
        super().__init__(
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="NOT_FOUND",
        )


class ConflictError(AppException):
    """Resource conflict (e.g., duplicate entry)."""

    def __init__(self, message: str = "Resource conflict"):
        super().__init__(
            message=message,
            status_code=status.HTTP_409_CONFLICT,
            error_code="CONFLICT",
        )


class ValidationError(AppException):
    """Validation error."""

    def __init__(self, message: str = "Validation error"):
        super().__init__(
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_code="VALIDATION_ERROR",
        )


class AccountLockedError(AppException):
    """Account is locked due to failed login attempts."""

    def __init__(self, message: str = "Account is locked"):
        super().__init__(
            message=message,
            status_code=status.HTTP_423_LOCKED,
            error_code="ACCOUNT_LOCKED",
        )


def add_error_handlers(app: FastAPI) -> None:
    """Add exception handlers to the FastAPI app."""

    @app.exception_handler(AppException)
    async def app_exception_handler(
        request: Request, exc: AppException
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.error_code,
                "message": exc.message,
            },
        )

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(
        request: Request, exc: IntegrityError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "error": "INTEGRITY_ERROR",
                "message": "Database integrity constraint violated",
            },
        )

    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_error_handler(
        request: Request, exc: SQLAlchemyError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "DATABASE_ERROR",
                "message": "A database error occurred",
            },
        )
