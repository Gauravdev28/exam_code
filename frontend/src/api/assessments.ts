import { apiClient } from './client';
import { APIResponse, PaginatedResponse } from '../types/api';
import {
  AssessmentAdminItem,
  AssessmentAdminDetail,
  CreateAssessmentPayload,
  UpdateAssessmentPayload,
  AddAssessmentQuestionPayload,
  AssessmentAssignmentItem,
  AudienceResolution,
  ConfigureAudiencePayload,
  StudentAssessmentItem,
  StudentAttemptDetail,
  SaveAnswerPayload,
} from '../types/assessment';

export interface AssessmentFilters {
  page?: number;
  page_size?: number;
  search?: string;
  status?: string;
  ordering?: string;
}

// ==============================================================================
// Admin API
// ==============================================================================

export const getAdminAssessments = async (
  filters: AssessmentFilters = {}
): Promise<PaginatedResponse<AssessmentAdminItem>> => {
  const params: Record<string, any> = {};
  if (filters.page) params.page = filters.page;
  if (filters.page_size) params.page_size = filters.page_size;
  if (filters.search) params.search = filters.search;
  if (filters.status) params.status = filters.status;
  if (filters.ordering) params.ordering = filters.ordering;

  const res = await apiClient.get<PaginatedResponse<AssessmentAdminItem>>('/admin/assessments/', { params });
  return res.data;
};

export const createAssessment = async (
  payload: CreateAssessmentPayload
): Promise<APIResponse<AssessmentAdminDetail>> => {
  const res = await apiClient.post<APIResponse<AssessmentAdminDetail>>('/admin/assessments/', payload);
  return res.data;
};

export const getAssessmentDetail = async (
  id: string
): Promise<APIResponse<AssessmentAdminDetail>> => {
  const res = await apiClient.get<APIResponse<AssessmentAdminDetail>>(`/admin/assessments/${id}/`);
  return res.data;
};

export const updateAssessment = async (
  id: string,
  payload: UpdateAssessmentPayload
): Promise<APIResponse<AssessmentAdminDetail>> => {
  const res = await apiClient.patch<APIResponse<AssessmentAdminDetail>>(`/admin/assessments/${id}/`, payload);
  return res.data;
};

export const deleteAssessment = async (
  id: string
): Promise<APIResponse<null>> => {
  const res = await apiClient.delete<APIResponse<null>>(`/admin/assessments/${id}/`);
  return res.data;
};

export const publishAssessment = async (
  id: string
): Promise<APIResponse<AssessmentAdminDetail>> => {
  const res = await apiClient.post<APIResponse<AssessmentAdminDetail>>(`/admin/assessments/${id}/publish/`);
  return res.data;
};

export const archiveAssessment = async (
  id: string
): Promise<APIResponse<AssessmentAdminDetail>> => {
  const res = await apiClient.post<APIResponse<AssessmentAdminDetail>>(`/admin/assessments/${id}/archive/`);
  return res.data;
};

export const fetchAssessmentAudience = async (
  assessmentId: string
): Promise<APIResponse<AudienceResolution>> => {
  const res = await apiClient.get<APIResponse<AudienceResolution>>(
    `/admin/assessments/${assessmentId}/audience/`
  );
  return res.data;
};

export const configureAssessmentAudience = async (
  assessmentId: string,
  payload: ConfigureAudiencePayload
): Promise<APIResponse<AudienceResolution>> => {
  const res = await apiClient.post<APIResponse<AudienceResolution>>(
    `/admin/assessments/${assessmentId}/audience/`,
    payload
  );
  return res.data;
};

export const previewAssessmentAudience = async (
  assessmentId: string,
  payload: ConfigureAudiencePayload
): Promise<APIResponse<AudienceResolution>> => {
  const res = await apiClient.post<APIResponse<AudienceResolution>>(
    `/admin/assessments/${assessmentId}/audience/preview/`,
    payload
  );
  return res.data;
};

export const addQuestionToAssessment = async (
  assessmentId: string,
  payload: AddAssessmentQuestionPayload
): Promise<APIResponse<AssessmentAdminDetail>> => {
  const res = await apiClient.post<APIResponse<AssessmentAdminDetail>>(
    `/admin/assessments/${assessmentId}/questions/`,
    payload
  );
  return res.data;
};

export const removeQuestionFromAssessment = async (
  assessmentId: string,
  questionVersionId: string
): Promise<APIResponse<AssessmentAdminDetail>> => {
  const res = await apiClient.delete<APIResponse<AssessmentAdminDetail>>(
    `/admin/assessments/${assessmentId}/questions/${questionVersionId}/`
  );
  return res.data;
};

export const getAssessmentAssignments = async (
  assessmentId: string
): Promise<APIResponse<AssessmentAssignmentItem[]>> => {
  const res = await apiClient.get<APIResponse<AssessmentAssignmentItem[]>>(
    `/admin/assessments/${assessmentId}/assignments/`
  );
  return res.data;
};

