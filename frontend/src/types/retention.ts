export interface RetentionMetrics {
  confirmed_bytes_reclaimed: number;
  confirmed_mb_reclaimed: number;
  total_tombstones_count: number;
  active_legal_holds_count: number;
  upcoming_purges_7d_count: number;
  due_today_count: number;
  deferred_holds_count: number;
  deferred_exports_count: number;
  pending_file_cleanups_count: number;
  pending_file_cleanup_bytes: number;
  active_policies_count: number;
}

export type PolicyScope = 'INSTITUTION' | 'ASSESSMENT';

export interface RetentionPolicy {
  id: string;
  name: string;
  version: number;
  scope: PolicyScope;
  assessment?: string | null;
  assessment_title?: string | null;
  detailed_data_ttl_days: number;
  proctoring_evidence_ttl_days: number;
  report_retention_ttl_days: number;
  is_active: boolean;
  created_by_email?: string;
  created_at: string;
  updated_at: string;
}

export type LegalHoldScope = 'ATTEMPT' | 'STUDENT' | 'ASSESSMENT';
export type LegalHoldStatus = 'ACTIVE' | 'RELEASED';

export interface LegalHold {
  id: string;
  title: string;
  case_reference: string;
  reason: string;
  scope: LegalHoldScope;
  attempt?: string | null;
  student?: string | null;
  student_email?: string | null;
  assessment?: string | null;
  assessment_title?: string | null;
  status: LegalHoldStatus;
  placed_by_email?: string;
  placed_at: string;
  released_by_email?: string | null;
  released_at?: string | null;
  release_reason?: string | null;
  created_at: string;
}

export type PurgeState =
  | 'SCHEDULED'
  | 'DEFERRED_HOLD'
  | 'DEFERRED_EXPORT'
  | 'SCRUBBING_DB'
  | 'CLEANING_FILES'
  | 'PURGED';

export interface RetentionRecord {
  id: string;
  attempt: string;
  assessment_title: string;
  student_euid: string;
  retention_policy: string;
  policy_version: number;
  detailed_data_expires_at: string;
  proctoring_evidence_expires_at: string;
  purge_state: PurgeState;
  database_scrub_status: string;
  filesystem_cleanup_status: string;
  last_scrubbed_at?: string | null;
  created_at: string;
}

export interface RetentionTombstone {
  id: string;
  attempt_id: string;
  student_id: string;
  student_euid: string;
  assessment_id: string;
  assessment_title_snapshot: string;
  purged_at: string;
  purged_by_system: boolean;
  operator_email?: string | null;
  answers_scrubbed_count: number;
  code_submissions_scrubbed_count: number;
  proctoring_events_scrubbed_count: number;
  evidence_files_deleted_count: number;
  confirmed_bytes_reclaimed: number;
  sha256_audit_proof: string;
  created_at: string;
}

export type ExportStatus =
  | 'REQUESTED'
  | 'SNAPSHOT_PENDING'
  | 'SNAPSHOT_ACQUIRED'
  | 'GENERATING'
  | 'READY'
  | 'EXPIRED'
  | 'FAILED';

export interface ExportJob {
  id: string;
  student: string;
  attempt?: string | null;
  assessment_title?: string | null;
  status: ExportStatus;
  archive_type: string;
  started_at?: string | null;
  lease_expires_at?: string | null;
  encryption_algorithm: string;
  encryption_key_version: string;
  file_bytes: number;
  expires_at?: string | null;
  error_message?: string | null;
  created_at: string;
}

export interface StudentRetentionAttempt {
  attempt_id: string;
  assessment_title: string;
  submitted_at: string | null;
  purge_state: PurgeState;
  detailed_data_expires_at: string | null;
  days_remaining_until_purge: number | null;
}

export interface StudentRetentionStatus {
  default_policy_days: number;
  attempts: StudentRetentionAttempt[];
}

export interface PurgeCandidate {
  attempt_id: string;
  assessment_id: string;
  assessment_title: string;
  student_id: string;
  student_euid: string;
  detailed_data_expires_at: string;
  current_purge_state: PurgeState;
  is_eligible: boolean;
}

export interface PurgePreviewResponse {
  preview_token: string;
  total_candidates: number;
  eligible_count: number;
  candidates: PurgeCandidate[];
  valid_for_seconds: number;
}

export interface PurgeExecutionSummary {
  job_run_id: string;
  evaluated_count: number;
  purged_count: number;
  deferred_hold_count: number;
  deferred_export_count: number;
}
