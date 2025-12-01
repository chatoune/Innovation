"""Authentication routes."""

from fastapi import APIRouter, Cookie, Request, Response

from src.api.deps.auth import (
    AuditDep,
    CurrentUserDep,
    DbDep,
)
from src.schemas.auth import AuthResponse, CurrentUser, LoginRequest
from src.services.auth import AuthService

router = APIRouter()


@router.post("/login", response_model=AuthResponse)
async def login(
    request: Request,
    response: Response,
    login_data: LoginRequest,
    db: DbDep,
    audit: AuditDep,
) -> AuthResponse:
    """Authenticate user with email and password.

    Returns JWT access token and sets refresh token in HTTPOnly cookie.
    Account locks after 5 failed attempts for 15 minutes.
    """
    auth_service = AuthService(db, audit)
    result = await auth_service.login(
        email=login_data.email,
        password=login_data.password,
        request=request,
        response=response,
    )
    return result


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    current_user: CurrentUserDep,
    db: DbDep,
    audit: AuditDep,
) -> dict[str, str]:
    """Logout current user.

    Clears the refresh token cookie.
    """
    auth_service = AuthService(db, audit)
    await auth_service.logout(
        user_id=current_user.id,
        request=request,
        response=response,
    )
    return {"message": "Successfully logged out"}


@router.get("/me", response_model=CurrentUser)
async def get_current_user_info(
    current_user: CurrentUserDep,
) -> CurrentUser:
    """Get current authenticated user information."""
    return current_user


@router.post("/refresh", response_model=AuthResponse)
async def refresh_token(
    response: Response,
    db: DbDep,
    audit: AuditDep,
    refresh_token: str | None = Cookie(None),
) -> AuthResponse:
    """Refresh access token using refresh token from cookie.

    Returns new access token and rotates refresh token.
    """
    from src.api.middleware.errors import AuthenticationError

    if refresh_token is None:
        raise AuthenticationError("Refresh token not found")

    auth_service = AuthService(db, audit)
    result = await auth_service.refresh_tokens(
        refresh_token=refresh_token,
        response=response,
    )
    return result
