/**
 * System Administration Types
 */

export interface UpdateResponse {
  success: boolean;
  inserted: number;
  updated: number;
  skipped: number;
  errors: number;
  total_processed: number;
  error_message?: string | null;
  package_name: string;
  hash_verified: boolean;
  manifest?: Record<string, unknown> | null;
  timestamp: string;
}

export interface ValidationResponse {
  valid: boolean;
  error?: string | null;
  item_count: number;
  hash_verified: boolean;
  hash_message: string;
  manifest?: Record<string, unknown> | null;
}

export interface DetailedStats {
  total: number;
  by_platform: Record<string, number>;
  labeled_count: number;
  unlabeled_count: number;
}

export interface DBStatsResponse {
  success: boolean;
  total_bugs: number;
  by_platform: Record<string, number>;
  by_type: Record<string, number>;
  labeled_count: number;
  unlabeled_count: number;
  // NEW: Separated stats
  bugs?: DetailedStats | null;
  psirts?: DetailedStats | null;
  // Rest unchanged
  last_import?: {
    timestamp: string;
    manifest?: Record<string, unknown>;
    stats?: Record<string, number>;
  } | null;
  db_size_mb: number;
  table_counts: Record<string, number>;
}

export interface SystemHealthResponse {
  status: 'healthy' | 'degraded' | 'error';
  database: {
    status: string;
    bug_count?: number;
    journal_mode?: string;
    path?: string;
    exists?: boolean;
    error?: string;
  };
  model: {
    status: string;
    lora_adapter: boolean;
    faiss_index: boolean;
    faiss_size_mb: number;
  };
  cache: {
    status: string;
    psirt_cache_entries: number;
  };
  uptime_info: {
    timestamp: string;
    python_version?: string;
  };
}

export interface CacheClearResponse {
  success: boolean;
  cleared: Record<string, number>;
  message: string;
}

export interface CacheStatsResponse {
  success: boolean;
  cache_stats: {
    psirt_cache: {
      entries: number;
      exists: boolean;
    };
  };
}
