/**
 * User list table component.
 */

import { post, ApiError } from '../../services/api';
import PermissionGate from '../common/PermissionGate';
import { Permissions } from '../../hooks/usePermissions';

interface UserListItem {
  id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  is_superuser: boolean;
  role_count: number;
  last_login: string | null;
}

interface UserTableProps {
  users: UserListItem[];
  isLoading: boolean;
  onViewUser: (userId: string) => void;
  onRefresh: () => void;
}

export default function UserTable({ users, isLoading, onViewUser, onRefresh }: UserTableProps) {
  async function handleDeactivate(userId: string) {
    if (!confirm('Are you sure you want to deactivate this user?')) {
      return;
    }

    try {
      await post(`/users/${userId}/deactivate`);
      onRefresh();
    } catch (err) {
      const apiError = err as ApiError;
      alert(apiError.message || 'Failed to deactivate user');
    }
  }

  async function handleReactivate(userId: string) {
    try {
      await post(`/users/${userId}/reactivate`);
      onRefresh();
    } catch (err) {
      const apiError = err as ApiError;
      alert(apiError.message || 'Failed to reactivate user');
    }
  }

  if (isLoading) {
    return (
      <div className="bg-white shadow rounded-lg p-8 text-center">
        <p className="text-gray-500">Loading users...</p>
      </div>
    );
  }

  if (users.length === 0) {
    return (
      <div className="bg-white shadow rounded-lg p-8 text-center">
        <p className="text-gray-500">No users found</p>
      </div>
    );
  }

  return (
    <div className="bg-white shadow rounded-lg overflow-hidden">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              User
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Status
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Roles
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Last Login
            </th>
            <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
              Actions
            </th>
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {users.map((user) => (
            <tr key={user.id} className="hover:bg-gray-50">
              <td className="px-6 py-4 whitespace-nowrap">
                <div className="flex items-center">
                  <div className="h-10 w-10 flex-shrink-0">
                    <div className="h-10 w-10 rounded-full bg-gray-200 flex items-center justify-center">
                      <span className="text-sm font-medium text-gray-600">
                        {user.email[0].toUpperCase()}
                      </span>
                    </div>
                  </div>
                  <div className="ml-4">
                    <div className="text-sm font-medium text-gray-900">
                      {user.full_name || 'No name'}
                    </div>
                    <div className="text-sm text-gray-500">{user.email}</div>
                  </div>
                </div>
              </td>
              <td className="px-6 py-4 whitespace-nowrap">
                <div className="flex flex-col gap-1">
                  <span
                    className={`inline-flex px-2 text-xs leading-5 font-semibold rounded-full ${
                      user.is_active
                        ? 'bg-green-100 text-green-800'
                        : 'bg-red-100 text-red-800'
                    }`}
                  >
                    {user.is_active ? 'Active' : 'Inactive'}
                  </span>
                  {user.is_superuser && (
                    <span className="inline-flex px-2 text-xs leading-5 font-semibold rounded-full bg-purple-100 text-purple-800">
                      Superuser
                    </span>
                  )}
                </div>
              </td>
              <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                {user.role_count} role{user.role_count !== 1 ? 's' : ''}
              </td>
              <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                {user.last_login
                  ? new Date(user.last_login).toLocaleDateString()
                  : 'Never'}
              </td>
              <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                <div className="flex justify-end gap-2">
                  <button
                    onClick={() => onViewUser(user.id)}
                    className="text-indigo-600 hover:text-indigo-900"
                  >
                    View
                  </button>
                  <PermissionGate permission={Permissions.USERS_UPDATE}>
                    {user.is_active ? (
                      <button
                        onClick={() => handleDeactivate(user.id)}
                        className="text-red-600 hover:text-red-900"
                      >
                        Deactivate
                      </button>
                    ) : (
                      <button
                        onClick={() => handleReactivate(user.id)}
                        className="text-green-600 hover:text-green-900"
                      >
                        Reactivate
                      </button>
                    )}
                  </PermissionGate>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
