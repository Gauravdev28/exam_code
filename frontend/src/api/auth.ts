import apiClient from './client';
import { APIResponse } from '../types/api';
import { User, LoginCredentials, AuthResponseData } from '../types/auth';

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
