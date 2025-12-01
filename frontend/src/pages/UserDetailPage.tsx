/**
 * User detail page for viewing and editing single user.
 */

import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { get, post, put, ApiError } from '../services/api';
import Layout from '../components/layout/Layout';
import PermissionGate from '../components/common/PermissionGate';
import { Permissions } from '../hooks/usePermissions';
import UserForm from '../components/users/UserForm';
import UserRoleAssignment from '../components/users/UserRoleAssignment';

interface Role {
  id: string;
  name: string;
  description: string | null;
}

interface UserDetail {
  id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  is_superuser: boolean;
  failed_attempts: number;
  locked_until: string | null;
  last_login: string | null;
  created_at: string;
  updated_at: string;
  roles: Role[];
}

export default function UserDetailPage() {
  const { userId } = useParams<{ userId: string }>();
  const navigate = useNavigate();

  const [user, setUser] = useState<UserDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showEditForm, setShowEditForm] = useState(false);
  const [showRoleEditor, setShowRoleEditor] = useState(false);
  const [selectedRoleIds, setSelectedRoleIds] = useState<string[]>([]);

  async function loadUser() {
    if (!userId) return;

    setIsLoading(true);
    setError(null);

    try {
      const data = await get<UserDetail>(`/users/${userId}`);
      setUser(data);
      setSelectedRoleIds(data.roles.map((r) => r.id));
    } catch (err) {
      const apiError = err as ApiError;
      setError(apiError.message || 'Failed to load user');
    } finally {
      setIsLoading(false);
    }
  }

  async function handleUnlock() {
    if (!userId) return;

    try {
      await post(`/users/${userId}/unlock`);
      loadUser();
    } catch (err) {
      const apiError = err as ApiError;
      setError(apiError.message || 'Failed to unlock user');
    }
  }

  async function handleSaveRoles() {
    if (!userId) return;

    try {
      await put(`/users/${userId}/roles`, {
        role_ids: selectedRoleIds,
      });
      setShowRoleEditor(false);
      loadUser();
    } catch (err) {
      const apiError = err as ApiError;
      setError(apiError.message || 'Failed to save roles');
    }
  }

  function handleFormClose() {
    setShowEditForm(false);
    loadUser();
  }

  useEffect(() => {
    loadUser();
  }, [userId]);

  if (isLoading) {
    return (
      <Layout>
        <div className="text-center py-8">
          <p className="text-gray-500">Loading user...</p>
        </div>
      </Layout>
    );
  }

  if (error || !user) {
    return (
      <Layout>
        <div className="text-center py-8">
          <p className="text-red-500">{error || 'User not found'}</p>
          <button
            onClick={() => navigate('/users')}
            className="mt-4 text-indigo-600 hover:text-indigo-800"
          >
            Back to Users
          </button>
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex justify-between items-center">
          <div>
            <button
              onClick={() => navigate('/users')}
              className="text-sm text-gray-500 hover:text-gray-700 mb-2"
            >
              &larr; Back to Users
            </button>
            <h1 className="text-2xl font-bold text-gray-900">{user.full_name || user.email}</h1>
          </div>
          <PermissionGate permission={Permissions.USERS_UPDATE}>
            <button
              onClick={() => setShowEditForm(true)}
              className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
            >
              Edit User
            </button>
          </PermissionGate>
        </div>

        {/* User info */}
        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">User Information</h2>
          <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <dt className="text-sm font-medium text-gray-500">Email</dt>
              <dd className="mt-1 text-sm text-gray-900">{user.email}</dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-gray-500">Full Name</dt>
              <dd className="mt-1 text-sm text-gray-900">{user.full_name || 'Not set'}</dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-gray-500">Status</dt>
              <dd className="mt-1">
                <span
                  className={`inline-flex px-2 text-xs leading-5 font-semibold rounded-full ${
                    user.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                  }`}
                >
                  {user.is_active ? 'Active' : 'Inactive'}
                </span>
              </dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-gray-500">Type</dt>
              <dd className="mt-1">
                <span
                  className={`inline-flex px-2 text-xs leading-5 font-semibold rounded-full ${
                    user.is_superuser ? 'bg-purple-100 text-purple-800' : 'bg-gray-100 text-gray-800'
                  }`}
                >
                  {user.is_superuser ? 'Superuser' : 'Standard User'}
                </span>
              </dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-gray-500">Last Login</dt>
              <dd className="mt-1 text-sm text-gray-900">
                {user.last_login ? new Date(user.last_login).toLocaleString() : 'Never'}
              </dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-gray-500">Created</dt>
              <dd className="mt-1 text-sm text-gray-900">
                {new Date(user.created_at).toLocaleString()}
              </dd>
            </div>
            {user.locked_until && (
              <div className="sm:col-span-2">
                <dt className="text-sm font-medium text-gray-500">Account Locked Until</dt>
                <dd className="mt-1 flex items-center gap-4">
                  <span className="text-sm text-red-600">
                    {new Date(user.locked_until).toLocaleString()}
                  </span>
                  <PermissionGate permission={Permissions.USERS_UPDATE}>
                    <button
                      onClick={handleUnlock}
                      className="text-sm text-indigo-600 hover:text-indigo-800"
                    >
                      Unlock Account
                    </button>
                  </PermissionGate>
                </dd>
              </div>
            )}
          </dl>
        </div>

        {/* Roles */}
        <div className="bg-white shadow rounded-lg p-6">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-lg font-semibold text-gray-900">Assigned Roles</h2>
            <PermissionGate permission={Permissions.USERS_UPDATE}>
              {showRoleEditor ? (
                <div className="flex gap-2">
                  <button
                    onClick={() => setShowRoleEditor(false)}
                    className="px-3 py-1 text-sm text-gray-600 hover:text-gray-800"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleSaveRoles}
                    className="px-3 py-1 text-sm bg-indigo-600 text-white rounded hover:bg-indigo-700"
                  >
                    Save Roles
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => setShowRoleEditor(true)}
                  className="px-3 py-1 text-sm bg-indigo-100 text-indigo-700 rounded hover:bg-indigo-200"
                >
                  Edit Roles
                </button>
              )}
            </PermissionGate>
          </div>

          {showRoleEditor ? (
            <UserRoleAssignment selectedRoleIds={selectedRoleIds} onChange={setSelectedRoleIds} />
          ) : (
            <div className="flex flex-wrap gap-2">
              {user.roles.length > 0 ? (
                user.roles.map((role) => (
                  <span
                    key={role.id}
                    className="inline-flex items-center px-3 py-1 rounded-full text-sm bg-blue-100 text-blue-800"
                    title={role.description || ''}
                  >
                    {role.name}
                  </span>
                ))
              ) : (
                <p className="text-sm text-gray-500">No roles assigned</p>
              )}
            </div>
          )}
        </div>

        {/* Edit form modal */}
        {showEditForm && <UserForm userId={userId} onClose={handleFormClose} />}
      </div>
    </Layout>
  );
}
