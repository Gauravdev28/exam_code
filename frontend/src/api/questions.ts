import { apiClient } from './client';
import { APIResponse, PaginatedResponse } from '../types/api';
import {
  QuestionItem,
  QuestionVersionDetail,
  QuestionVersionSummary,
  CreateQuestionPayload,
  UpdateQuestionVersionPayload,
  Tag,
} from '../types/question';

export interface QuestionFilters {
  page?: number;
  page_size?: number;
  search?: string;
  type?: string;
  difficulty?: string;
  status?: string;
  version_status?: string;
  tag?: string;
  ordering?: string;
}

export const getQuestions = async (
  filters: QuestionFilters = {}
): Promise<PaginatedResponse<QuestionItem>> => {
  const params: Record<string, any> = {};
  if (filters.page) params.page = filters.page;
  if (filters.page_size) params.page_size = filters.page_size;
  if (filters.search) params.search = filters.search;
  if (filters.type) params.type = filters.type;
  if (filters.difficulty) params.difficulty = filters.difficulty;
  if (filters.status) params.status = filters.status;
  if (filters.version_status) params.version_status = filters.version_status;
  if (filters.tag) params.tag = filters.tag;
  if (filters.ordering) params.ordering = filters.ordering;

  const res = await apiClient.get<PaginatedResponse<QuestionItem>>('/admin/questions/', { params });
  return res.data;
};

export const createQuestion = async (
  payload: CreateQuestionPayload
): Promise<APIResponse<QuestionVersionDetail>> => {
  const res = await apiClient.post<APIResponse<QuestionVersionDetail>>('/admin/questions/', payload);
  return res.data;
};

export const getQuestionDetail = async (
  questionId: string
): Promise<APIResponse<{ id: string; question_type: string; status: string; versions: QuestionVersionSummary[] }>> => {
  const res = await apiClient.get<APIResponse<any>>(`/admin/questions/${questionId}/`);
  return res.data;
};

export const archiveQuestion = async (
  questionId: string
): Promise<APIResponse<any>> => {
  const res = await apiClient.post<APIResponse<any>>(`/admin/questions/${questionId}/archive/`);
  return res.data;
};

export const deleteDraftQuestion = async (
  questionId: string
): Promise<APIResponse<null>> => {
  const res = await apiClient.delete<APIResponse<null>>(`/admin/questions/${questionId}/`);
  return res.data;
};

export const getQuestionVersions = async (
  questionId: string
): Promise<APIResponse<QuestionVersionSummary[]>> => {
  const res = await apiClient.get<APIResponse<QuestionVersionSummary[]>>(`/admin/questions/${questionId}/versions/`);
  return res.data;
};

export const createNewVersion = async (
  questionId: string
): Promise<APIResponse<QuestionVersionDetail>> => {
  const res = await apiClient.post<APIResponse<QuestionVersionDetail>>(`/admin/questions/${questionId}/versions/`);
  return res.data;
};

export const getQuestionVersionDetail = async (
  questionId: string,
  versionNumber: number
): Promise<APIResponse<QuestionVersionDetail>> => {
  const res = await apiClient.get<APIResponse<QuestionVersionDetail>>(
    `/admin/questions/${questionId}/versions/${versionNumber}/`
  );
  return res.data;
};

export const updateDraftVersion = async (
  questionId: string,
  versionNumber: number,
  payload: UpdateQuestionVersionPayload
): Promise<APIResponse<QuestionVersionDetail>> => {
  const res = await apiClient.patch<APIResponse<QuestionVersionDetail>>(
    `/admin/questions/${questionId}/versions/${versionNumber}/`,
    payload
  );
  return res.data;
};

export const publishVersion = async (
  questionId: string,
  versionNumber: number
): Promise<APIResponse<QuestionVersionDetail>> => {
  const res = await apiClient.post<APIResponse<QuestionVersionDetail>>(
    `/admin/questions/${questionId}/versions/${versionNumber}/publish/`
  );
  return res.data;
};

export const archiveVersion = async (
  questionId: string,
  versionNumber: number
): Promise<APIResponse<QuestionVersionDetail>> => {
  const res = await apiClient.post<APIResponse<QuestionVersionDetail>>(
    `/admin/questions/${questionId}/versions/${versionNumber}/archive/`
  );
  return res.data;
};

export const getQuestionVersionPreview = async (
  questionId: string,
  versionNumber: number
): Promise<APIResponse<QuestionVersionDetail>> => {
  const res = await apiClient.get<APIResponse<QuestionVersionDetail>>(
    `/admin/questions/${questionId}/versions/${versionNumber}/preview/`
  );
  return res.data;
};

export const getTags = async (): Promise<APIResponse<Tag[]>> => {
  const res = await apiClient.get<APIResponse<Tag[]>>('/admin/tags/');
  return res.data;
};
