import apiClient from './client';
import { APIResponse, SystemHealthData } from '../types/api';

export const fetchSystemHealth = async (): Promise<APIResponse<SystemHealthData>> => {
  const response = await apiClient.get<APIResponse<SystemHealthData>>('/health/');
  return response.data;
};

export const fetchSystemInfo = async (): Promise<APIResponse<any>> => {
  const response = await apiClient.get<APIResponse<any>>('/info/');
  return response.data;
};
