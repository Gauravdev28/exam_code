export interface StudentProfile {
  id: string;
  user_id: string;
  email: string;
  role: string;
  roll_number: string;
  euid: string;
  is_active: boolean;
  first_login_required: boolean;
  created_at: string;
  updated_at: string;
}

export interface CreateStudentPayload {
  email: string;
  roll_number: string;
}

export interface UpdateStudentPayload {
  email?: string;
  roll_number?: string;
}

export interface ImportPreviewRow {
  row_number: number;
  roll_number: string;
  email: string;
  euid: string;
  status: 'VALID' | 'INVALID' | 'DUPLICATE';
  errors: string[];
}

export interface ImportPreviewReport {
  total_rows: number;
  valid_count: number;
  invalid_count: number;
  duplicate_count: number;
  rows: ImportPreviewRow[];
}

export interface ImportConfirmPayload {
  filename: string;
  students: CreateStudentPayload[];
}

export interface ImportConfirmResult {
  total_submitted: number;
  created_count: number;
  failed_count: number;
  created_students: Array<{
    id: string;
    email: string;
    roll_number: string;
    euid: string;
  }>;
  failed_rows: Array<{
    roll_number: string;
    email: string;
    error: string;
  }>;
}

export interface ChangePasswordPayload {
  current_password: string;
  new_password: string;
  confirm_password: string;
}
