/**
 * Main layout component with sidebar navigation.
 */

import { ReactNode, useState } from 'react';

interface LayoutProps {
  children: ReactNode;
}

interface NavItem {
  name: string;
  href: string;
  icon: string;
}

// Navigation items - will be dynamically populated based on user permissions
const navigation: NavItem[] = [
  { name: 'Dashboard', href: '/dashboard', icon: '📊' },
  { name: 'Users', href: '/users', icon: '👥' },
  { name: 'Roles', href: '/roles', icon: '🔐' },
  { name: 'Import', href: '/import', icon: '📤' },
];

export default function Layout({ children }: LayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Mobile sidebar backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-gray-600 bg-opacity-75 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 w-64 transform bg-white shadow-lg transition-transform duration-300 lg:translate-x-0 ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {/* Logo */}
        <div className="flex h-16 items-center justify-center border-b border-gray-200">
          <span className="text-xl font-bold text-gray-900">Innovation Platform</span>
        </div>

        {/* Navigation */}
        <nav className="mt-4 px-4">
          <ul className="space-y-1">
            {navigation.map((item) => (
              <li key={item.name}>
                <a
                  href={item.href}
                  className="flex items-center rounded-lg px-4 py-2 text-gray-700 hover:bg-gray-100"
                >
                  <span className="mr-3">{item.icon}</span>
                  <span>{item.name}</span>
                </a>
              </li>
            ))}
          </ul>
        </nav>

        {/* User section at bottom */}
        <div className="absolute bottom-0 w-full border-t border-gray-200 p-4">
          <div className="flex items-center">
            <div className="h-8 w-8 rounded-full bg-gray-300" />
            <div className="ml-3">
              <p className="text-sm font-medium text-gray-700">User Name</p>
              <button className="text-xs text-gray-500 hover:text-gray-700">Sign out</button>
            </div>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <div className="lg:pl-64">
        {/* Top bar */}
        <header className="sticky top-0 z-30 flex h-16 items-center border-b border-gray-200 bg-white px-4 shadow-sm">
          {/* Mobile menu button */}
          <button
            className="rounded-lg p-2 text-gray-600 hover:bg-gray-100 lg:hidden"
            onClick={() => setSidebarOpen(true)}
          >
            <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 6h16M4 12h16M4 18h16"
              />
            </svg>
          </button>

          {/* Page title placeholder */}
          <h1 className="ml-4 text-lg font-semibold text-gray-900 lg:ml-0">Page Title</h1>
        </header>

        {/* Page content */}
        <main className="p-6">{children}</main>
      </div>
    </div>
  );
}
