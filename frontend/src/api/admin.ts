import apiClient from './client';
import { Administrator, CreateAdminPayload, ResetPasswordPayload, AdminDashboardOverview, SecurityAuditLog, ResetPasswordResponse } from '../types/admin';

export const AdminAPI = {
  getOverview: async (): Promise<AdminDashboardOverview> => {
    const response = await apiClient.get('/admin/overview/');
    return response.data.data;
  },

  getAdministrators: async (): Promise<{ administrators: Administrator[]; count: number }> => {
    const response = await apiClient.get('/admin/administrators/');
    return response.data.data;
  },

  createAdministrator: async (payload: CreateAdminPayload): Promise<Administrator> => {
    const response = await apiClient.post('/admin/administrators/', payload);
    return response.data.data;
  },

  toggleAdministratorStatus: async (adminId: string, isActive?: boolean, reason?: string): Promise<Administrator> => {
    const response = await apiClient.post(`/admin/administrators/${adminId}/status/`, {
      is_active: isActive,
      reason,
    });
    return response.data.data;
  },

  resetAdminPassword: async (adminId: string, payload: ResetPasswordPayload): Promise<ResetPasswordResponse> => {
    const response = await apiClient.post(`/admin/administrators/${adminId}/reset-password/`, payload);
    return response.data.data;
  },

  deleteAdministrator: async (adminId: string): Promise<void> => {
    await apiClient.delete(`/admin/administrators/${adminId}/`);
  },

  getSecurityAuditLogs: async (params?: Record<string, any>): Promise<{ logs: SecurityAuditLog[]; total: number; limit: number; offset: number }> => {
    const response = await apiClient.get('/admin/audit-logs/', { params });
    return response.data.data;
  },
};

export default AdminAPI;

