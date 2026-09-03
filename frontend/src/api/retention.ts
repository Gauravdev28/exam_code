import api from './client';
import {
  RetentionMetrics,
  RetentionPolicy,
  LegalHold,
  RetentionTombstone,
  ExportJob,
  StudentRetentionStatus,
  PurgePreviewResponse,
  PurgeExecutionSummary,
} from '../types/retention';
import { PaginatedResponse } from './results';

export const RetentionAPI = {
  // Admin Retention & Policies
  getMetrics: async (): Promise<RetentionMetrics> => {
    const res = await api.get('/admin/retention/metrics/');
    return res.data.data;
  },

  getPolicies: async (): Promise<RetentionPolicy[]> => {
    const res = await api.get('/admin/retention/policies/');
    return res.data.data;
  },

  createPolicy: async (data: Partial<RetentionPolicy>): Promise<RetentionPolicy> => {
    const res = await api.post('/admin/retention/policies/', data);
    return res.data.data;
  },

  updatePolicy: async (id: string, data: Partial<RetentionPolicy>): Promise<RetentionPolicy> => {
    const res = await api.patch(`/admin/retention/policies/${id}/`, data);
    return res.data.data;
  },

  getCandidates: async (params?: { assessment_id?: string; page?: number }) => {
    const res = await api.get('/admin/retention/candidates/', { params });
    return res.data;
  },

  previewPurge: async (assessmentId?: string): Promise<PurgePreviewResponse> => {
    const res = await api.post('/admin/retention/preview-purge/', { assessment_id: assessmentId });
    return res.data.data;
  },

  executePurge: async (previewToken: string): Promise<PurgeExecutionSummary> => {
    const res = await api.post('/admin/retention/execute-purge/', { preview_token: previewToken });
    return res.data.data;
  },

  getTombstones: async (params?: { student_euid?: string; assessment_id?: string; page?: number }): Promise<PaginatedResponse<RetentionTombstone>> => {
    const res = await api.get('/admin/retention/tombstones/', { params });
    return res.data;
  },

  // Admin Legal Holds
  getLegalHolds: async (params?: { status?: string; scope?: string; page?: number }): Promise<PaginatedResponse<LegalHold>> => {
    const res = await api.get('/admin/legal-holds/', { params });
    return res.data;
  },

  createLegalHold: async (data: {
    title: string;
    case_reference: string;
    reason: string;
    scope: 'ATTEMPT' | 'STUDENT' | 'ASSESSMENT';
    attempt?: string;
    student?: string;
    assessment?: string;
  }): Promise<LegalHold> => {
    const res = await api.post('/admin/legal-holds/', data);
    return res.data.data;
  },

  releaseLegalHold: async (id: string, releaseReason: string): Promise<LegalHold> => {
    const res = await api.post(`/admin/legal-holds/${id}/release/`, { release_reason: releaseReason });
    return res.data.data;
  },

  // Student Privacy
  getStudentRetentionStatus: async (): Promise<StudentRetentionStatus> => {
    const res = await api.get('/student/privacy/retention-status/');
    return res.data.data;
  },

  getStudentExportJobs: async (): Promise<ExportJob[]> => {
    const res = await api.get('/student/privacy/export-requests/');
    return res.data.data;
  },

  createStudentExportJob: async (attemptId?: string): Promise<ExportJob> => {
    const res = await api.post('/student/privacy/export-requests/', { attempt_id: attemptId });
    return res.data.data;
  },

  downloadExportArchive: async (jobId: string): Promise<Blob> => {
    const res = await api.get(`/student/privacy/export-requests/${jobId}/download/`, {
      responseType: 'blob',
    });
    return res.data;
  },
};
