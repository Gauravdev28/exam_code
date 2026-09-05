import apiClient from './client';
import { APIResponse } from '../types/api';
import { User, LoginCredentials, AuthResponseData } from '../types/auth';

export const initCsrfToken = async (): Promise<string> => {
  try {
    const response = await apiClient.get<APIResponse<{ csrf_token: string }>>('/auth/csrf/');
    return response.data?.data?.csrf_token || '';
  } catch {
    return '';
  }
};

export const loginUser = async (credentials: LoginCredentials): Promise<APIResponse<AuthResponseData>> => {
  const response = await apiClient.post<APIResponse<AuthResponseData>>('/auth/login/', credentials);
  return response.data;
};

export const logoutUser = async (): Promise<APIResponse<null>> => {
  const response = await apiClient.post<APIResponse<null>>('/auth/logout/');
  return response.data;
};

export const fetchCurrentUser = async (): Promise<APIResponse<User>> => {
  const response = await apiClient.get<APIResponse<User>>('/auth/me/');
  return response.data;
};

export const testAdminAccess = async (): Promise<APIResponse<any>> => {
  const response = await apiClient.get<APIResponse<any>>('/auth/admin-only/');
  return response.data;
};

export const testStudentAccess = async (): Promise<APIResponse<any>> => {
  const response = await apiClient.get<APIResponse<any>>('/auth/student-only/');
  return response.data;
};

export interface SessionStatusData {
  is_authenticated: boolean;
  idle_seconds: number;
  time_remaining_seconds: number;
  is_idle_expired: boolean;
  is_in_active_assessment: boolean;
  warning_threshold_seconds: number;
}

export const getSessionStatus = async (): Promise<APIResponse<SessionStatusData>> => {
  const response = await apiClient.get<APIResponse<SessionStatusData>>('/auth/session/status/');
  return response.data;
};

export const refreshSession = async (): Promise<APIResponse<{ message: string; last_activity: number }>> => {
  const response = await apiClient.post<APIResponse<{ message: string; last_activity: number }>>('/auth/session/refresh/');
  return response.data;
};

