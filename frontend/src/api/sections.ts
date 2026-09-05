import apiClient from './client';
import { APIResponse } from '../types/api';
import { Section, CreateSectionPayload, UpdateSectionPayload } from '../types/section';

export interface SectionFilterParams {
  search?: string;
  active_only?: boolean;
}

export const fetchSections = async (
  params?: SectionFilterParams
): Promise<APIResponse<Section[]>> => {
  const response = await apiClient.get<APIResponse<Section[]>>('/admin/sections/', {
    params,
  });
  return response.data;
};

export const createSection = async (
  payload: CreateSectionPayload
): Promise<APIResponse<Section>> => {
  const response = await apiClient.post<APIResponse<Section>>('/admin/sections/', payload);
  return response.data;
};

export const fetchSectionDetail = async (
  id: string
): Promise<APIResponse<Section>> => {
  const response = await apiClient.get<APIResponse<Section>>(`/admin/sections/${id}/`);
  return response.data;
};

export const updateSection = async (
  id: string,
  payload: UpdateSectionPayload
): Promise<APIResponse<Section>> => {
  const response = await apiClient.patch<APIResponse<Section>>(`/admin/sections/${id}/`, payload);
  return response.data;
};

export const deleteSection = async (
  id: string
): Promise<APIResponse<{ message: string }>> => {
  const response = await apiClient.delete<APIResponse<{ message: string }>>(`/admin/sections/${id}/`);
  return response.data;
};
