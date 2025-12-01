/**
 * Role creation and editing form component.
 */

import { useState, useEffect, FormEvent } from 'react';
import { get, post, patch, put, ApiError } from '../../services/api';
import PermissionSelector from './PermissionSelector';

interface Permission {
  id: string;
  code: string;
  name: string;
  description: string | null;
  category: string;
}

interface RoleDetail {
  id: string;
  name: string;
  description: string | null;
  is_system: boolean;
  permissions: Permission[];
}

interface RoleFormProps {
  role: RoleDetail | null;
  onClose: () => void;
}

export default function RoleForm({ role, onClose }: RoleFormProps) {
  const [name, setName] = useState(role?.name || '');
  const [description, setDescription] = useState(role?.description || '');
  const [selectedPermissionIds, setSelectedPermissionIds] = useState<string[]>(
    role?.permissions.map((p) => p.id) || []
  );
  const [allPermissions, setAllPermissions] = useState<Permission[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isEditMode = role !== null;

  useEffect(() => {
    async function loadPermissions() {
      try {
        const data = await get<Permission[]>('/roles/permissions');
        setAllPermissions(data);
      } catch (err) {
        const apiError = err as ApiError;
        setError(apiError.message || 'Failed to load permissions');
      }
    }
    loadPermissions();
  }, []);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setIsLoading(true);
    setError(null);

    try {
      if (isEditMode && role) {
        // Update role
        await patch(`/roles/${role.id}`, {
          name,
          description,
        });
        // Update permissions
        await put(`/roles/${role.id}/permissions`, {
          permission_ids: selectedPermissionIds,
        });
      } else {
        // Create new role
        await post('/roles', {
          name,
          description,
          permission_ids: selectedPermissionIds,
        });
      }
      onClose();
    } catch (err) {
      const apiError = err as ApiError;
      setError(apiError.message || 'Failed to save role');
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-gray-600 bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-xl font-semibold text-gray-900">
            {isEditMode ? 'Edit Role' : 'Create Role'}
          </h2>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4 overflow-y-auto max-h-[calc(90vh-120px)]">
          {error && (
            <div className="rounded-md bg-red-50 p-4">
              <p className="text-sm text-red-800">{error}</p>
            </div>
          )}

          {/* Name */}
          <div>
            <label htmlFor="name" className="block text-sm font-medium text-gray-700">
              Role Name
            </label>
            <input
              type="text"
              id="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
              placeholder="Enter role name"
            />
          </div>

          {/* Description */}
          <div>
            <label htmlFor="description" className="block text-sm font-medium text-gray-700">
              Description
            </label>
            <textarea
              id="description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
              placeholder="Enter role description"
            />
          </div>

          {/* Permissions */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Permissions
            </label>
            <PermissionSelector
              permissions={allPermissions}
              selectedIds={selectedPermissionIds}
              onChange={setSelectedPermissionIds}
            />
          </div>

          {/* Actions */}
          <div className="flex justify-end gap-3 pt-4 border-t border-gray-200">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isLoading}
              className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-md hover:bg-indigo-700 disabled:opacity-50"
            >
              {isLoading ? 'Saving...' : isEditMode ? 'Save Changes' : 'Create Role'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
