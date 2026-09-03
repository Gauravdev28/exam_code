export type SubmissionType = 'RUN' | 'SUBMIT';

export type SubmissionStatus =
  | 'QUEUED'
  | 'PROCESSING'
  | 'COMPILING'
  | 'RUNNING'
  | 'EVALUATING'
  | 'COMPLETED'
  | 'FAILED'
  | 'CANCELLED';

export type CodeVerdict =
  | 'ACCEPTED'
  | 'WRONG_ANSWER'
  | 'TIME_LIMIT_EXCEEDED'
  | 'MEMORY_LIMIT_EXCEEDED'
  | 'COMPILATION_ERROR'
  | 'RUNTIME_ERROR'
  | 'OUTPUT_LIMIT_EXCEEDED'
  | 'SYSTEM_ERROR';

export type TestCaseVerdict =
  | 'PASSED'
  | 'FAILED'
  | 'TIME_LIMIT_EXCEEDED'
  | 'MEMORY_LIMIT_EXCEEDED'
  | 'RUNTIME_ERROR';

export interface StudentTestCaseResult {
  index: number;
  is_hidden: boolean;
  verdict: TestCaseVerdict;
  points_awarded: string | number;
  max_points: string | number;
  execution_time_ms: number;
  memory_used_kb: number;
  input: string | null;
  expected_output: string | null;
  actual_output: string | null;
  error_message: string | null;
}

export interface CodeSubmissionResult {
  submission_id: string;
  status: SubmissionStatus;
  verdict: CodeVerdict | null;
  submission_type: SubmissionType;
  language: string;
  total_test_cases: number;
  passed_test_cases: number;
  score_awarded: string;
  max_score: number;
  execution_time_ms: number;
  memory_used_kb: number;
  compilation_error: string | null;
  test_cases: StudentTestCaseResult[];
  started_at: string | null;
  completed_at: string | null;
}

export interface CodeRunResponse {
  submission_id: string;
  status: SubmissionStatus;
  submission_type: SubmissionType;
  language: string;
  is_new: boolean;
  estimated_wait_seconds: number;
}
