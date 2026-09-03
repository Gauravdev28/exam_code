import apiClient from './client';
import { APIResponse, PaginatedResponse } from '../types/api';
import {
  StudentProfile,
  CreateStudentPayload,
  UpdateStudentPayload,
  ImportPreviewReport,
  ImportConfirmPayload,
  ImportConfirmResult,
  ChangePasswordPayload,
} from '../types/student';
import { User } from '../types/auth';

export interface StudentFilterParams {
  search?: string;
  is_active?: boolean;
  first_login_required?: boolean;
  ordering?: string;
  page?: number;
  page_size?: number;
}

export const fetchStudents = async (
  params?: StudentFilterParams
): Promise<PaginatedResponse<StudentProfile>> => {
  const response = await apiClient.get<PaginatedResponse<StudentProfile>>('/admin/students/', {
    params,
  });
  return response.data;
};

export const createStudent = async (
  payload: CreateStudentPayload
): Promise<APIResponse<StudentProfile>> => {
  const response = await apiClient.post<APIResponse<StudentProfile>>('/admin/students/', payload);
  return response.data;
};

export const fetchStudentDetail = async (
  id: string
): Promise<APIResponse<StudentProfile>> => {
  const response = await apiClient.get<APIResponse<StudentProfile>>(`/admin/students/${id}/`);
  return response.data;
};

export const updateStudent = async (
  id: string,
  payload: UpdateStudentPayload
): Promise<APIResponse<StudentProfile>> => {
  const response = await apiClient.patch<APIResponse<StudentProfile>>(`/admin/students/${id}/`, payload);
  return response.data;
};

export const disableStudent = async (
  id: string
): Promise<APIResponse<StudentProfile>> => {
  const response = await apiClient.post<APIResponse<StudentProfile>>(`/admin/students/${id}/disable/`);
  return response.data;
};

export const enableStudent = async (
  id: string
): Promise<APIResponse<StudentProfile>> => {
  const response = await apiClient.post<APIResponse<StudentProfile>>(`/admin/students/${id}/enable/`);
  return response.data;
};

export const previewStudentImport = async (
  file: File
): Promise<APIResponse<ImportPreviewReport>> => {
  const formData = new FormData();
  formData.append('file', file);
  const response = await apiClient.post<APIResponse<ImportPreviewReport>>(
    '/admin/students/import/preview/',
    formData,
    {
      headers: { 'Content-Type': 'multipart/form-data' },
    }
  );
  return response.data;
};

export const confirmStudentImport = async (
  payload: ImportConfirmPayload
): Promise<APIResponse<ImportConfirmResult>> => {
  const response = await apiClient.post<APIResponse<ImportConfirmResult>>(
    '/admin/students/import/confirm/',
    payload
  );
  return response.data;
};

export const fetchStudentSelfProfile = async (): Promise<APIResponse<StudentProfile>> => {
  const response = await apiClient.get<APIResponse<StudentProfile>>('/student/profile/');
  return response.data;
};

export const changeUserPassword = async (
  payload: ChangePasswordPayload
): Promise<APIResponse<User>> => {
  const response = await apiClient.post<APIResponse<User>>('/auth/change-password/', payload);
  return response.data;
};
