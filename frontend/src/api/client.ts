import axios from 'axios';
import { APIResponse } from '../types/api';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true, // Enables HttpOnly cookies transmission
});

// Response interceptor for consistent error extraction
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      const customError: APIResponse = error.response.data;
      return Promise.reject(customError);
    }
    return Promise.reject({
      status: 'error',
      error: {
        code: 'NETWORK_ERROR',
        message: error.message || 'Network connection failed. Please verify server connectivity.',
      },
    });
  }
);

export default apiClient;