export const assignStudentsToAssessment = async (
  assessmentId: string,
  studentIds: string[]
): Promise<APIResponse<AssessmentAssignmentItem[]>> => {
  const res = await apiClient.post<APIResponse<AssessmentAssignmentItem[]>>(
    `/admin/assessments/${assessmentId}/assignments/`,
    { student_ids: studentIds }
  );
  return res.data;
};

export const revokeStudentAssignment = async (
  assessmentId: string,
  studentId: string
): Promise<APIResponse<AssessmentAssignmentItem>> => {
  const res = await apiClient.delete<APIResponse<AssessmentAssignmentItem>>(
    `/admin/assessments/${assessmentId}/assignments/${studentId}/`
  );
  return res.data;
};

// ==============================================================================
// Student API
// ==============================================================================

export const getStudentAssessments = async (): Promise<APIResponse<StudentAssessmentItem[]>> => {
  const res = await apiClient.get<APIResponse<StudentAssessmentItem[]>>('/student/assessments/');
  return res.data;
};

export const getStudentAssessmentDetail = async (
  id: string
): Promise<APIResponse<StudentAssessmentItem>> => {
  const res = await apiClient.get<APIResponse<StudentAssessmentItem>>(`/student/assessments/${id}/`);
  return res.data;
};

export const startAssessmentAttempt = async (
  assessmentId: string
): Promise<APIResponse<{ attempt_id: string; status: string; is_new: boolean }>> => {
  const res = await apiClient.post<APIResponse<{ attempt_id: string; status: string; is_new: boolean }>>(
    `/student/assessments/${assessmentId}/start/`
  );
  return res.data;
};

export const getStudentAttemptDetail = async (
  attemptId: string
): Promise<APIResponse<StudentAttemptDetail>> => {
  const res = await apiClient.get<APIResponse<StudentAttemptDetail>>(`/student/attempts/${attemptId}/`);
  return res.data;
};

export const saveAttemptAnswer = async (
  attemptId: string,
  questionId: string,
  payload: SaveAnswerPayload
): Promise<APIResponse<{ status: string; server_revision: number; is_answered: boolean; last_saved_at: string }>> => {
  const res = await apiClient.post<APIResponse<any>>(
    `/student/attempts/${attemptId}/answers/${questionId}/`,
    payload
  );
  return res.data;
};

export const submitAttempt = async (
  attemptId: string
): Promise<APIResponse<{ attempt_id: string; status: string; submitted_at: string }>> => {
  const res = await apiClient.post<APIResponse<any>>(`/student/attempts/${attemptId}/submit/`);
  return res.data;
};

// ==============================================================================
// Assessment Attendance & Reporting API
// ==============================================================================

export interface AttendanceFilterParams {
  section_id?: string;
  attendance_status?: string;
  attempt_status?: string;
  search?: string;
  page?: number;
  page_size?: number;
}

export interface AttendanceStudentRow {
  student_id: string;
  student_name: string;
  email: string;
  roll_number: string;
  euid: string;
  section: string;
  section_id: string | null;
  assignment_status: string;
  attendance_status: 'ATTENDED' | 'NOT_ATTENDED';
  attempt_status: string;
  started_at: string | null;
  submitted_at: string | null;
  duration_seconds: number | null;
  attempts_count: number;
}

export interface AttendanceSectionSummary {
  section_id: string | null;
  section_name: string;
  assigned: number;
  attended: number;
  not_attended: number;
  in_progress: number;
  submitted: number;
  attendance_percentage: number;
}

export interface AttendanceSummary {
  total_assigned: number;
  total_attended: number;
  total_not_attended: number;
  total_in_progress: number;
  total_submitted: number;
  attendance_percentage: number;
  is_pre_exam: boolean;
}

export interface AssessmentAttendanceData {
  assessment: {
    id: string;
    title: string;
    status: string;
    start_datetime: string;
    end_datetime: string;
    duration_minutes: number;
    is_pre_exam: boolean;
  };
  summary: AttendanceSummary;
  sections: AttendanceSectionSummary[];
  results: AttendanceStudentRow[];
  total_count: number;
  page: number;
  page_size: number;
}

export const getAssessmentAttendance = async (
  assessmentId: string,
  params?: AttendanceFilterParams
): Promise<APIResponse<AssessmentAttendanceData>> => {
  const res = await apiClient.get<APIResponse<AssessmentAttendanceData>>(
    `/admin/assessments/${assessmentId}/attendance/`,
    { params }
  );
  return res.data;
};

export const exportAssessmentAttendance = async (
  assessmentId: string,
  format: 'xlsx' | 'pdf',
  params?: AttendanceFilterParams
): Promise<Blob> => {
  const res = await apiClient.get(`/admin/assessments/${assessmentId}/attendance/export/`, {
    params: { ...params, format },
    responseType: 'blob',
  });
  return res.data;
};

