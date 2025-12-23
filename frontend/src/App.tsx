import { useState } from 'react';
import { QueryClient, QueryClientProvider, useMutation } from '@tanstack/react-query';
import { api } from './api/client';
import { ThemeProvider } from './context/ThemeContext';
import { ThemeToggle } from './components/ThemeToggle';
import { AnalyzeForm } from './components/AnalyzeForm';
import { ResultsDisplay } from './components/ResultsDisplay';
import { DeviceForm } from './components/DeviceForm';
import { SnapshotForm } from './components/SnapshotForm';
import { VerificationReport } from './components/VerificationReport';
import { ScannerForm } from './components/ScannerForm';
import { ScanResults } from './components/ScanResults';
import { InventoryManager } from './components/InventoryManager';
import { SystemAdmin } from './components/SystemAdmin';
import { AIAssistant } from './components/AIAssistant';
import type {
  Platform,
  AnalysisResult,
  VerificationResult,
  DeviceCredentials,
  PSIRTMetadata,
  FeatureSnapshot,
  ScanResult,
} from './types';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

type VerificationMode = 'device' | 'snapshot';
type ActiveTab = 'psirt' | 'scanner' | 'inventory' | 'assistant' | 'system';

function AppContent() {
  // Tab state
  const [activeTab, setActiveTab] = useState<ActiveTab>('psirt');

  // PSIRT Analysis state
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null);
  const [verificationResult, setVerificationResult] = useState<VerificationResult | null>(null);
  const [verificationMode, setVerificationMode] = useState<VerificationMode | null>(null);

  // Vulnerability Scanner state
  const [scanResult, setScanResult] = useState<ScanResult | null>(null);

  // Error state
  const [error, setError] = useState<string | null>(null);

  // Analysis mutation
  const analyzeMutation = useMutation({
    mutationFn: (data: { summary: string; platform: Platform; advisoryId?: string }) =>
      api.analyzePSIRT({
        summary: data.summary,
        platform: data.platform,
        advisory_id: data.advisoryId,
      }),
    onSuccess: (data) => {
      setAnalysisResult(data);
      setVerificationResult(null);
      setVerificationMode(null);
      setError(null);
    },
    onError: (err: Error) => {
      setError(err.message);
    },
  });

  // Device verification mutation
  const verifyDeviceMutation = useMutation({
    mutationFn: (data: { credentials: DeviceCredentials; metadata: PSIRTMetadata }) => {
      if (!analysisResult) throw new Error('No analysis result available');
      return api.verifyDevice({
        analysis_id: analysisResult.analysis_id,
        device: data.credentials,
        psirt_metadata: data.metadata,
      });
    },
    onSuccess: (data) => {
      setVerificationResult(data);
      setError(null);
    },
    onError: (err: Error) => {
      setError(err.message);
    },
  });

  // Snapshot verification mutation
  const verifySnapshotMutation = useMutation({
    mutationFn: (snapshot: FeatureSnapshot) => {
      if (!analysisResult) throw new Error('No analysis result available');
      return api.verifySnapshot({
        analysis_id: analysisResult.analysis_id,
        snapshot,
      });
    },
    onSuccess: (data) => {
      setVerificationResult(data);
      setError(null);
    },
    onError: (err: Error) => {
      setError(err.message);
    },
  });

  // Scanner mutation
  const scanMutation = useMutation({
    mutationFn: (data: {
      platform: Platform;
      version: string;
      hardwareModel?: string | null;
      features?: string[];
      severityFilter?: number[];
    }) =>
      api.scanDevice({
        platform: data.platform,
        version: data.version,
        hardware_model: data.hardwareModel,
        features: data.features,
        severity_filter: data.severityFilter,
      }),
    onSuccess: (data) => {
      setScanResult(data);
      setError(null);
    },
    onError: (err: Error) => {
      setError(err.message);
    },
  });

  // Feature extraction mutation
  const extractFeaturesMutation = useMutation({
    mutationFn: (data: { credentials: DeviceCredentials; platform?: string }) =>
      api.extractFeatures(data.credentials, data.platform),
  });

  const handleAnalyze = (summary: string, platform: Platform, advisoryId?: string) => {
    analyzeMutation.mutate({ summary, platform, advisoryId });
  };

  const handleVerifyDevice = (credentials: DeviceCredentials, metadata: PSIRTMetadata) => {
    verifyDeviceMutation.mutate({ credentials, metadata });
  };

  const handleVerifySnapshot = (snapshot: FeatureSnapshot) => {
    verifySnapshotMutation.mutate(snapshot);
  };

  const handleScan = (
    platform: Platform,
    version: string,
    hardwareModel?: string | null,
    features?: string[],
    severityFilter?: number[]
  ) => {
    scanMutation.mutate({ platform, version, hardwareModel, features, severityFilter });
  };

  const handleExtractFeatures = async (
    credentials: DeviceCredentials,
    platform?: string
  ): Promise<FeatureSnapshot> => {
    return extractFeaturesMutation.mutateAsync({ credentials, platform });
  };

  const handleExport = (format: 'json') => {
    if (!verificationResult) return;

    if (format === 'json') {
      const dataStr = JSON.stringify(verificationResult, null, 2);
      const dataBlob = new Blob([dataStr], { type: 'application/json' });
      const url = URL.createObjectURL(dataBlob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `verification_${verificationResult.verification_id}.json`;
      link.click();
      URL.revokeObjectURL(url);
    }
  };

  const handleNewAnalysis = () => {
    setAnalysisResult(null);
    setVerificationResult(null);
    setVerificationMode(null);
    setError(null);
  };

  const handleNewScan = () => {
    setScanResult(null);
    setError(null);
  };

  const handleTabChange = (tab: ActiveTab) => {
    setActiveTab(tab);
    setError(null);
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950">
      {/* Header */}
      <header className="bg-gradient-to-r from-blue-700 via-indigo-700 to-violet-800 dark:from-slate-900 dark:via-blue-950 dark:to-slate-900 text-white shadow-lg border-b border-white/10">
        <div className="container mx-auto px-4 py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold tracking-tight text-white drop-shadow-sm">Security Analyzer</h1>
              <p className="text-blue-100 dark:text-blue-200 mt-1 font-medium opacity-90">
                Cisco PSIRT & Bug Analysis • Feature-Aware Scanning
              </p>
            </div>
            <ThemeToggle />
          </div>
        </div>
      </header>

      {/* Tab Navigation */}
      <div className="bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 sticky top-0 z-10 backdrop-blur-sm bg-white/90 dark:bg-slate-900/90 supports-[backdrop-filter]:bg-white/60">
        <div className={`container mx-auto px-4 ${['inventory', 'system', 'assistant'].includes(activeTab) ? 'max-w-7xl' : 'max-w-4xl'}`}>
          <nav className="flex gap-2">
            <button
              onClick={() => handleTabChange('psirt')}
              className={`px-6 py-4 font-semibold transition-colors border-b-2 ${activeTab === 'psirt'
                ? 'border-blue-600 text-blue-600 dark:text-blue-400'
                : 'border-transparent text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
                }`}
            >
              🔍 Security Analysis
            </button>
            <button
              onClick={() => handleTabChange('scanner')}
              className={`px-6 py-4 font-semibold transition-colors border-b-2 ${activeTab === 'scanner'
                ? 'border-blue-600 text-blue-600 dark:text-blue-400'
                : 'border-transparent text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
                }`}
            >
              🗄️ Defect Scanner
            </button>
            <button
              onClick={() => handleTabChange('inventory')}
              className={`px-6 py-4 font-semibold transition-colors border-b-2 ${activeTab === 'inventory'
                ? 'border-blue-600 text-blue-600 dark:text-blue-400'
                : 'border-transparent text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
                }`}
            >
              📦 Device Inventory
            </button>
            <button
              onClick={() => handleTabChange('assistant')}
              className={`px-6 py-4 font-semibold transition-colors border-b-2 ${activeTab === 'assistant'
                ? 'border-blue-600 text-blue-600 dark:text-blue-400'
                : 'border-transparent text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
                }`}
            >
              🤖 AI Assistant
            </button>
            <button
              onClick={() => handleTabChange('system')}
              className={`px-6 py-4 font-semibold transition-colors border-b-2 ${activeTab === 'system'
                ? 'border-blue-600 text-blue-600 dark:text-blue-400'
                : 'border-transparent text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
                }`}
            >
              ⚙️ System
            </button>
          </nav>
        </div>
      </div>

      {/* Main Content */}
      <main className={`container mx-auto px-4 py-8 ${['inventory', 'system', 'assistant'].includes(activeTab) ? 'max-w-7xl' : 'max-w-4xl'}`}>
        {/* Error Alert */}
        {error && (
          <div className="alert alert-error mb-6">
            <p className="font-semibold">Error:</p>
            <p>{error}</p>
            <button
              onClick={() => setError(null)}
              className="text-sm underline hover:no-underline"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* PSIRT Analysis Tab */}
        {activeTab === 'psirt' && (
          <>
            {/* Step 1: Analyze PSIRT */}
            <div className="card">
              <div className="flex items-center justify-between mb-4">
                <h2 className="card-header mb-0">Step 1: Analyze PSIRT or Bug</h2>
                {analysisResult && (
                  <button
                    onClick={handleNewAnalysis}
                    className="btn btn-secondary text-sm"
                  >
                    New Analysis
                  </button>
                )}
              </div>
              {!analysisResult ? (
                <AnalyzeForm onAnalyze={handleAnalyze} loading={analyzeMutation.isPending} />
              ) : (
                <div className="text-sm text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-900/20 p-3 rounded-md">
                  ✓ Analysis complete
                </div>
              )}
            </div>

            {/* Step 2: Analysis Results */}
            {analysisResult && (
              <div className="card">
                <h2 className="card-header">Step 2: Analysis Results</h2>
                <ResultsDisplay
                  analysis={analysisResult}
                  onVerifyDevice={() => setVerificationMode('device')}
                />
              </div>
            )}

            {/* Step 3: Choose Verification Method */}
            {analysisResult && !verificationMode && !verificationResult && (
              <div className="card">
                <h2 className="card-header">Step 3: Choose Verification Method</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Live Device Option */}
                  <button
                    onClick={() => setVerificationMode('device')}
                    className="p-6 border-2 border-gray-300 dark:border-gray-600 rounded-lg hover:border-blue-500 dark:hover:border-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-colors text-left"
                  >
                    <div className="text-lg font-semibold mb-2">🔌 Live Device (SSH)</div>
                    <p className="text-sm text-gray-600 dark:text-gray-400">
                      Connect to device via SSH and verify in real-time
                    </p>
                    <ul className="mt-3 text-xs text-gray-500 dark:text-gray-300 space-y-1">
                      <li>✓ Complete verification (version + features)</li>
                      <li>✓ Collects evidence from device</li>
                      <li>⚠️  Requires network access</li>
                    </ul>
                  </button>

                  {/* Snapshot Option */}
                  <button
                    onClick={() => setVerificationMode('snapshot')}
                    className="p-6 border-2 border-gray-300 dark:border-gray-600 rounded-lg hover:border-green-500 dark:hover:border-green-400 hover:bg-green-50 dark:hover:bg-green-900/20 transition-colors text-left"
                  >
                    <div className="text-lg font-semibold mb-2">📦 Pre-extracted Snapshot</div>
                    <p className="text-sm text-gray-600 dark:text-gray-400">
                      Verify using feature snapshot (air-gapped mode)
                    </p>
                    <ul className="mt-3 text-xs text-gray-500 dark:text-gray-300 space-y-1">
                      <li>✓ Works offline / air-gapped</li>
                      <li>✓ No SSH required</li>
                      <li>⚠️  Feature-only check (no version)</li>
                    </ul>
                  </button>
                </div>
              </div>
            )}

            {/* Step 3: Device Verification Form */}
            {verificationMode === 'device' && analysisResult && !verificationResult && (
              <div className="card">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="card-header mb-0">Step 3: Live Device Verification</h2>
                  <button
                    onClick={() => setVerificationMode(null)}
                    className="text-sm text-gray-500 hover:text-gray-700 dark:text-gray-300 dark:hover:text-gray-100"
                  >
                    ← Back to method selection
                  </button>
                </div>
                <DeviceForm
                  onVerify={handleVerifyDevice}
                  loading={verifyDeviceMutation.isPending}
                />
              </div>
            )}

            {/* Step 3: Snapshot Verification Form */}
            {verificationMode === 'snapshot' && analysisResult && !verificationResult && (
              <div className="card">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="card-header mb-0">Step 3: Snapshot Verification</h2>
                  <button
                    onClick={() => setVerificationMode(null)}
                    className="text-sm text-gray-500 hover:text-gray-700 dark:text-gray-300 dark:hover:text-gray-100"
                  >
                    ← Back to method selection
                  </button>
                </div>
                <SnapshotForm
                  onVerify={handleVerifySnapshot}
                  loading={verifySnapshotMutation.isPending}
                />
              </div>
            )}

            {/* Step 4: Verification Report */}
            {verificationResult && (
              <div className="card">
                <h2 className="card-header">Step 4: Verification Report</h2>
                <VerificationReport result={verificationResult} onExport={handleExport} />
              </div>
            )}
          </>
        )}

        {/* Vulnerability Scanner Tab */}
        {activeTab === 'scanner' && (
          <>
            {/* Scanner Form */}
            <div className="card">
              <h2 className="card-header">Known Defect Database Scanner</h2>
              <ScannerForm
                onScan={handleScan}
                onExtractFeatures={handleExtractFeatures}
                loading={scanMutation.isPending}
              />
            </div>

            {/* Scan Results */}
            {scanResult && (
              <div className="card">
                <ScanResults result={scanResult} onNewScan={handleNewScan} />
              </div>
            )}
          </>
        )}

        {/* Device Inventory Tab */}
        {activeTab === 'inventory' && (
          <InventoryManager />
        )}

        {/* AI Assistant Tab */}
        {activeTab === 'assistant' && (
          <AIAssistant />
        )}

        {/* System Admin Tab */}
        {activeTab === 'system' && (
          <SystemAdmin />
        )}
      </main>

      {/* Footer */}
      <footer className="bg-slate-900 dark:bg-slate-950 text-slate-400 dark:text-slate-500 py-8 mt-12 border-t border-slate-200/10 dark:border-slate-800">
        <div className="container mx-auto px-4 text-center text-sm font-medium">
          <p>Security Analyzer • Foundation-Sec-8B • Local Inference • 9,600+ Known Bugs</p>
        </div>
      </footer>
    </div>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <AppContent />
      </ThemeProvider>
    </QueryClientProvider>
  );
}

export default App;
