export type QuestionType =
  | 'MCQ'
  | 'MULTI_SELECT'
  | 'TRUE_FALSE'
  | 'SHORT_ANSWER'
  | 'CODING'
  | 'SQL';

export type Difficulty = 'EASY' | 'MEDIUM' | 'HARD';

export type VersionStatus = 'DRAFT' | 'PUBLISHED' | 'ARCHIVED';

export type QuestionStatus = 'ACTIVE' | 'ARCHIVED';

export type CodingLanguage = 'PYTHON' | 'CPP' | 'JAVA';

export interface Tag {
  id: string;
  name: string;
  slug: string;
  created_at: string;
}

export interface TestCase {
  id?: string;
  name?: string;
  input_data: string;
  expected_output: string;
  points: number;
  is_hidden: boolean;
  is_verified?: boolean;
  difficulty?: Difficulty;
  execution_order: number;
  time_limit_override_ms?: number | null;
  memory_limit_override_mb?: number | null;
}

export interface CodingQuestionConfig {
  id?: string;
  problem_statement: string;
  input_description?: string;
  output_description?: string;
  constraints?: string;
  allowed_languages: CodingLanguage[];
  time_limit_ms: number;
  memory_limit_mb: number;
  starter_codes?: Record<string, string>;
  examples?: Array<{ id?: string; name?: string; input: string; output: string; explanation?: string }>;
  reference_solutions?: Record<string, string>;
  reference_solution_language?: string;
  reference_solution_hash?: string;
  reference_solution_verified?: boolean;
  reference_solution_verified_at?: string | null;
  test_cases?: TestCase[];
}

export interface SQLQuestionConfig {
  id?: string;
  problem_statement: string;
  schema_setup_sql: string;
  expected_result_definition: string;
  allowed_dialect: string;
  time_limit_ms: number;
}

export interface QuestionHealthCheck {
  key: string;
  display_name: string;
  passed: boolean;
  message: string;
}

export interface QuestionHealthStatus {
  is_ready: boolean;
  status: string;
  passed_checks: number;
  total_checks: number;
  checks: QuestionHealthCheck[];
  errors: string[];
}

export interface PlatformImportStatus {
  hackerrank: { configured: boolean; auth_mode: string; message: string };
  leetcode: { configured: boolean; auth_mode: string; message: string };
  zip_package: { supported: boolean; auth_mode: string; message: string };
  manual_json: { supported: boolean; auth_mode: string; message: string };
}

export interface PlatformImportPreview {
  source: string;
  title: string;
  difficulty: Difficulty;
  tags: string[];
  languages: CodingLanguage[];
  examples: Array<{ input: string; output: string; explanation?: string }>;
  test_case_count: number;
  sample_test_count: number;
  hidden_test_count: number;
  has_reference_solution: boolean;
  reference_solution_language: string;
  expected_output_verification_status: string;
  import_status: string;
  normalized_payload: any;
}

export interface SupportedLanguageItem {
  key: CodingLanguage;
  label: string;
  monaco_lang: string;
  judge0_id: number;
  default_starter_code: string;
}

export interface QuestionVersionSummary {
  id: string;
  version_number: number;
  question_type: QuestionType;
  title: string;
  points: number;
  difficulty: Difficulty;
  status: VersionStatus;
  tags: Tag[];
  published_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface QuestionVersionDetail {
  id: string;
  question_id: string;
  version_number: number;
  question_type: QuestionType;
  title: string;
  description: string;
  instructions: string;
  points: number;
  negative_marking_enabled: boolean;
  negative_points: number;
  difficulty: Difficulty;
  tags: Tag[];
  status: VersionStatus;
  type_config: Record<string, any>;
  coding_config?: CodingQuestionConfig | null;
  sql_config?: SQLQuestionConfig | null;
  health_status?: QuestionHealthStatus | null;
  created_by_email?: string;
  published_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface QuestionItem {
  id: string;
  question_type: QuestionType;
  status: QuestionStatus;
  created_by_email?: string;
  latest_version?: QuestionVersionSummary | null;
  published_version?: QuestionVersionSummary | null;
  created_at: string;
  updated_at: string;
}

export interface CreateQuestionPayload {
  question_type: QuestionType;
  title: string;
  description: string;
  instructions?: string;
  points: number;
  negative_marking_enabled?: boolean;
  negative_points?: number;
  difficulty: Difficulty;
  tags?: string[];
  type_config?: Record<string, any>;
  coding_config?: Partial<CodingQuestionConfig>;
  test_cases?: TestCase[];
  sql_config?: Partial<SQLQuestionConfig>;
}

export interface UpdateQuestionVersionPayload {
  title?: string;
  description?: string;
  instructions?: string;
  points?: number;
  negative_marking_enabled?: boolean;
  negative_points?: number;
  difficulty?: Difficulty;
  tags?: string[];
  type_config?: Record<string, any>;
  coding_config?: Partial<CodingQuestionConfig>;
  test_cases?: TestCase[];
  sql_config?: Partial<SQLQuestionConfig>;
}
