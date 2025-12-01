/**
 * Hook for checking user permissions.
 */

import { useMemo } from 'react';
import { useAuthStore } from '../stores/authStore';

/**
 * Hook that provides permission checking utilities.
 */
export function usePermissions() {
  const { user } = useAuthStore();

  const permissions = useMemo(() => {
    return new Set(user?.permissions || []);
  }, [user?.permissions]);

  const isSuperuser = user?.is_superuser ?? false;

  /**
   * Check if user has a specific permission.
   */
  function hasPermission(permission: string): boolean {
    // Superusers have all permissions (indicated by "*" or is_superuser flag)
    if (isSuperuser || permissions.has('*')) {
      return true;
    }
    return permissions.has(permission);
  }

  /**
   * Check if user has any of the specified permissions.
   */
  function hasAnyPermission(permissionList: string[]): boolean {
    if (isSuperuser || permissions.has('*')) {
      return true;
    }
    return permissionList.some((p) => permissions.has(p));
  }

  /**
   * Check if user has all of the specified permissions.
   */
  function hasAllPermissions(permissionList: string[]): boolean {
    if (isSuperuser || permissions.has('*')) {
      return true;
    }
    return permissionList.every((p) => permissions.has(p));
  }

  return {
    permissions,
    isSuperuser,
    hasPermission,
    hasAnyPermission,
    hasAllPermissions,
  };
}

/**
 * Standard permission codes matching backend PermissionCode.
 */
export const Permissions = {
  // User management
  USERS_READ: 'users:read',
  USERS_CREATE: 'users:create',
  USERS_UPDATE: 'users:update',
  USERS_DELETE: 'users:delete',

  // Role management
  ROLES_READ: 'roles:read',
  ROLES_CREATE: 'roles:create',
  ROLES_UPDATE: 'roles:update',
  ROLES_DELETE: 'roles:delete',

  // Data import
  IMPORT_READ: 'import:read',
  IMPORT_CREATE: 'import:create',
  IMPORT_DELETE: 'import:delete',

  // Audit logs
  AUDIT_READ: 'audit:read',

  // Admin (superuser-only)
  ADMIN_ALL: 'admin:all',
} as const;

export type PermissionCode = (typeof Permissions)[keyof typeof Permissions];
