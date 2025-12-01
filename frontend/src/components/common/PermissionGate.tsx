/**
 * Component for conditional rendering based on permissions.
 */

import { ReactNode } from 'react';
import { usePermissions } from '../../hooks/usePermissions';

interface PermissionGateProps {
  children: ReactNode;
  /** Single permission to check */
  permission?: string;
  /** Multiple permissions - user must have any of these */
  anyOf?: string[];
  /** Multiple permissions - user must have all of these */
  allOf?: string[];
  /** Content to render if permission check fails */
  fallback?: ReactNode;
}

/**
 * Conditionally renders children based on user permissions.
 *
 * Usage:
 * ```tsx
 * // Single permission
 * <PermissionGate permission="users:create">
 *   <CreateUserButton />
 * </PermissionGate>
 *
 * // Any of multiple permissions
 * <PermissionGate anyOf={["users:update", "admin:all"]}>
 *   <EditUserButton />
 * </PermissionGate>
 *
 * // All of multiple permissions
 * <PermissionGate allOf={["users:read", "users:delete"]}>
 *   <DeleteUserSection />
 * </PermissionGate>
 *
 * // With fallback
 * <PermissionGate permission="admin:all" fallback={<AccessDenied />}>
 *   <AdminPanel />
 * </PermissionGate>
 * ```
 */
export default function PermissionGate({
  children,
  permission,
  anyOf,
  allOf,
  fallback = null,
}: PermissionGateProps) {
  const { hasPermission, hasAnyPermission, hasAllPermissions } = usePermissions();

  let hasAccess = false;

  if (permission) {
    hasAccess = hasPermission(permission);
  } else if (anyOf && anyOf.length > 0) {
    hasAccess = hasAnyPermission(anyOf);
  } else if (allOf && allOf.length > 0) {
    hasAccess = hasAllPermissions(allOf);
  } else {
    // No permission specified, allow access
    hasAccess = true;
  }

  if (!hasAccess) {
    return <>{fallback}</>;
  }

  return <>{children}</>;
}

/**
 * HOC for wrapping components with permission checks.
 */
export function withPermission<P extends object>(
  WrappedComponent: React.ComponentType<P>,
  permission: string,
  FallbackComponent?: React.ComponentType
) {
  return function PermissionWrapper(props: P) {
    return (
      <PermissionGate
        permission={permission}
        fallback={FallbackComponent ? <FallbackComponent /> : null}
      >
        <WrappedComponent {...props} />
      </PermissionGate>
    );
  };
}
