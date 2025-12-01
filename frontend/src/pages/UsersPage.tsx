/**
 * User management page.
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { get, ApiError } from '../services/api';
import Layout from '../components/layout/Layout';
import PermissionGate from '../components/common/PermissionGate';
import { Permissions } from '../hooks/usePermissions';
import UserTable from '../components/users/UserTable';
import UserForm from '../components/users/UserForm';

interface UserListItem {
  id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  is_superuser: boolean;
  role_count: number;
  last_login: string | null;
}

interface UserListResponse {
  items: UserListItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export default function UsersPage() {
  const navigate = useNavigate();
  const [users, setUsers] = useState<UserListItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);

  // Pagination
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const pageSize = 20;

  // Filters
  const [search, setSearch] = useState('');
  const [activeFilter, setActiveFilter] = useState<string>('all');

  async function loadUsers() {
    setIsLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams({
        page: String(page),
        page_size: String(pageSize),
      });

      if (search) {
        params.append('search', search);
      }

      if (activeFilter !== 'all') {
        params.append('is_active', activeFilter === 'active' ? 'true' : 'false');
      }

      const data = await get<UserListResponse>(`/users?${params.toString()}`);
      setUsers(data.items);
      setTotalPages(data.total_pages);
      setTotal(data.total);
    } catch (err) {
      const apiError = err as ApiError;
      setError(apiError.message || 'Failed to load users');
    } finally {
      setIsLoading(false);
    }
  }

  function handleViewUser(userId: string) {
    navigate(`/users/${userId}`);
  }

  function handleFormClose() {
    setShowCreateForm(false);
    loadUsers();
  }

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    setPage(1);
    loadUsers();
  }

  useEffect(() => {
    loadUsers();
  }, [page, activeFilter]);

  return (
    <Layout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex justify-between items-center">
          <h1 className="text-2xl font-bold text-gray-900">User Management</h1>
          <PermissionGate permission={Permissions.USERS_CREATE}>
            <button
              onClick={() => setShowCreateForm(true)}
              className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
            >
              Create User
            </button>
          </PermissionGate>
        </div>

        {/* Filters */}
        <div className="bg-white shadow rounded-lg p-4">
          <form onSubmit={handleSearch} className="flex gap-4 items-end">
            <div className="flex-1">
              <label htmlFor="search" className="block text-sm font-medium text-gray-700">
                Search
              </label>
              <input
                type="text"
                id="search"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search by email or name..."
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
              />
            </div>
            <div>
              <label htmlFor="status" className="block text-sm font-medium text-gray-700">
                Status
              </label>
              <select
                id="status"
                value={activeFilter}
                onChange={(e) => {
                  setActiveFilter(e.target.value);
                  setPage(1);
                }}
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
              >
                <option value="all">All</option>
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
              </select>
            </div>
            <button
              type="submit"
              className="px-4 py-2 bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200"
            >
              Search
            </button>
          </form>
        </div>

        {/* Error message */}
        {error && (
          <div className="rounded-md bg-red-50 p-4">
            <p className="text-sm text-red-800">{error}</p>
          </div>
        )}

        {/* User table */}
        <UserTable
          users={users}
          isLoading={isLoading}
          onViewUser={handleViewUser}
          onRefresh={loadUsers}
        />

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between bg-white px-4 py-3 rounded-lg shadow">
            <div className="text-sm text-gray-700">
              Showing {(page - 1) * pageSize + 1} to {Math.min(page * pageSize, total)} of{' '}
              {total} results
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setPage(page - 1)}
                disabled={page === 1}
                className="px-3 py-1 rounded border disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
              >
                Previous
              </button>
              <span className="px-3 py-1">
                Page {page} of {totalPages}
              </span>
              <button
                onClick={() => setPage(page + 1)}
                disabled={page === totalPages}
                className="px-3 py-1 rounded border disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
              >
                Next
              </button>
            </div>
          </div>
        )}

        {/* Create form modal */}
        {showCreateForm && <UserForm onClose={handleFormClose} />}
      </div>
    </Layout>
  );
}
