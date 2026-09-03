export type ProctoringSessionStatus = 'ACTIVE' | 'PAUSED' | 'TERMINATED' | 'DEGRADED';

export type RiskBand = 'NORMAL' | 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export type ReviewStatus = 'UNREVIEWED' | 'UNDER_REVIEW' | 'REVIEWED' | 'DISMISSED' | 'ESCALATED';

export type EventSource = 'BROWSER' | 'AI' | 'SERVER' | 'SYSTEM';

export type EventSeverity = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export interface ProctoringWarning {
  id: string;
  warning_type: string;
  message: string;
  issued_at: string;
  acknowledged_at: string | null;
}

export interface ProctoringEvent {
  id: string;
  event_type: string;
  source: EventSource;
  severity: EventSeverity;
  confidence: number;
  started_at: string;
  ended_at: string | null;
  duration_ms: number;
  client_detected_at: string | null;
  server_received_at: string;
  model_name: string;
  model_version: string;
  threshold_version: string;
  inference_policy_version: string;
  risk_delta: string;
  metadata: Record<string, any>;
  evidence_id: string | null;
}

export interface ProctoringReview {
  id: string;
  decision: string;
  notes: string;
  reviewed_by: string;
  reviewed_at: string;
}

export interface StudentProctoringSession {
  session_id: string;
  status: ProctoringSessionStatus;
  frame_sampling_interval_seconds: number;
  heartbeat_interval_seconds: number;
  created_at: string;
}

export interface AdminProctoringSessionSummary {
  session_id: string;
  attempt_id: string;
  student: {
    id: string;
    email: string;
    euid: string;
    full_name: string;
  };
  status: ProctoringSessionStatus;
  risk_score: string;
  risk_band: RiskBand;
  total_events_count: number;
  total_warnings_count: number;
  review_status: ReviewStatus;
  created_at: string;
  updated_at: string;
}

export interface AdminProctoringSessionDetail extends AdminProctoringSessionSummary {
  events: ProctoringEvent[];
  warnings: ProctoringWarning[];
  review: ProctoringReview | null;
}
