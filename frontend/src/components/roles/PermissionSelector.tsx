/**
 * Permission selector component for role management.
 */

import { useMemo } from 'react';

interface Permission {
  id: string;
  code: string;
  name: string;
  description: string | null;
  category: string;
}

interface PermissionSelectorProps {
  permissions: Permission[];
  selectedIds: string[];
  onChange: (ids: string[]) => void;
}

export default function PermissionSelector({
  permissions,
  selectedIds,
  onChange,
}: PermissionSelectorProps) {
  // Group permissions by category
  const groupedPermissions = useMemo(() => {
    const groups: Record<string, Permission[]> = {};
    for (const perm of permissions) {
      const category = perm.category || 'general';
      if (!groups[category]) {
        groups[category] = [];
      }
      groups[category].push(perm);
    }
    return groups;
  }, [permissions]);

  function handleToggle(permissionId: string) {
    if (selectedIds.includes(permissionId)) {
      onChange(selectedIds.filter((id) => id !== permissionId));
    } else {
      onChange([...selectedIds, permissionId]);
    }
  }

  function handleSelectAll(category: string) {
    const categoryPermIds = groupedPermissions[category]?.map((p) => p.id) || [];
    const newSelectedIds = new Set(selectedIds);
    for (const id of categoryPermIds) {
      newSelectedIds.add(id);
    }
    onChange(Array.from(newSelectedIds));
  }

  function handleDeselectAll(category: string) {
    const categoryPermIds = new Set(groupedPermissions[category]?.map((p) => p.id) || []);
    onChange(selectedIds.filter((id) => !categoryPermIds.has(id)));
  }

  function getCategoryLabel(category: string): string {
    const labels: Record<string, string> = {
      users: 'User Management',
      roles: 'Role Management',
      import: 'Data Import',
      audit: 'Audit Logs',
      admin: 'Administration',
      general: 'General',
    };
    return labels[category] || category.charAt(0).toUpperCase() + category.slice(1);
  }

  return (
    <div className="border border-gray-300 rounded-md p-4 space-y-4 max-h-64 overflow-y-auto">
      {Object.entries(groupedPermissions).map(([category, perms]) => {
        // These could be used for visual indicators in the future
        const _allSelected = perms.every((p) => selectedIds.includes(p.id));
        const _someSelected = perms.some((p) => selectedIds.includes(p.id));
        void _allSelected;
        void _someSelected;

        return (
          <div key={category} className="space-y-2">
            {/* Category header */}
            <div className="flex items-center justify-between">
              <h4 className="text-sm font-medium text-gray-700">
                {getCategoryLabel(category)}
              </h4>
              <div className="flex gap-2 text-xs">
                <button
                  type="button"
                  onClick={() => handleSelectAll(category)}
                  className="text-indigo-600 hover:text-indigo-800"
                >
                  Select all
                </button>
                <span className="text-gray-300">|</span>
                <button
                  type="button"
                  onClick={() => handleDeselectAll(category)}
                  className="text-gray-600 hover:text-gray-800"
                >
                  Clear
                </button>
              </div>
            </div>

            {/* Permission checkboxes */}
            <div className="grid grid-cols-2 gap-2">
              {perms.map((perm) => (
                <label
                  key={perm.id}
                  className="flex items-start space-x-2 p-2 rounded hover:bg-gray-50 cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={selectedIds.includes(perm.id)}
                    onChange={() => handleToggle(perm.id)}
                    className="mt-0.5 h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
                  />
                  <div className="flex-1 min-w-0">
                    <span className="text-sm text-gray-900">{perm.name}</span>
                    {perm.description && (
                      <p className="text-xs text-gray-500 truncate" title={perm.description}>
                        {perm.description}
                      </p>
                    )}
                  </div>
                </label>
              ))}
            </div>
          </div>
        );
      })}

      {Object.keys(groupedPermissions).length === 0 && (
        <p className="text-sm text-gray-500 text-center py-4">
          No permissions available
        </p>
      )}
    </div>
  );
}
