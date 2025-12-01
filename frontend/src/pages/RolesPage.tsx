/**
 * Role management page.
 */

import { useState, useEffect } from 'react';
import { get, del, ApiError } from '../services/api';
import Layout from '../components/layout/Layout';
import PermissionGate from '../components/common/PermissionGate';
import { Permissions } from '../hooks/usePermissions';
import RoleForm from '../components/roles/RoleForm';

interface Permission {
  id: string;
  code: string;
  name: string;
  description: string | null;
  category: string;
}

interface Role {
  id: string;
  name: string;
  description: string | null;
  is_system: boolean;
  permission_count: number;
  user_count: number;
}

interface RoleDetail {
  id: string;
  name: string;
  description: string | null;
  is_system: boolean;
  permissions: Permission[];
  created_at: string;
  updated_at: string;
}

export default function RolesPage() {
  const [roles, setRoles] = useState<Role[]>([]);
  const [selectedRole, setSelectedRole] = useState<RoleDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [editMode, setEditMode] = useState(false);

  async function loadRoles() {
    setIsLoading(true);
    setError(null);
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

  async function loadRoleDetails(roleId: string) {
    try {
      const data = await get<RoleDetail>(`/roles/${roleId}`);
      setSelectedRole(data);
    } catch (err) {
      const apiError = err as ApiError;
      setError(apiError.message || 'Failed to load role details');
    }
  }

  async function handleDelete(roleId: string) {
    if (!confirm('Are you sure you want to delete this role?')) {
      return;
    }

    try {
      await del(`/roles/${roleId}`);
      await loadRoles();
      if (selectedRole?.id === roleId) {
        setSelectedRole(null);
      }
    } catch (err) {
      const apiError = err as ApiError;
      setError(apiError.message || 'Failed to delete role');
    }
  }

  function handleCreateNew() {
    setSelectedRole(null);
    setEditMode(false);
    setShowForm(true);
  }

  function handleEdit(role: RoleDetail) {
    setSelectedRole(role);
    setEditMode(true);
    setShowForm(true);
  }

  function handleFormClose() {
    setShowForm(false);
    setEditMode(false);
    loadRoles();
  }

  useEffect(() => {
    loadRoles();
  }, []);

  return (
    <Layout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex justify-between items-center">
          <h1 className="text-2xl font-bold text-gray-900">Role Management</h1>
          <PermissionGate permission={Permissions.ROLES_CREATE}>
            <button
              onClick={handleCreateNew}
              className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
            >
              Create Role
            </button>
          </PermissionGate>
        </div>

        {/* Error message */}
        {error && (
          <div className="rounded-md bg-red-50 p-4">
            <p className="text-sm text-red-800">{error}</p>
          </div>
        )}

        {/* Loading state */}
        {isLoading ? (
          <div className="text-center py-8">
            <p className="text-gray-500">Loading roles...</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Roles list */}
            <div className="lg:col-span-1 bg-white shadow rounded-lg">
              <div className="p-4 border-b border-gray-200">
                <h2 className="text-lg font-medium text-gray-900">Roles</h2>
              </div>
              <ul className="divide-y divide-gray-200">
                {roles.map((role) => (
                  <li
                    key={role.id}
                    className={`p-4 hover:bg-gray-50 cursor-pointer ${
                      selectedRole?.id === role.id ? 'bg-indigo-50' : ''
                    }`}
                    onClick={() => loadRoleDetails(role.id)}
                  >
                    <div className="flex justify-between items-start">
                      <div>
                        <p className="font-medium text-gray-900">{role.name}</p>
                        <p className="text-sm text-gray-500">{role.description}</p>
                        <div className="mt-1 flex gap-2 text-xs text-gray-400">
                          <span>{role.permission_count} permissions</span>
                          <span>•</span>
                          <span>{role.user_count} users</span>
                        </div>
                      </div>
                      {role.is_system && (
                        <span className="text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded">
                          System
                        </span>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            </div>

            {/* Role details */}
            <div className="lg:col-span-2 bg-white shadow rounded-lg">
              {selectedRole ? (
                <div>
                  <div className="p-4 border-b border-gray-200 flex justify-between items-center">
                    <h2 className="text-lg font-medium text-gray-900">
                      {selectedRole.name}
                    </h2>
                    {!selectedRole.is_system && (
                      <div className="flex gap-2">
                        <PermissionGate permission={Permissions.ROLES_UPDATE}>
                          <button
                            onClick={() => handleEdit(selectedRole)}
                            className="px-3 py-1 text-sm bg-indigo-100 text-indigo-700 rounded hover:bg-indigo-200"
                          >
                            Edit
                          </button>
                        </PermissionGate>
                        <PermissionGate permission={Permissions.ROLES_DELETE}>
                          <button
                            onClick={() => handleDelete(selectedRole.id)}
                            className="px-3 py-1 text-sm bg-red-100 text-red-700 rounded hover:bg-red-200"
                          >
                            Delete
                          </button>
                        </PermissionGate>
                      </div>
                    )}
                  </div>
                  <div className="p-4">
                    <p className="text-gray-600 mb-4">{selectedRole.description}</p>
                    <h3 className="font-medium text-gray-900 mb-2">Permissions</h3>
                    <div className="flex flex-wrap gap-2">
                      {selectedRole.permissions.map((perm) => (
                        <span
                          key={perm.id}
                          className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800"
                          title={perm.description || ''}
                        >
                          {perm.name}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="p-8 text-center text-gray-500">
                  Select a role to view details
                </div>
              )}
            </div>
          </div>
        )}

        {/* Role form modal */}
        {showForm && (
          <RoleForm
            role={editMode ? selectedRole : null}
            onClose={handleFormClose}
          />
        )}
      </div>
    </Layout>
  );
}
