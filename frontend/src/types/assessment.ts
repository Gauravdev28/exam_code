import { QuestionType, Difficulty } from './question';

export type AssessmentStatus = 'DRAFT' | 'PUBLISHED' | 'ARCHIVED';
export type AssignmentStatus = 'ASSIGNED' | 'REVOKED';
export type AttemptStatus = 'NOT_STARTED' | 'IN_PROGRESS' | 'SUBMITTED' | 'EXPIRED' | 'CANCELLED';
export type ResultVisibility = 'IMMEDIATE' | 'AFTER_DEADLINE' | 'MANUAL';

export interface AssessmentQuestionAdmin {
  id: string;
  question_version_id: string;
  version_number: number;
  question_title: string;
  question_type: QuestionType;
  difficulty: Difficulty;
  order: number;
  points: number;
  negative_marking_enabled: boolean;
  negative_points: number;
  tags: string[];
  created_at: string;
}

export interface AudienceSectionSummary {
  id: string;
  code: string;
  name: string;
  is_active: boolean;
  student_count: number;
}

export interface AudienceStudentSummary {
  id: string;
  email: string;
  display_name: string;
  roll_number: string;
  euid: string;
  section: string | null;
}

export interface AudienceResolution {
  section_student_count: number;
  individual_student_count: number;
  overlap_count: number;
  total_eligible: number;
  eligible_student_ids: string[];
  sections: AudienceSectionSummary[];
  additional_students: AudienceStudentSummary[];
}

export interface ConfigureAudiencePayload {
  section_ids?: string[];
  student_ids?: string[];
  target_section_ids?: string[];
  target_student_ids?: string[];
}

export interface AssessmentAdminItem {
  id: string;
  title: string;
  status: AssessmentStatus;
  start_datetime: string;
  end_datetime: string;
  duration_minutes: number;
  total_points: number;
  passing_percentage?: number;
  attempt_limit: number;
  negative_marking_enabled: boolean;
  randomize_questions: boolean;
  randomize_options: boolean;
  result_visibility: ResultVisibility;
  question_count: number;
  assigned_count: number;
  eligible_students_count?: number;
  target_sections_summary?: string;
  audience_summary?: {
    total_eligible: number;
    sections_count: number;
    individual_students_count: number;
    section_codes: string[];
  };
  created_by_email?: string;
  published_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface AssessmentAdminDetail extends AssessmentAdminItem {
  description: string;
  instructions: string;
  assessment_questions: AssessmentQuestionAdmin[];
}

export interface CreateAssessmentPayload {
  title: string;
  description: string;
  instructions?: string;
  start_datetime: string;
  end_datetime: string;
  duration_minutes: number;
  total_points: number;
  passing_percentage?: number;
  negative_marking_enabled?: boolean;
  attempt_limit?: number;
  randomize_questions?: boolean;
  randomize_options?: boolean;
  result_visibility?: ResultVisibility;
}

export interface UpdateAssessmentPayload {
  title?: string;
  description?: string;
  instructions?: string;
  start_datetime?: string;
  end_datetime?: string;
  duration_minutes?: number;
  total_points?: number;
  passing_percentage?: number;
  negative_marking_enabled?: boolean;
  attempt_limit?: number;
  randomize_questions?: boolean;
  randomize_options?: boolean;
  result_visibility?: ResultVisibility;
  target_section_ids?: string[];
  target_student_ids?: string[];
  section_ids?: string[];
  student_ids?: string[];
}

export interface AddAssessmentQuestionPayload {
  question_version_id: string;
  order?: number;
  points?: number;
  negative_marking_enabled?: boolean;
  negative_points?: number;
}

export interface AssessmentAssignmentItem {
  id: string;
  student_id: string;
  user_id?: string;
  student_profile_id?: string | null;
  student_email: string;
  student_roll_number?: string | null;
  status: AssignmentStatus;
  assigned_by_email?: string;
  assigned_at: string;
}

// --- Student Types ---

export interface StudentAssessmentItem {
  id: string;
  title: string;
  description: string;
  instructions: string;
  start_datetime: string;
  end_datetime: string;
  duration_minutes: number;
  total_points: number;
  attempt_limit: number;
  attempts_used: number;
  is_eligible: boolean;
  active_attempt_id?: string | null;
}

export interface StudentSnapshotQuestion {
  snapshot_question_id: string;
  order: number;
  question_type: QuestionType;
  title: string;
  description: string;
  instructions: string;
  points: number;
  negative_marking_enabled: boolean;
  negative_points: number;
  difficulty: Difficulty;
  type_config: Record<string, any>;
  coding_config?: {
    problem_statement?: string;
    input_description?: string;
    output_description?: string;
    constraints?: string;
    allowed_languages?: string[];
    time_limit_ms?: number;
    memory_limit_mb?: number;
    public_test_cases?: Array<{
      input_data: string;
      expected_output: string;
      points: number;
      is_hidden: boolean;
      execution_order: number;
    }>;
  };
  sql_config?: {
    problem_statement?: string;
    schema_setup_sql?: string;
    allowed_dialect?: string;
    time_limit_ms?: number;
  };
  tags: string[];
}

export interface StudentAnswerData {
  question_id: string;
  question_type: QuestionType;
  revision: number;
  selected_options?: string[] | null;
  text_response?: string | null;
  code_response?: string | null;
  code_language?: string | null;
  sql_response?: string | null;
  is_answered: boolean;
  last_saved_at?: string;
}

export interface StudentAttemptDetail {
  attempt_id: string;
  assessment_id: string;
  title: string;
  instructions: string;
  status: AttemptStatus;
  attempt_number: number;
  started_at: string;
  expires_at: string;
  submitted_at?: string | null;
  remaining_seconds: number;
  questions: StudentSnapshotQuestion[];
  answers: Record<string, StudentAnswerData>;
}

export interface SaveAnswerPayload {
  selected_options?: string[];
  text_response?: string;
  code_response?: string;
  code_language?: string;
  sql_response?: string;
  revision: number;
}
