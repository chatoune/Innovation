"""Database seed script for creating initial data."""

import asyncio
import sys
from pathlib import Path

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import select

from src.core.security import hash_password
from src.db.session import async_session_maker
from src.models.permission import Permission, PermissionCode
from src.models.role import Role
from src.models.user import User

# Default permissions to seed
DEFAULT_PERMISSIONS = [
    # User management
    {"code": PermissionCode.USERS_READ, "name": "View Users", "description": "View user list and details", "category": "users"},
    {"code": PermissionCode.USERS_CREATE, "name": "Create Users", "description": "Create new user accounts", "category": "users"},
    {"code": PermissionCode.USERS_UPDATE, "name": "Update Users", "description": "Modify user accounts", "category": "users"},
    {"code": PermissionCode.USERS_DELETE, "name": "Delete Users", "description": "Delete user accounts", "category": "users"},
    # Role management
    {"code": PermissionCode.ROLES_READ, "name": "View Roles", "description": "View roles and permissions", "category": "roles"},
    {"code": PermissionCode.ROLES_CREATE, "name": "Create Roles", "description": "Create new roles", "category": "roles"},
    {"code": PermissionCode.ROLES_UPDATE, "name": "Update Roles", "description": "Modify roles and permissions", "category": "roles"},
    {"code": PermissionCode.ROLES_DELETE, "name": "Delete Roles", "description": "Delete roles", "category": "roles"},
    # Data import
    {"code": PermissionCode.IMPORT_READ, "name": "View Imports", "description": "View import history", "category": "import"},
    {"code": PermissionCode.IMPORT_CREATE, "name": "Import Data", "description": "Upload and import Excel files", "category": "import"},
    {"code": PermissionCode.IMPORT_DELETE, "name": "Delete Imports", "description": "Delete import records", "category": "import"},
    # Audit
    {"code": PermissionCode.AUDIT_READ, "name": "View Audit Logs", "description": "View audit trail", "category": "audit"},
    # Admin
    {"code": PermissionCode.ADMIN_ALL, "name": "Full Admin Access", "description": "Full administrative access", "category": "admin"},
]


async def seed_permissions() -> dict[str, Permission]:
    """Seed default permissions."""
    async with async_session_maker() as session:
        permission_map = {}

        for perm_data in DEFAULT_PERMISSIONS:
            # Check if permission exists
            result = await session.execute(
                select(Permission).where(Permission.code == perm_data["code"])
            )
            existing = result.scalar_one_or_none()

            if existing:
                permission_map[perm_data["code"]] = existing
                print(f"  Permission '{perm_data['code']}' already exists.")
            else:
                permission = Permission(**perm_data)
                session.add(permission)
                await session.flush()
                permission_map[perm_data["code"]] = permission
                print(f"  Created permission: {perm_data['code']}")

        await session.commit()
        return permission_map


async def seed_roles(permission_map: dict[str, Permission]) -> dict[str, Role]:
    """Seed default roles."""
    async with async_session_maker() as session:
        role_map = {}

        # Admin role with all permissions
        result = await session.execute(select(Role).where(Role.name == "Administrator"))
        admin_role = result.scalar_one_or_none()
        if admin_role:
            print("  Role 'Administrator' already exists.")
            role_map["admin"] = admin_role
        else:
            admin_role = Role(
                name="Administrator",
                description="Full administrative access to all features",
                is_system=True,
                permissions=list(permission_map.values()),
            )
            session.add(admin_role)
            print("  Created role: Administrator")
            role_map["admin"] = admin_role

        # User Manager role
        result = await session.execute(select(Role).where(Role.name == "User Manager"))
        user_mgr_role = result.scalar_one_or_none()
        if user_mgr_role:
            print("  Role 'User Manager' already exists.")
            role_map["user_manager"] = user_mgr_role
        else:
            user_mgr_perms = [
                permission_map.get(PermissionCode.USERS_READ),
                permission_map.get(PermissionCode.USERS_CREATE),
                permission_map.get(PermissionCode.USERS_UPDATE),
                permission_map.get(PermissionCode.ROLES_READ),
            ]
            user_mgr_role = Role(
                name="User Manager",
                description="Can manage user accounts",
                is_system=True,
                permissions=[p for p in user_mgr_perms if p],
            )
            session.add(user_mgr_role)
            print("  Created role: User Manager")
            role_map["user_manager"] = user_mgr_role

        # Data Importer role
        result = await session.execute(select(Role).where(Role.name == "Data Importer"))
        importer_role = result.scalar_one_or_none()
        if importer_role:
            print("  Role 'Data Importer' already exists.")
            role_map["importer"] = importer_role
        else:
            importer_perms = [
                permission_map.get(PermissionCode.IMPORT_READ),
                permission_map.get(PermissionCode.IMPORT_CREATE),
            ]
            importer_role = Role(
                name="Data Importer",
                description="Can import data from Excel files",
                is_system=True,
                permissions=[p for p in importer_perms if p],
            )
            session.add(importer_role)
            print("  Created role: Data Importer")
            role_map["importer"] = importer_role

        # Viewer role (read-only)
        result = await session.execute(select(Role).where(Role.name == "Viewer"))
        viewer_role = result.scalar_one_or_none()
        if viewer_role:
            print("  Role 'Viewer' already exists.")
            role_map["viewer"] = viewer_role
        else:
            viewer_perms = [
                permission_map.get(PermissionCode.USERS_READ),
                permission_map.get(PermissionCode.ROLES_READ),
                permission_map.get(PermissionCode.IMPORT_READ),
            ]
            viewer_role = Role(
                name="Viewer",
                description="Read-only access to view data",
                is_system=True,
                permissions=[p for p in viewer_perms if p],
            )
            session.add(viewer_role)
            print("  Created role: Viewer")
            role_map["viewer"] = viewer_role

        await session.commit()
        return role_map


async def create_admin_user(
    email: str = "admin@example.com",
    password: str = "admin123!",
    full_name: str = "System Administrator",
) -> None:
    """Create the initial admin user if not exists."""
    async with async_session_maker() as session:
        # Check if admin user already exists
        result = await session.execute(select(User).where(User.email == email))
        existing_user = result.scalar_one_or_none()

        if existing_user:
            print(f"Admin user '{email}' already exists.")
            return

        # Create admin user (superuser flag grants all permissions)
        admin_user = User(
            email=email,
            password_hash=hash_password(password),
            full_name=full_name,
            is_active=True,
            is_superuser=True,
        )

        session.add(admin_user)
        await session.commit()

        print(f"Created admin user: {email}")
        print(f"  Password: {password}")
        print("  IMPORTANT: Change this password in production!")


async def seed_database() -> None:
    """Run all seed operations."""
    print("Seeding database...")

    print("\nSeeding permissions...")
    permission_map = await seed_permissions()

    print("\nSeeding roles...")
    await seed_roles(permission_map)

    print("\nCreating admin user...")
    await create_admin_user()

    print("\nDatabase seeding complete.")


if __name__ == "__main__":
    asyncio.run(seed_database())
