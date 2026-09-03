export type UserRole = 'ADMIN' | 'STUDENT';

export interface User {
  id: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  is_staff: boolean;
  first_login_required?: boolean;
  student_profile?: {
    id: string;
    roll_number: string;
    euid: string;
    first_login_required: boolean;
  };
  created_at: string;
  updated_at: string;
}

export interface LoginCredentials {
  email?: string;
  identifier?: string;
  password: string;
}

export interface AuthResponseData {
  user: User;
  csrf_token: string;
}
