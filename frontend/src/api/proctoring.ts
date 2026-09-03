import apiClient from './client';
import {
  StudentProctoringSession,
  AdminProctoringSessionSummary,
  AdminProctoringSessionDetail,
  ProctoringWarning,
  ProctoringReview,
} from '../types/proctoring';

export const startProctoringSession = async (attemptId: string): Promise<StudentProctoringSession> => {
  const response = await apiClient.post<StudentProctoringSession>(`/student/attempts/${attemptId}/proctoring/start/`);
  return response.data;
};

export const sendProctoringHeartbeat = async (attemptId: string): Promise<{ status: string; session_status: string; server_time: string }> => {
  const response = await apiClient.post(`/student/attempts/${attemptId}/proctoring/heartbeat/`);
  return response.data;
};

export const reportBrowserEvent = async (
  attemptId: string,
  eventType: string,
  metadata: Record<string, any> = {}
): Promise<{ event_id: string | null; status: string; warning_issued: boolean; warning: ProctoringWarning | null }> => {
  const response = await apiClient.post(`/student/attempts/${attemptId}/proctoring/events/`, {
    event_type: eventType,
    client_detected_at: new Date().toISOString(),
    metadata,
  });
  return response.data;
};

export const uploadProctoringFrame = async (
  attemptId: string,
  frameBlob: Blob,
  sequenceNumber: number = 0
): Promise<{ status: string; sequence_number: number }> => {
  const formData = new FormData();
  formData.append('frame', frameBlob, 'frame.jpg');
  formData.append('sequence_number', sequenceNumber.toString());

  const response = await apiClient.post(`/student/attempts/${attemptId}/proctoring/frames/`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
};

export const uploadProctoringAudio = async (
  attemptId: string,
  audioBlob: Blob,
  rmsDb: number = 0
): Promise<{ status: string }> => {
  const formData = new FormData();
  formData.append('audio', audioBlob, 'audio.webm');
  formData.append('rms_db', rmsDb.toString());

  const response = await apiClient.post(`/student/attempts/${attemptId}/proctoring/audio/`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
};

export const acknowledgeWarning = async (attemptId: string, warningId: string): Promise<{ status: string; acknowledged_at: string }> => {
  const response = await apiClient.post(`/student/attempts/${attemptId}/proctoring/warnings/${warningId}/ack/`);
  return response.data;
};

export const getAdminProctoringSessions = async (
  assessmentId: string,
  params?: { risk_band?: string; review_status?: string; search?: string }
): Promise<{ count: number; results: AdminProctoringSessionSummary[] }> => {
  const response = await apiClient.get<{ count: number; results: AdminProctoringSessionSummary[] }>(
    `/admin/assessments/${assessmentId}/proctoring/sessions/`,
    { params }
  );
  return response.data;
};

export const getAdminProctoringSessionDetail = async (sessionId: string): Promise<AdminProctoringSessionDetail> => {
  const response = await apiClient.get<AdminProctoringSessionDetail>(`/admin/proctoring/sessions/${sessionId}/`);
  return response.data;
};

export const updateAdminProctoringReview = async (
  sessionId: string,
  decision: string,
  notes: string = ''
): Promise<ProctoringReview> => {
  const response = await apiClient.patch<ProctoringReview>(`/admin/proctoring/sessions/${sessionId}/review/`, {
    decision,
    notes,
  });
  return response.data;
};

export const getEvidenceUrl = (evidenceId: string): string => {
  return `/api/v1/admin/proctoring/evidence/${evidenceId}/`;
};
