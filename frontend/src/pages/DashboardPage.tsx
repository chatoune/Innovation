/**
 * Dashboard page component (placeholder).
 */

import { useAuthStore } from '../stores/authStore';
import { logout } from '../services/auth';
import { useNavigate } from 'react-router-dom';
import Layout from '../components/layout/Layout';

export default function DashboardPage() {
  const navigate = useNavigate();
  const { user } = useAuthStore();

  async function handleLogout() {
    await logout();
    navigate('/login');
  }

  return (
    <Layout>
      <div className="space-y-6">
        {/* Welcome card */}
        <div className="bg-white shadow rounded-lg p-6">
          <h1 className="text-2xl font-bold text-gray-900">
            Welcome, {user?.full_name || user?.email || 'User'}!
          </h1>
          <p className="mt-2 text-gray-600">
            You are logged in to the Innovation Platform.
          </p>
        </div>

        {/* User info card */}
        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Account Information</h2>
          <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <dt className="text-sm font-medium text-gray-500">Email</dt>
              <dd className="mt-1 text-sm text-gray-900">{user?.email}</dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-gray-500">Full Name</dt>
              <dd className="mt-1 text-sm text-gray-900">{user?.full_name || 'Not set'}</dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-gray-500">Account Status</dt>
              <dd className="mt-1">
                <span
                  className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                    user?.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                  }`}
                >
                  {user?.is_active ? 'Active' : 'Inactive'}
                </span>
              </dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-gray-500">Role</dt>
              <dd className="mt-1">
                <span
                  className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                    user?.is_superuser ? 'bg-purple-100 text-purple-800' : 'bg-gray-100 text-gray-800'
                  }`}
                >
                  {user?.is_superuser ? 'Administrator' : 'User'}
                </span>
              </dd>
            </div>
            {user?.last_login && (
              <div className="sm:col-span-2">
                <dt className="text-sm font-medium text-gray-500">Last Login</dt>
                <dd className="mt-1 text-sm text-gray-900">
                  {new Date(user.last_login).toLocaleString()}
                </dd>
              </div>
            )}
          </dl>
        </div>

        {/* Logout button */}
        <div className="flex justify-end">
          <button
            onClick={handleLogout}
            className="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-md hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500"
          >
            Sign out
          </button>
        </div>
      </div>
    </Layout>
  );
}
