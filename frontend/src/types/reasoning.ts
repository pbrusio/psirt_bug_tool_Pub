// AI Reasoning API Types

// Explain endpoint
export interface ExplainRequest {
  psirt_id?: string;
  psirt_summary?: string;
  labels?: string[];
  platform: string;
  device_id?: number;
  device_features?: string[];
  question_type?: 'why' | 'impact' | 'technical';
}

export interface ExplainResponse {
  request_id: string;
  psirt_id: string | null;
  platform: string;
  labels_explained: string[];
  explanation: string;
  device_context: string | null;
  affected: boolean | null;
  confidence: number;
  reasoning_time_ms: number;
  timestamp: string;
}

// Remediate endpoint
export interface RemediateRequest {
  psirt_id: string;
  platform: string;
  device_id?: number;
  device_version?: string;
  device_features?: string[];
  include_commands?: boolean;
  include_upgrade_path?: boolean;
}

export interface RemediationOption {
  action: 'disable_feature' | 'apply_acl' | 'upgrade' | 'workaround';
  title: string;
  description: string;
  commands: string[] | null;
  impact: string;
  effectiveness: 'full' | 'partial' | 'temporary';
}

export interface UpgradePath {
  current: string;
  target: string;
  direct_upgrade: boolean;
  intermediate_versions: string[] | null;
}

export interface RemediateResponse {
  request_id: string;
  psirt_id: string;
  platform: string;
  device_context: string | null;
  severity: string;
  options: RemediationOption[];
  recommended_option: number;
  upgrade_path: UpgradePath | null;
  confidence: number;
  reasoning_time_ms: number;
  timestamp: string;
}

// Ask endpoint
export interface AskRequest {
  question: string;
  context?: Record<string, unknown>;
}

export interface AskSource {
  type: string;
  [key: string]: unknown;
}

export interface AskResponse {
  request_id: string;
  question: string;
  answer: string;
  sources: AskSource[];
  suggested_actions: string[] | null;
  follow_up_questions: string[] | null;
  confidence: number;
  reasoning_time_ms: number;
  timestamp: string;
}

// Summary endpoint
export interface CriticalAction {
  priority: number;
  action: string;
  affected_devices: number;
  advisory: string | null;
}

export interface SummaryTrends {
  by_severity: Record<string, number>;
  by_platform: Record<string, number>;
}

export interface ImpactMetrics {
  total: number;
  critical_high: number;
  by_platform: Record<string, number>;
  affecting_inventory?: number;  // PSIRTs matching inventory platforms
  inventory_critical_high?: number;  // Critical+High PSIRTs matching inventory
}

export interface SummaryResponse {
  request_id: string;
  period: string;
  total_advisories: number;
  total_bugs_in_db?: number;
  inventory_devices_scanned?: number;
  inventory_critical_high?: number;
  inventory_medium_low?: number;
  inventory_platforms?: string[];  // Platforms in inventory
  affecting_environment: number;
  summary_text: string;
  risk_assessment: 'low' | 'moderate' | 'elevated' | 'critical';
  critical_actions: CriticalAction[];
  trends: SummaryTrends;
  bugs?: ImpactMetrics;
  psirts?: ImpactMetrics;
  timestamp: string;
}

// Health endpoint
export interface ReasoningHealthResponse {
  status: string;
  taxonomies_loaded: number;
  mlx_status: string;
  endpoints: string[];
}
