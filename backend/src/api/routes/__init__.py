"""API route aggregation."""

from fastapi import APIRouter

from src.api.routes import auth, roles, users

api_router = APIRouter()

# Authentication routes
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])

# Role and permission management routes
api_router.include_router(roles.router, prefix="/roles", tags=["Roles"])

# User management routes
api_router.include_router(users.router, prefix="/users", tags=["Users"])
