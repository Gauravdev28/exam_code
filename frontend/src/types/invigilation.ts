import { RiskBand } from './proctoring';

export type InterventionEventType =
  | 'WARNING_ISSUED'
  | 'WARNING_ACKNOWLEDGED'
  | 'PAUSE_STARTED'
  | 'PAUSE_ENDED'
  | 'ROOM_SCAN_REQUESTED'
  | 'ROOM_SCAN_COMPLETED'
  | 'TERMINATION_REQUESTED';

export interface ProctorAssignment {
  id: string;
  proctor: string;
  proctor_email: string;
  assessment: string;
  assessment_title: string;
  is_active: boolean;
  max_candidates: number;
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface ProctorIntervention {
  id: string;
  attempt: string;
  proctor: string | null;
  proctor_email: string | null;
  student: string;
  student_email: string;
  event_type: InterventionEventType;
  reason_code: string;
  reason_text: string;
  internal_notes?: string;
  parent_event: string | null;
  metadata: Record<string, any>;
  issued_at: string;
}

export interface StudentIntervention {
  id: string;
  attempt: string;
  event_type: InterventionEventType;
  reason_code: string;
  reason_text: string;
  parent_event: string | null;
  issued_at: string;
}

export interface ProctorChatMessage {
  id: string;
  attempt: string;
  sender: string;
  sender_email: string;
  sender_role: string;
  recipient: string;
  recipient_email: string;
  message_text: string;
  is_read: boolean;
  sent_at: string;
}

export interface TriageCandidate {
  attempt_id: string;
  student_id: string;
  student_name: string;
  student_email: string;
  roll_number: string;
  euid: string;
  status: string;
  is_paused: boolean;
  paused_at: string | null;
  risk_band: RiskBand;
  risk_score: number;
  events_count: number;
  remaining_seconds: number;
  started_at: string | null;
  expires_at: string | null;
  priority_rank: number;
  latest_keyframe_url?: string;
}

export interface WarningPayload {
  reason_code: string;
  message: string;
  internal_notes?: string;
  idempotency_key?: string;
}

export interface PausePayload {
  reason?: string;
  internal_notes?: string;
  idempotency_key?: string;
  max_pause_seconds?: number;
}

export interface ResumePayload {
  reason?: string;
  internal_notes?: string;
  idempotency_key?: string;
}

export interface TerminatePayload {
  reason_code: string;
  formal_justification: string;
  internal_notes?: string;
  idempotency_key?: string;
}
