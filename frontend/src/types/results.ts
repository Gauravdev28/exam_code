export type ResultStatus = 'PENDING' | 'PROCESSING' | 'FINALIZED';

export interface QuestionResult {
  id: string;
  question_id: string;
  order: number;
  title: string;
  question_type: string;
  earned_points: string;
  max_points: string;
  is_correct: boolean;
  is_partially_correct: boolean;
  is_skipped: boolean;
  evaluation_details: Record<string, any>;
  time_spent_seconds: number;
  tags?: string[];
}

export interface AssessmentResult {
  id: string;
  attempt_id: string;
  assessment_id: string;
  assessment_title: string;
  student?: {
    id: string;
    email: string;
    full_name: string;
    roll_number: string;
    euid: string;
  };
  status: ResultStatus;
  total_score_earned: string;
  total_possible_score: string;
  percentage: string;
  is_passed: boolean | null;
  is_released?: boolean;
  total_questions: number;
  answered_questions: number;
  correct_questions: number;
  partially_correct_questions: number;
  incorrect_questions: number;
  skipped_questions: number;
  time_spent_seconds: number;
  finalized_at: string;
  question_results?: QuestionResult[];
  proctoring_summary?: {
    risk_score: string;
    risk_band: string;
    review_status?: string;
    status: string;
  } | null;
}

export interface ScoreDistributionBucket {
  bucket: string;
  count: number;
}

export interface AssessmentAnalytics {
  assessment_id: string;
  assessment_title: string;
  cohort_metrics: {
    total_assigned: number;
    total_started: number;
    total_completed: number;
    total_expired: number;
    completion_rate_percentage: number;
    pass_rate_percentage: number;
  };
  score_statistics: {
    mean_score: string;
    median_score: string;
    highest_score: string;
    lowest_score: string;
    standard_deviation: string;
    quartiles: {
      q1: string;
      q2: string;
      q3: string;
    };
  };
  score_distribution: ScoreDistributionBucket[];
  proctoring_risk_correlation: {
    is_available: boolean;
    reason?: string;
    min_cohort_threshold_met?: boolean;
    distribution?: Record<string, { count: number; average_score: string }>;
  };
}

export interface QuestionAnalyticsItem {
  snapshot_question_id: string;
  order: number;
  question_type: string;
  title: string;
  difficulty_index_p: number;
  discrimination_index_d: number | null;
  average_score: string;
  max_points: string;
  average_time_spent_seconds: number;
  breakdown: {
    total_responses: number;
    correct: number;
    partially_correct: number;
    incorrect: number;
    skipped: number;
  };
}

export interface StudentTopicPerformance {
  tag_name: string;
  questions_attempted: number;
  accuracy_percentage: number;
  earned_points: string;
  max_points: string;
}

export interface ReportJob {
  id: string;
  report_type: 'STUDENT_SCORECARD' | 'ASSESSMENT_SUMMARY' | 'ASSESSMENT_ROSTER';
  format: 'PDF' | 'XLSX' | 'CSV';
  status: 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED' | 'EXPIRED';
  file_size_bytes: number;
  sha256_hash?: string;
  error_message?: string;
  download_url?: string;
  expires_at: string;
  created_at: string;
  completed_at?: string;
}
