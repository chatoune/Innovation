/**
 * Authentication service for login, logout, and user management.
 */

import { api, post, get } from './api';
import { useAuthStore, User } from '../stores/authStore';

interface LoginRequest {
  email: string;
  password: string;
}

interface AuthResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

/**
 * Login with email and password.
 */
export async function login(credentials: LoginRequest): Promise<User> {
  const { setLoading, login: setAuth, logout } = useAuthStore.getState();

  setLoading(true);

  try {
    // Authenticate and get token
    const authResponse = await post<AuthResponse, LoginRequest>('/auth/login', credentials);

    // Store token in memory (not persisted)
    const token = authResponse.access_token;

    // Set auth header for subsequent requests
    api.defaults.headers.common['Authorization'] = `Bearer ${token}`;

    // Get current user info
    const user = await get<User>('/auth/me');

    // Update store with user and token
    setAuth(user, token);

    return user;
  } catch (error) {
    logout();
    throw error;
  } finally {
    setLoading(false);
  }
}

/**
 * Logout the current user.
 */
export async function logout(): Promise<void> {
  const { logout: clearAuth } = useAuthStore.getState();

  try {
    await post('/auth/logout');
  } finally {
    // Always clear local state, even if API call fails
    delete api.defaults.headers.common['Authorization'];
    clearAuth();
  }
}

/**
 * Get the current authenticated user.
 */
export async function getCurrentUser(): Promise<User | null> {
  const { setUser, setLoading, accessToken } = useAuthStore.getState();

  if (!accessToken) {
    return null;
  }

  setLoading(true);

  try {
    // Ensure auth header is set
    api.defaults.headers.common['Authorization'] = `Bearer ${accessToken}`;

    const user = await get<User>('/auth/me');
    setUser(user);
    return user;
  } catch {
    // Token might be expired, try to refresh
    try {
      await refreshToken();
      const user = await get<User>('/auth/me');
      setUser(user);
      return user;
    } catch {
      // Refresh failed, clear auth state
      const { logout: clearAuth } = useAuthStore.getState();
      clearAuth();
      return null;
    }
  } finally {
    setLoading(false);
  }
}

/**
 * Refresh the access token using the refresh token cookie.
 */
export async function refreshToken(): Promise<string> {
  const { setAccessToken } = useAuthStore.getState();

  const response = await post<AuthResponse>('/auth/refresh');
  const token = response.access_token;

  // Update token in memory and request headers
  api.defaults.headers.common['Authorization'] = `Bearer ${token}`;
  setAccessToken(token);

  return token;
}

/**
 * Check if the user is authenticated (has a valid token).
 */
export function isAuthenticated(): boolean {
  const { isAuthenticated } = useAuthStore.getState();
  return isAuthenticated;
}

/**
 * Initialize auth state on app load.
 * Attempts to restore session from refresh token.
 */
export async function initializeAuth(): Promise<void> {
  const { accessToken, isAuthenticated, setLoading } = useAuthStore.getState();

  if (!isAuthenticated) {
    return;
  }

  setLoading(true);

  try {
    if (accessToken) {
      // Try to get current user with existing token
      api.defaults.headers.common['Authorization'] = `Bearer ${accessToken}`;
      await getCurrentUser();
    } else {
      // Try to refresh token from cookie
      await refreshToken();
      await getCurrentUser();
    }
  } catch {
    // Session is invalid, clear auth state
    const { logout: clearAuth } = useAuthStore.getState();
    clearAuth();
  } finally {
    setLoading(false);
  }
}
