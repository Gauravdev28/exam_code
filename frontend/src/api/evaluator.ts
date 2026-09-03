import apiClient from './client';
import { APIResponse } from '../types/api';
import { CodeRunResponse, CodeSubmissionResult } from '../types/evaluator';

export const evaluatorApi = {
  /**
   * Queue a test run on public test cases only.
   */
  runCode: async (
    attemptId: string,
    questionId: string,
    sourceCode: string,
    language: string,
    customInput?: string
  ): Promise<APIResponse<CodeRunResponse>> => {
    const response = await apiClient.post<APIResponse<CodeRunResponse>>(
      `/student/attempts/${attemptId}/questions/${questionId}/run/`,
      {
        source_code: sourceCode,
        language: language,
        custom_input: customInput || null,
      }
    );
    return response.data;
  },

  /**
   * Queue an authoritative evaluation against all test cases.
   */
  submitCode: async (
    attemptId: string,
    questionId: string,
    sourceCode: string,
    language: string
  ): Promise<APIResponse<CodeRunResponse>> => {
    const response = await apiClient.post<APIResponse<CodeRunResponse>>(
      `/student/attempts/${attemptId}/questions/${questionId}/submit/`,
      {
        source_code: sourceCode,
        language: language,
      }
    );
    return response.data;
  },

  /**
   * Retrieve or poll execution results for a submission.
   */
  getSubmissionResult: async (
    submissionId: string
  ): Promise<APIResponse<CodeSubmissionResult>> => {
    const response = await apiClient.get<APIResponse<CodeSubmissionResult>>(
      `/student/submissions/${submissionId}/`
    );
    return response.data;
  },
};
