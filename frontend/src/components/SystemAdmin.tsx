import { useState, useCallback } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { systemApi } from '../api/client';
import type { UpdateResponse } from '../types/system';

export function SystemAdmin() {
  const [dragActive, setDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadResult, setUploadResult] = useState<UpdateResponse | null>(null);
  const [statsMode, setStatsMode] = useState<'bugs' | 'psirts'>('bugs');

  // Fetch database stats
  const { data: dbStats, isLoading: statsLoading, error: statsError, refetch: refetchStats } = useQuery({
    queryKey: ['dbStats'],
    queryFn: systemApi.getDatabaseStats,
    refetchInterval: 30000, // Refresh every 30s
  });

  // Fetch system health
  const { data: health, isLoading: healthLoading, error: healthError, refetch: refetchHealth } = useQuery({
    queryKey: ['systemHealth'],
    queryFn: systemApi.getSystemHealth,
    refetchInterval: 30000,
  });

  // Fetch cache stats
  const { data: cacheStats, refetch: refetchCache } = useQuery({
    queryKey: ['cacheStats'],
    queryFn: systemApi.getCacheStats,
  });

  // Upload mutation
  const uploadMutation = useMutation({
    mutationFn: (file: File) => systemApi.uploadOfflinePackage(file),
    onSuccess: (data) => {
      setUploadResult(data);
      setSelectedFile(null);
      // Refresh stats after successful upload
      refetchStats();
    },
    onError: (error: Error) => {
      setUploadResult({
        success: false,
        error_message: error.message,
        inserted: 0,
        updated: 0,
        skipped: 0,
        errors: 0,
        total_processed: 0,
        package_name: selectedFile?.name || '',
        hash_verified: false,
        timestamp: new Date().toISOString(),
      });
    },
  });

  // Cache clear mutation
  const clearCacheMutation = useMutation({
    mutationFn: (cacheType: string) => systemApi.clearCache(cacheType),
    onSuccess: () => {
      refetchCache();
    },
  });

  // Drag and drop handlers
  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      if (file.name.endsWith('.zip')) {
        setSelectedFile(file);
        setUploadResult(null);
      }
    }
  }, []);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
      setUploadResult(null);
    }
  };

  const handleUpload = () => {
    if (selectedFile) {
      uploadMutation.mutate(selectedFile);
    }
  };

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'healthy':
        return 'text-green-600 dark:text-green-400';
      case 'degraded':
        return 'text-yellow-600 dark:text-yellow-400';
      case 'error':
      case 'missing':
        return 'text-red-600 dark:text-red-400';
      default:
        return 'text-gray-600 dark:text-gray-400';
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">System Administration</h1>
          <p className="text-gray-600 dark:text-gray-400 mt-1">
            Manage offline updates, monitor system health, and control caches
          </p>
        </div>
        <button
          onClick={() => {
            refetchStats();
            refetchHealth();
            refetchCache();
          }}
          className="btn btn-secondary flex items-center gap-2"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          Refresh All
        </button>
      </div>

      {/* Grid Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Offline Update Card */}
        <div className="card">
          <h2 className="card-header flex items-center gap-2">
            <span className="text-xl">📦</span> Offline Update
          </h2>

          {/* Drop Zone */}
          <div
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            className={`
              border-2 border-dashed rounded-lg p-8 text-center transition-colors
              ${dragActive
                ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                : 'border-gray-300 dark:border-gray-600 hover:border-gray-400 dark:hover:border-gray-500'
              }
            `}
          >
            <div className="space-y-4">
              <div className="text-4xl">📁</div>
              <div className="text-gray-600 dark:text-gray-400">
                <p className="font-medium">Drag & drop a .zip update package</p>
                <p className="text-sm">or click to browse</p>
              </div>
              <input
                type="file"
                accept=".zip"
                onChange={handleFileSelect}
                className="hidden"
                id="file-upload"
              />
              <label
                htmlFor="file-upload"
                className="btn btn-secondary cursor-pointer inline-block"
              >
                Select File
              </label>
            </div>
          </div>

          {/* Selected File */}
          {selectedFile && (
            <div className="mt-4 p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="text-2xl">📄</span>
                  <div>
                    <p className="font-medium text-gray-900 dark:text-white">{selectedFile.name}</p>
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                      {formatBytes(selectedFile.size)}
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => setSelectedFile(null)}
                  className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
              <button
                onClick={handleUpload}
                disabled={uploadMutation.isPending}
                className="btn btn-primary w-full mt-4"
              >
                {uploadMutation.isPending ? (
                  <span className="flex items-center justify-center gap-2">
                    <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    Uploading & Applying...
                  </span>
                ) : (
                  'Upload & Apply Update'
                )}
              </button>
            </div>
          )}

          {/* Upload Result */}
          {uploadResult && (
            <div className={`mt-4 p-4 rounded-lg ${
              uploadResult.success
                ? 'bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800'
                : 'bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800'
            }`}>
              <div className="flex items-start gap-3">
                <span className="text-2xl">{uploadResult.success ? '✅' : '❌'}</span>
                <div className="flex-1">
                  <p className={`font-medium ${
                    uploadResult.success ? 'text-green-800 dark:text-green-200' : 'text-red-800 dark:text-red-200'
                  }`}>
                    {uploadResult.success ? 'Update Applied Successfully' : 'Update Failed'}
                  </p>
                  {uploadResult.success ? (
                    <div className="mt-2 text-sm text-green-700 dark:text-green-300 space-y-1">
                      <p>📥 Inserted: {uploadResult.inserted} new records</p>
                      <p>🔄 Updated: {uploadResult.updated} existing records</p>
                      <p>⏭️ Skipped: {uploadResult.skipped} records</p>
                      {uploadResult.hash_verified && <p>🔐 Hash verified</p>}
                    </div>
                  ) : (
                    <p className="mt-1 text-sm text-red-700 dark:text-red-300">
                      {uploadResult.error_message}
                    </p>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Database Stats Card */}
        <div className="card">
          <div className="card-header flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-xl">🗄️</span> Database Statistics
            </div>
            <div className="flex items-center gap-2">
              <button
                className={`px-3 py-1 rounded text-sm transition-colors ${
                  statsMode === 'bugs'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-600 text-gray-300 hover:bg-gray-500'
                }`}
                onClick={() => setStatsMode('bugs')}
              >
                Bugs
              </button>
              <button
                className={`px-3 py-1 rounded text-sm transition-colors ${
                  statsMode === 'psirts'
                    ? 'bg-purple-600 text-white'
                    : 'bg-gray-600 text-gray-300 hover:bg-gray-500'
                }`}
                onClick={() => setStatsMode('psirts')}
              >
                PSIRTs
              </button>
            </div>
          </div>

          {statsLoading ? (
            <div className="flex items-center justify-center py-8">
              <svg className="animate-spin h-8 w-8 text-blue-500" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
            </div>
          ) : statsError ? (
            <div className="text-red-600 dark:text-red-400 py-4">
              Failed to load statistics
            </div>
          ) : dbStats && (
            <div className="space-y-4">
              {/* Total Count */}
              <div className="flex justify-between items-center py-2 border-b border-gray-200 dark:border-gray-700">
                <span className="text-gray-600 dark:text-gray-400">
                  Total {statsMode === 'bugs' ? 'Bugs' : 'PSIRTs'}
                </span>
                <span className="text-2xl font-bold text-gray-900 dark:text-white">
                  {statsMode === 'bugs'
                    ? (dbStats.bugs?.total || 0).toLocaleString()
                    : (dbStats.psirts?.total || 0).toLocaleString()}
                </span>
              </div>

              {/* By Platform */}
              <div>
                <p className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-2">By Platform</p>
                <div className="grid grid-cols-2 gap-2">
                  {Object.entries(
                    statsMode === 'bugs'
                      ? dbStats.bugs?.by_platform || {}
                      : dbStats.psirts?.by_platform || {}
                  ).map(([platform, count]) => (
                    <div key={platform} className="flex justify-between items-center bg-gray-50 dark:bg-gray-800 px-3 py-2 rounded">
                      <span className="text-sm text-gray-700 dark:text-gray-300">{platform}</span>
                      <span className="font-medium text-gray-900 dark:text-white">{count.toLocaleString()}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Labeled vs Unlabeled */}
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-green-50 dark:bg-green-900/20 px-4 py-3 rounded-lg">
                  <p className="text-sm text-green-600 dark:text-green-400">Labeled</p>
                  <p className="text-xl font-bold text-green-700 dark:text-green-300">
                    {statsMode === 'bugs'
                      ? (dbStats.bugs?.labeled_count || 0).toLocaleString()
                      : (dbStats.psirts?.labeled_count || 0).toLocaleString()}
                  </p>
                </div>
                <div className="bg-yellow-50 dark:bg-yellow-900/20 px-4 py-3 rounded-lg">
                  <p className="text-sm text-yellow-600 dark:text-yellow-400">Unlabeled</p>
                  <p className="text-xl font-bold text-yellow-700 dark:text-yellow-300">
                    {statsMode === 'bugs'
                      ? (dbStats.bugs?.unlabeled_count || 0).toLocaleString()
                      : (dbStats.psirts?.unlabeled_count || 0).toLocaleString()}
                  </p>
                </div>
              </div>

              {/* DB Size */}
              <div className="flex justify-between items-center text-sm">
                <span className="text-gray-500 dark:text-gray-400">Database Size</span>
                <span className="text-gray-700 dark:text-gray-300">{dbStats.db_size_mb} MB</span>
              </div>

              {/* Last Import */}
              {dbStats.last_import && (
                <div className="text-xs text-gray-500 dark:text-gray-400 pt-2 border-t border-gray-200 dark:border-gray-700">
                  Last import: {new Date(dbStats.last_import.timestamp).toLocaleString()}
                </div>
              )}
            </div>
          )}
        </div>

        {/* System Health Card */}
        <div className="card">
          <h2 className="card-header flex items-center gap-2">
            <span className="text-xl">💚</span> System Health
          </h2>

          {healthLoading ? (
            <div className="flex items-center justify-center py-8">
              <svg className="animate-spin h-8 w-8 text-blue-500" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
            </div>
          ) : healthError ? (
            <div className="text-red-600 dark:text-red-400 py-4">
              Failed to load health status
            </div>
          ) : health && (
            <div className="space-y-4">
              {/* Overall Status */}
              <div className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
                <span className="font-medium text-gray-700 dark:text-gray-300">Overall Status</span>
                <span className={`font-bold uppercase ${getStatusColor(health.status)}`}>
                  {health.status === 'healthy' ? '● HEALTHY' : health.status === 'degraded' ? '○ DEGRADED' : '✕ ERROR'}
                </span>
              </div>

              {/* Component Status */}
              <div className="space-y-2">
                {/* Database */}
                <div className="flex items-center justify-between py-2">
                  <div className="flex items-center gap-2">
                    <span>🗄️</span>
                    <span className="text-gray-700 dark:text-gray-300">Database</span>
                  </div>
                  <span className={getStatusColor(health.database?.status || 'unknown')}>
                    {health.database?.status}
                  </span>
                </div>

                {/* Model */}
                <div className="flex items-center justify-between py-2">
                  <div className="flex items-center gap-2">
                    <span>🤖</span>
                    <span className="text-gray-700 dark:text-gray-300">ML Model</span>
                  </div>
                  <span className={getStatusColor(health.model?.status || 'unknown')}>
                    {health.model?.status}
                  </span>
                </div>

                {/* Model Details */}
                {health.model && (
                  <div className="ml-8 text-sm text-gray-500 dark:text-gray-400 space-y-1">
                    <p>Platform: {health.model.device_info || health.model.platform || 'Unknown'}</p>
                    <p>Backend: {health.model.backend || 'Unknown'}</p>
                    <p>Adapter: {health.model.adapter_exists ? `✓ (${health.model.adapter_path})` : '✕ Missing'}</p>
                    <p>FAISS Index: {health.model.faiss_index ? `✓ (${health.model.faiss_size_mb} MB)` : '✕'}</p>
                    {health.model.embedder_config !== undefined && (
                      <p>Embedder Config: {health.model.embedder_config ? '✓' : '✕'}</p>
                    )}
                  </div>
                )}

                {/* Cache */}
                <div className="flex items-center justify-between py-2">
                  <div className="flex items-center gap-2">
                    <span>💾</span>
                    <span className="text-gray-700 dark:text-gray-300">Cache</span>
                  </div>
                  <span className={getStatusColor(health.cache?.status || 'unknown')}>
                    {health.cache?.status}
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Cache Management Card */}
        <div className="card">
          <h2 className="card-header flex items-center gap-2">
            <span className="text-xl">🧹</span> Cache Management
          </h2>

          <div className="space-y-4">
            {/* PSIRT Cache */}
            <div className="flex items-center justify-between p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
              <div>
                <p className="font-medium text-gray-900 dark:text-white">PSIRT Cache</p>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  {cacheStats?.cache_stats?.psirt_cache?.entries || 0} cached entries
                </p>
              </div>
              <button
                onClick={() => clearCacheMutation.mutate('psirt')}
                disabled={clearCacheMutation.isPending}
                className="btn btn-secondary text-sm"
              >
                {clearCacheMutation.isPending ? 'Clearing...' : 'Clear'}
              </button>
            </div>

            {/* Clear All */}
            <button
              onClick={() => clearCacheMutation.mutate('all')}
              disabled={clearCacheMutation.isPending}
              className="btn btn-secondary w-full"
            >
              Clear All Caches
            </button>

            {clearCacheMutation.isSuccess && (
              <p className="text-sm text-green-600 dark:text-green-400 text-center">
                ✓ Cache cleared successfully
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
