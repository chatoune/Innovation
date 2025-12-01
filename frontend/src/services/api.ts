/**
 * Base API client configuration with Axios.
 */

import axios, { AxiosError, AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios';

// API base URL from environment
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

/**
 * Standard API error response structure.
 */
export interface ApiError {
  error: string;
  message: string;
}

/**
 * Create configured Axios instance.
 */
function createApiClient(): AxiosInstance {
  const client = axios.create({
    baseURL: API_BASE_URL,
    timeout: 30000,
    headers: {
      'Content-Type': 'application/json',
    },
    withCredentials: true, // Include cookies for JWT
  });

  // Request interceptor for auth token
  client.interceptors.request.use(
    (config) => {
      // Token is handled via HTTPOnly cookie, no manual header needed
      return config;
    },
    (error) => Promise.reject(error)
  );

  // Response interceptor for error handling
  client.interceptors.response.use(
    (response: AxiosResponse) => response,
    async (error: AxiosError<ApiError>) => {
      const originalRequest = error.config as AxiosRequestConfig & { _retry?: boolean };

      // Handle 401 Unauthorized - attempt token refresh
      if (error.response?.status === 401 && !originalRequest._retry) {
        originalRequest._retry = true;

        try {
          // Attempt to refresh the token
          await client.post('/auth/refresh');
          // Retry the original request
          return client(originalRequest);
        } catch (refreshError) {
          // Refresh failed, redirect to login
          window.location.href = '/login';
          return Promise.reject(refreshError);
        }
      }

      // Extract error message from response
      const apiError: ApiError = error.response?.data || {
        error: 'NETWORK_ERROR',
        message: error.message || 'An unexpected error occurred',
      };

      return Promise.reject(apiError);
    }
  );

  return client;
}

// Export singleton API client instance
export const api = createApiClient();

/**
 * Type-safe GET request.
 */
export async function get<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
  const response = await api.get<T>(url, config);
  return response.data;
}

/**
 * Type-safe POST request.
 */
export async function post<T, D = unknown>(
  url: string,
  data?: D,
  config?: AxiosRequestConfig
): Promise<T> {
  const response = await api.post<T>(url, data, config);
  return response.data;
}

/**
 * Type-safe PUT request.
 */
export async function put<T, D = unknown>(
  url: string,
  data?: D,
  config?: AxiosRequestConfig
): Promise<T> {
  const response = await api.put<T>(url, data, config);
  return response.data;
}

/**
 * Type-safe PATCH request.
 */
export async function patch<T, D = unknown>(
  url: string,
  data?: D,
  config?: AxiosRequestConfig
): Promise<T> {
  const response = await api.patch<T>(url, data, config);
  return response.data;
}

/**
 * Type-safe DELETE request.
 */
export async function del<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
  const response = await api.delete<T>(url, config);
  return response.data;
}
