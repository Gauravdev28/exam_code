export interface Section {
  id: string;
  code: string;
  name: string;
  is_active: boolean;
  student_count?: number;
  created_at?: string;
  updated_at?: string;
}

export interface CreateSectionPayload {
  code: string;
  name: string;
  is_active?: boolean;
}

export interface UpdateSectionPayload {
  name?: string;
  is_active?: boolean;
}
