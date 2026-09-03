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
  input_data: string;
  expected_output: string;
  points: number;
  is_hidden: boolean;
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
