/**
 * Role assignment component for user management.
 */

import { useState, useEffect } from 'react';
import { get, ApiError } from '../../services/api';

interface Role {
  id: string;
  name: string;
  description: string | null;
  is_system: boolean;
  permission_count: number;
  user_count: number;
}

interface UserRoleAssignmentProps {
  selectedRoleIds: string[];
  onChange: (roleIds: string[]) => void;
}

export default function UserRoleAssignment({
  selectedRoleIds,
  onChange,
}: UserRoleAssignmentProps) {
  const [roles, setRoles] = useState<Role[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadRoles() {
      try {
        const data = await get<Role[]>('/roles');
        setRoles(data);
      } catch (err) {
        const apiError = err as ApiError;
        setError(apiError.message || 'Failed to load roles');
      } finally {
        setIsLoading(false);
      }
    }
    loadRoles();
  }, []);

  function handleToggle(roleId: string) {
    if (selectedRoleIds.includes(roleId)) {
      onChange(selectedRoleIds.filter((id) => id !== roleId));
    } else {
      onChange([...selectedRoleIds, roleId]);
    }
  }

  if (isLoading) {
    return <p className="text-sm text-gray-500">Loading roles...</p>;
  }

  if (error) {
    return <p className="text-sm text-red-500">{error}</p>;
  }

  return (
    <div className="border border-gray-300 rounded-md p-3 max-h-48 overflow-y-auto">
      {roles.length === 0 ? (
        <p className="text-sm text-gray-500">No roles available</p>
      ) : (
        <div className="space-y-2">
          {roles.map((role) => (
            <label
              key={role.id}
              className="flex items-start space-x-3 p-2 rounded hover:bg-gray-50 cursor-pointer"
            >
              <input
                type="checkbox"
                checked={selectedRoleIds.includes(role.id)}
                onChange={() => handleToggle(role.id)}
                className="mt-0.5 h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
              />
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-gray-900">{role.name}</span>
                  {role.is_system && (
                    <span className="text-xs bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded">
                      System
                    </span>
                  )}
                </div>
                {role.description && (
                  <p className="text-xs text-gray-500">{role.description}</p>
                )}
                <p className="text-xs text-gray-400 mt-0.5">
                  {role.permission_count} permissions
                </p>
              </div>
            </label>
          ))}
        </div>
      )}
    </div>
  );
}
