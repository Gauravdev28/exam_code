export interface APIResponse<T = any> {
  status: 'success' | 'error';
  message?: string;
  data?: T;
  error?: {
    code: string;
    message: string;
    details?: any;
  };
}

export interface PaginatedData<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface PaginatedResponse<T> {
  status: 'success' | 'error';
  message?: string;
  data: PaginatedData<T>;
  error?: {
    code: string;
    message: string;
    details?: any;
  };
}

export interface ServiceHealth {
  status: 'healthy' | 'degraded' | 'unhealthy';
  latency_ms?: number;
  engine?: string;
  mode?: string;
  error?: string;
  message?: string;
}

export interface SystemHealthData {
  application: string;
  version: string;
  timestamp: string;
  environment: string;
  status: 'healthy' | 'degraded' | 'unhealthy';
  services: {
    database?: ServiceHealth;
    redis?: ServiceHealth;
    [key: string]: ServiceHealth | undefined;
  };
}
