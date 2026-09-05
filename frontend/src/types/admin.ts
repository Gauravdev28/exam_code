export interface Administrator {
  id: string;
  admin_id: string;
  email: string;
  display_name: string;
  first_name: string;
  role: 'ADMIN';
  is_active: boolean;
  is_primary?: boolean;
  first_login_required?: boolean;
  last_login?: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateAdminPayload {
  email: string;
  display_name?: string;
  password: string;
  confirm_password: string;
  is_active?: boolean;
}

export interface UpdateAdminPayload {
  display_name?: string;
  email?: string;
}

export interface ResetPasswordPayload {
  reason: string;
  temporary_password: string;
  confirm_temporary_password: string;
}

export interface OperationalMetrics {
  active_assessments: number;
  upcoming_assessments: number;
  completed_assessments: number;
  total_students: number;
}

export interface RecentAssessmentItem {
  id: string;
  title: string;
  status: string;
  start_datetime: string | null;
  end_datetime: string | null;
  duration_minutes: number;
  candidates_count: number;
}

export interface UpcomingAssessmentItem {
  id: string;
  title: string;
  status: string;
  start_datetime: string | null;
  duration_minutes: number;
}

export interface RecentActivityItem {
  id: string;
  action: string;
  actor_name: string;
  target_type: string;
  target_id: string;
  timestamp: string;
  metadata: Record<string, any>;
}

export interface AdminDashboardOverview {
  metrics: OperationalMetrics;
  recent_assessments: RecentAssessmentItem[];
  upcoming_assessments: UpcomingAssessmentItem[];
  recent_activity: RecentActivityItem[];
}

export interface SecurityAuditLog {
  id: string;
  action: string;
  actor_id: string | null;
  actor_name: string;
  actor_admin_id: string;
  target_type: string;
  target_id: string;
  target_identity: string;
  target_email: string;
  target_role: string;
  reason: string;
  result: 'SUCCESS' | 'FAILURE';
  metadata: Record<string, any>;
  ip_address: string | null;
  created_at: string;
}

export interface ResetPasswordResponse {
  temporary_password: string;
  student?: {
    id: string;
    user_id: string;
    email: string;
    euid: string;
    roll_number: string;
  };
  administrator?: {
    id: string;
    email: string;
    admin_id: string;
  };
}

