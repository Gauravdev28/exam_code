import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true, // Enables Session & CSRF cookies transmission
  xsrfCookieName: 'csrftoken',
  xsrfHeaderName: 'X-CSRFToken',
});

// Helper to extract cookie by name
function getCookie(name: string): string | null {
  if (typeof document === 'undefined') return null;
  const match = document.cookie.match(new RegExp('(^|;\\s*)(' + name + ')=([^;]*)'));
  return match ? decodeURIComponent(match[3]) : null;
}

// Request interceptor ensuring X-CSRFToken is attached to mutating requests
apiClient.interceptors.request.use((config) => {
  const token = getCookie('csrftoken');
  if (token && config.headers) {
    config.headers['X-CSRFToken'] = token;
  }
  return config;
});

// Response interceptor for consistent error extraction and session expiration handling
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      // If 401 on an authenticated endpoint, notify session expiration
      if (
        error.response.status === 401 &&
        typeof window !== 'undefined' &&
        !error.config?.url?.includes('/auth/login/') &&
        !error.config?.url?.includes('/auth/csrf/')
      ) {
        window.dispatchEvent(new CustomEvent('auth:session-expired'));
      }

      const data = error.response.data;
      const customError: any = (typeof data === 'object' && data !== null) ? { ...data } : {};
      customError.status_code = error.response.status;
      customError.response = error.response;

      if (!customError.error) {
        const fallbackMsg =
          customError.detail ||
          customError.message ||
          (error.response.status === 401
            ? 'Your session has expired. Please sign in again.'
            : error.response.status === 403
            ? 'You do not have permission to perform this action.'
            : 'An unexpected error occurred.');
        customError.error = {
          code:
            error.response.status === 401
              ? 'AUTHENTICATION_REQUIRED'
              : error.response.status === 403
              ? 'PERMISSION_DENIED'
              : 'API_ERROR',
          message: fallbackMsg,
        };
      }

      return Promise.reject(customError);
    }
    return Promise.reject({
      status: 'error',
      status_code: 0,
      error: {
        code: 'NETWORK_ERROR',
        message: error.message || 'Network connection failed. Please verify server connectivity.',
      },
    });
  }
);

export default apiClient;
