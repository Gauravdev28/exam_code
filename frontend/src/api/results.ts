import api from './client';
import {
  AssessmentResult,
  AssessmentAnalytics,
  QuestionAnalyticsItem,
  StudentTopicPerformance,
  ReportJob,
} from '../types/results';

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export const ResultsAPI = {
  // Student Endpoints
  getStudentAttemptResult: async (attemptId: string): Promise<AssessmentResult> => {
    const response = await api.get(`/student/attempts/${attemptId}/result/`);
    return response.data.data;
  },

  getStudentResults: async (page = 1): Promise<PaginatedResponse<AssessmentResult>> => {
    const response = await api.get(`/student/results/?page=${page}`);
    return response.data;
  },

  getStudentResultDetail: async (resultId: string): Promise<AssessmentResult> => {
    const response = await api.get(`/student/results/${resultId}/`);
    return response.data.data;
  },

  getStudentTopicAnalytics: async (): Promise<StudentTopicPerformance[]> => {
    const response = await api.get('/student/analytics/topics/');
    return response.data.data.topics;
  },

  createStudentReport: async (assessmentId: string, format: 'PDF' | 'XLSX' | 'CSV'): Promise<ReportJob> => {
    const response = await api.post('/student/reports/', {
      report_type: 'STUDENT_SCORECARD',
      format,
      assessment_id: assessmentId,
    });
    return response.data.data;
  },

  getStudentReportStatus: async (reportId: string): Promise<ReportJob> => {
    const response = await api.get(`/student/reports/${reportId}/`);
    return response.data.data;
  },

  // Admin Endpoints
  getAdminAssessmentResults: async (
    assessmentId: string,
    params: {
      page?: number;
      search?: string;
      is_passed?: boolean;
      score_min?: number;
      score_max?: number;
      ordering?: string;
    } = {}
  ): Promise<PaginatedResponse<AssessmentResult>> => {
    const response = await api.get(`/admin/assessments/${assessmentId}/results/`, { params });
    return response.data;
  },

  getAdminResultDetail: async (resultId: string): Promise<AssessmentResult> => {
    const response = await api.get(`/admin/results/${resultId}/`);
    return response.data.data;
  },

  getAdminAssessmentAnalytics: async (assessmentId: string): Promise<AssessmentAnalytics> => {
    const response = await api.get(`/admin/assessments/${assessmentId}/analytics/`);
    return response.data.data;
  },

  getAdminQuestionAnalytics: async (assessmentId: string): Promise<QuestionAnalyticsItem[]> => {
    const response = await api.get(`/admin/assessments/${assessmentId}/analytics/questions/`);
    return response.data.data.questions;
  },

  releaseAdminAssessmentResults: async (assessmentId: string): Promise<{ released_count: number }> => {
    const response = await api.post(`/admin/assessments/${assessmentId}/release-results/`);
    return response.data.data;
  },

  createAdminReport: async (
    assessmentId: string,
    reportType: 'ASSESSMENT_SUMMARY' | 'ASSESSMENT_ROSTER',
    format: 'PDF' | 'XLSX' | 'CSV'
  ): Promise<ReportJob> => {
    const response = await api.post('/admin/reports/', {
      assessment_id: assessmentId,
      report_type: reportType,
      format,
    });
    return response.data.data;
  },

  getAdminReportStatus: async (reportId: string): Promise<ReportJob> => {
    const response = await api.get(`/admin/reports/${reportId}/`);
    return response.data.data;
  },
};
