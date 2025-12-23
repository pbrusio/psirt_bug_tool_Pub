// API Request/Response Types

export interface AnalyzePSIRTRequest {
  summary: string;
  platform: string;
  advisory_id?: string;
}

export interface AnalysisResult {
  analysis_id: string;
  predicted_labels: string[];
  confidence?: number;
  config_regex: string[];
  show_commands: string[];
  timestamp: string;
  platform: string;
  psirt_summary: string;
  advisory_id?: string;
  source?: string;
  cached?: boolean;
  needs_review?: boolean;
}

export interface DeviceCredentials {
  host: string;
  username: string;
  password: string;
  device_type?: string;
}

export interface PSIRTMetadata {
  product_names: string[];
  bug_id?: string;
}

export interface FeatureSnapshot {
  snapshot_id: string;
  platform: string;
  extracted_at: string;
  features_present: string[];
  feature_count: number;
  total_checked: number;
  extractor_version: string;
  version?: string;
  hardware_model?: string | null;
}

export interface VerifyDeviceRequest {
  analysis_id: string;
  device: DeviceCredentials;
  psirt_metadata: PSIRTMetadata;
}

export interface VerifySnapshotRequest {
  analysis_id: string;
  snapshot: FeatureSnapshot;
  psirt_metadata?: PSIRTMetadata;
}

export interface VersionCheck {
  affected: boolean;
  reason: string;
  matched_versions?: string[];
}

export interface FeatureCheck {
  present: string[];
  absent: string[];
}

export interface VerificationResult {
  verification_id: string;
  analysis_id: string;
  device_hostname?: string;
  device_version?: string;
  device_platform?: string;
  version_check?: VersionCheck;
  feature_check?: FeatureCheck;
  overall_status: 'VULNERABLE' | 'NOT_VULNERABLE' | 'POTENTIALLY VULNERABLE' | 'LIKELY NOT VULNERABLE' | 'ERROR' | 'UNKNOWN';
  reason: string;
  evidence?: Record<string, string>;
  timestamp: string;
  error?: string;
}

export interface HealthResponse {
  status: string;
  timestamp: string;
}

export type Platform = 'IOS-XE' | 'IOS-XR' | 'ASA' | 'FTD' | 'NX-OS';

export const PLATFORMS: Platform[] = ['IOS-XE', 'IOS-XR', 'ASA', 'FTD', 'NX-OS'];

// Hardware Model Choices by Platform
export interface HardwareChoice {
  value: string | null;
  label: string;
}

export const HARDWARE_CHOICES_BY_PLATFORM: Record<Platform, HardwareChoice[]> = {
  'IOS-XE': [
    { value: null, label: 'Any Hardware (Generic Bugs Only)' },
    { value: 'Cat9200', label: 'Catalyst 9200 Series' },
    { value: 'Cat9300', label: 'Catalyst 9300 Series' },
    { value: 'Cat9400', label: 'Catalyst 9400 Series' },
    { value: 'Cat9500', label: 'Catalyst 9500 Series' },
    { value: 'Cat9600', label: 'Catalyst 9600 Series' },
    { value: 'Cat9800', label: 'Catalyst 9800 Series (Wireless)' },
    { value: 'C8200', label: 'Catalyst 8200 Series' },
    { value: 'C8300', label: 'Catalyst 8300 Series' },
    { value: 'C8500', label: 'Catalyst 8500 Series' },
    { value: 'C8000V', label: 'Catalyst 8000V (Virtual)' },
    { value: 'ISR4K', label: 'ISR 4000 Series' },
    { value: 'ASR1K', label: 'ASR 1000 Series' },
    { value: 'CSR1000v', label: 'CSR 1000v (Virtual)' },
  ],
  'IOS-XR': [
    { value: null, label: 'Any Hardware (Generic Bugs Only)' },
    { value: 'NCS540', label: 'NCS 540 Series' },
    { value: 'NCS560', label: 'NCS 560 Series' },
    { value: 'NCS5500', label: 'NCS 5500 Series' },
    { value: 'NCS5700', label: 'NCS 5700 Series' },
    { value: 'C8000', label: 'Cisco 8000 Series' },
    { value: 'ASR9K', label: 'ASR 9000 Series' },
  ],
  'NX-OS': [
    { value: null, label: 'Any Hardware (Generic Bugs Only)' },
    { value: 'N9K-9300', label: 'Nexus 9300 Series' },
    { value: 'N9K-9500', label: 'Nexus 9500 Series' },
    { value: 'N9K-9500R', label: 'Nexus 9500R Series' },
    { value: 'N3K', label: 'Nexus 3000 Series' },
    { value: 'MDS9K', label: 'MDS 9000 Series' },
  ],
  'FTD': [
    { value: null, label: 'Any Hardware (Generic Bugs Only)' },
    { value: 'FP3100', label: 'Secure Firewall 3100 Series' },
    { value: 'FP4100', label: 'Firepower 4100 Series' },
    { value: 'FP9300', label: 'Firepower 9300 Series' },
  ],
  'ASA': [
    { value: null, label: 'Any Hardware (Generic Bugs Only)' },
  ],
};

// Bug Scanner Types
// Note: "Bug" = software defect from Cisco Bug Search Tool (CSCxxxx IDs)
// "PSIRT/Advisory" = security advisory (cisco-sa-xxxx)
// Users are "susceptible to" bugs and "vulnerable to" PSIRTs/advisories

export interface ScanDeviceRequest {
  platform: string;
  version: string;
  hardware_model?: string | null;
  features?: string[];
  severity_filter?: number[];
  limit?: number;
  offset?: number;
}

export interface Bug {
  bug_id: string;
  severity: number;
  headline: string;
  summary: string;
  status: string;
  affected_versions: string;
  labels: string[];
  url: string;
}

export interface ScanResult {
  scan_id: string;
  platform: string;
  version: string;
  hardware_model?: string | null;
  features?: string[];
  total_bugs_checked: number;
  version_matches: number;
  hardware_filtered?: number;
  hardware_filtered_count?: number;
  feature_filtered?: number;
  critical_high: number;
  medium_low: number;
  // Separated bug/PSIRT counts (v3.1+)
  bug_count?: number;
  psirt_count?: number;
  bug_critical_high?: number;
  psirt_critical_high?: number;
  bugs: Bug[];
  filtered_bugs?: Bug[];
  timestamp: string;
  query_time_ms: number;
}
