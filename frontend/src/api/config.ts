/**
 * API Configuration
 *
 * Provides centralized API base URL configuration.
 * Honors VITE_API_URL environment variable for deployment flexibility.
 *
 * Security Configuration:
 * - Set VITE_ADMIN_API_KEY to enable secured mode (when backend has DEV_MODE=false)
 * - The key is sent via X-ADMIN-KEY header for POST/PUT/DELETE/PATCH requests
 */

// API base URL - use environment variable if set, otherwise default to localhost
export const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

// Full backend URL (for endpoints outside /api/v1)
export const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';

// Admin API key for secured mode (optional - only needed when DEV_MODE=false on backend)
export const ADMIN_API_KEY = import.meta.env.VITE_ADMIN_API_KEY || '';

/**
 * Get headers for API requests
 * Includes X-ADMIN-KEY header when configured (for secured mode)
 * @param includeAuth - Whether to include auth header (default: true for write operations)
 */
export function getApiHeaders(includeAuth: boolean = true): Record<string, string> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };

  if (includeAuth && ADMIN_API_KEY) {
    headers['X-ADMIN-KEY'] = ADMIN_API_KEY;
  }

  return headers;
}

/**
 * Build full API URL from a path
 * @param path - API path (e.g., '/inventory/devices')
 * @returns Full URL (e.g., 'http://localhost:8000/api/v1/inventory/devices')
 */
export function buildApiUrl(path: string): string {
  // Remove leading slash if present to avoid double slashes
  const cleanPath = path.startsWith('/') ? path.slice(1) : path;
  return `${API_BASE_URL}/${cleanPath}`;
}

/**
 * Build inventory API URL
 * @param path - Inventory endpoint path (e.g., 'devices', 'stats')
 * @returns Full URL for inventory endpoint
 */
export function buildInventoryUrl(path: string): string {
  const cleanPath = path.startsWith('/') ? path.slice(1) : path;
  return `${API_BASE_URL}/inventory/${cleanPath}`;
}
