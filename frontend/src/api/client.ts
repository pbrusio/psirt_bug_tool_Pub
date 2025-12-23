import axios, { AxiosError } from 'axios';
import type {
  AnalyzePSIRTRequest,
  AnalysisResult,
  VerifyDeviceRequest,
  VerifySnapshotRequest,
  VerificationResult,
  HealthResponse,
  ScanDeviceRequest,
  ScanResult,
  DeviceCredentials,
  FeatureSnapshot,
} from '../types';
import type {
  UpdateResponse,
  ValidationResponse,
  DBStatsResponse,
  SystemHealthResponse,
  CacheClearResponse,
  CacheStatsResponse,
} from '../types/system';
import type {
  ExplainRequest,
  ExplainResponse,
  RemediateRequest,
  RemediateResponse,
  AskRequest,
  AskResponse,
  SummaryResponse,
  ReasoningHealthResponse,
} from '../types/reasoning';
import { API_BASE_URL, ADMIN_API_KEY } from './config';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 300000, // 5 minutes for device verification
});

// Add request interceptor to include X-ADMIN-KEY for write operations
apiClient.interceptors.request.use((config) => {
  // Add admin key header for POST/PUT/DELETE/PATCH requests when configured
  if (ADMIN_API_KEY && ['post', 'put', 'delete', 'patch'].includes(config.method?.toLowerCase() || '')) {
    config.headers['X-ADMIN-KEY'] = ADMIN_API_KEY;
  }
  return config;
});

export class APIError extends Error {
  constructor(
    message: string,
    public statusCode?: number,
    public details?: unknown
  ) {
    super(message);
    this.name = 'APIError';
  }
}

function handleAPIError(error: unknown): never {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<{ detail?: string }>;
    const message = axiosError.response?.data?.detail || axiosError.message;
    throw new APIError(message, axiosError.response?.status, axiosError.response?.data);
  }
  throw error;
}

export const api = {
  async analyzePSIRT(request: AnalyzePSIRTRequest): Promise<AnalysisResult> {
    try {
      const response = await apiClient.post<AnalysisResult>('/analyze-psirt', request);
      return response.data;
    } catch (error) {
      handleAPIError(error);
    }
  },

  async verifyDevice(request: VerifyDeviceRequest): Promise<VerificationResult> {
    try {
      const response = await apiClient.post<VerificationResult>('/verify-device', request);
      return response.data;
    } catch (error) {
      handleAPIError(error);
    }
  },

  async verifySnapshot(request: VerifySnapshotRequest): Promise<VerificationResult> {
    try {
      const response = await apiClient.post<VerificationResult>('/verify-snapshot', request);
      return response.data;
    } catch (error) {
      handleAPIError(error);
    }
  },

  async getAnalysisResult(analysisId: string): Promise<AnalysisResult> {
    try {
      const response = await apiClient.get<AnalysisResult>(`/results/${analysisId}`);
      return response.data;
    } catch (error) {
      handleAPIError(error);
    }
  },

  async healthCheck(): Promise<HealthResponse> {
    try {
      const response = await apiClient.get<HealthResponse>('/health');
      return response.data;
    } catch (error) {
      handleAPIError(error);
    }
  },

  async scanDevice(request: ScanDeviceRequest): Promise<ScanResult> {
    try {
      const response = await apiClient.post<ScanResult>('/scan-device', request);
      return response.data;
    } catch (error) {
      handleAPIError(error);
    }
  },

  async extractFeatures(credentials: DeviceCredentials, platform?: string): Promise<FeatureSnapshot> {
    try {
      const response = await apiClient.post<FeatureSnapshot>('/extract-features', {
        device: credentials,
        platform,
      });
      return response.data;
    } catch (error) {
      handleAPIError(error);
    }
  },
};

// System administration API
export const systemApi = {
  async uploadOfflinePackage(file: File, skipHash: boolean = false): Promise<UpdateResponse> {
    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await apiClient.post<UpdateResponse>(
        `/system/update/offline?skip_hash=${skipHash}`,
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
          timeout: 600000, // 10 minutes for large uploads
        }
      );
      return response.data;
    } catch (error) {
      handleAPIError(error);
    }
  },

  async validatePackage(file: File): Promise<ValidationResponse> {
    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await apiClient.post<ValidationResponse>(
        '/system/update/validate',
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
        }
      );
      return response.data;
    } catch (error) {
      handleAPIError(error);
    }
  },

  async getDatabaseStats(): Promise<DBStatsResponse> {
    try {
      const response = await apiClient.get<DBStatsResponse>('/system/stats/database');
      return response.data;
    } catch (error) {
      handleAPIError(error);
    }
  },

  async getSystemHealth(): Promise<SystemHealthResponse> {
    try {
      const response = await apiClient.get<SystemHealthResponse>('/system/health');
      return response.data;
    } catch (error) {
      handleAPIError(error);
    }
  },

  async clearCache(cacheType: string = 'all'): Promise<CacheClearResponse> {
    try {
      const response = await apiClient.post<CacheClearResponse>(
        `/system/cache/clear?cache_type=${cacheType}`
      );
      return response.data;
    } catch (error) {
      handleAPIError(error);
    }
  },

  async getCacheStats(): Promise<CacheStatsResponse> {
    try {
      const response = await apiClient.get<CacheStatsResponse>('/system/cache/stats');
      return response.data;
    } catch (error) {
      handleAPIError(error);
    }
  },
};

// AI Reasoning API
export const reasoningApi = {
  async explain(request: ExplainRequest): Promise<ExplainResponse> {
    try {
      const response = await apiClient.post<ExplainResponse>('/reasoning/explain', request);
      return response.data;
    } catch (error) {
      handleAPIError(error);
    }
  },

  async remediate(request: RemediateRequest): Promise<RemediateResponse> {
    try {
      const response = await apiClient.post<RemediateResponse>('/reasoning/remediate', request);
      return response.data;
    } catch (error) {
      handleAPIError(error);
    }
  },

  async ask(request: AskRequest): Promise<AskResponse> {
    try {
      const response = await apiClient.post<AskResponse>('/reasoning/ask', request);
      return response.data;
    } catch (error) {
      handleAPIError(error);
    }
  },

  async getSummary(period: string = 'week', format: string = 'brief'): Promise<SummaryResponse> {
    try {
      const response = await apiClient.get<SummaryResponse>(
        `/reasoning/summary?period=${period}&format=${format}`
      );
      return response.data;
    } catch (error) {
      handleAPIError(error);
    }
  },

  async healthCheck(): Promise<ReasoningHealthResponse> {
    try {
      const response = await apiClient.get<ReasoningHealthResponse>('/reasoning/health');
      return response.data;
    } catch (error) {
      handleAPIError(error);
    }
  },
};
