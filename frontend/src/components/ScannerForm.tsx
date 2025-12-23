import { useState } from 'react';
import {
  PLATFORMS,
  HARDWARE_CHOICES_BY_PLATFORM,
  type Platform,
  type FeatureSnapshot,
  type DeviceCredentials
} from '../types';

interface ScannerFormProps {
  onScan: (platform: Platform, version: string, hardwareModel?: string | null, features?: string[], severityFilter?: number[]) => void;
  onExtractFeatures: (credentials: DeviceCredentials, platform?: string) => Promise<FeatureSnapshot>;
  loading: boolean;
}

type FeatureMode = 'none' | 'device' | 'snapshot';

export function ScannerForm({ onScan, onExtractFeatures, loading }: ScannerFormProps) {
  const [platform, setPlatform] = useState<Platform>('IOS-XE');
  const [version, setVersion] = useState('');
  const [hardwareModel, setHardwareModel] = useState<string | null>(null);
  const [featureMode, setFeatureMode] = useState<FeatureMode>('none');
  const [severityFilter, setSeverityFilter] = useState<number[]>([]);

  // Live Device state
  const [deviceHost, setDeviceHost] = useState('');
  const [deviceUsername, setDeviceUsername] = useState('');
  const [devicePassword, setDevicePassword] = useState('');
  const [extracting, setExtracting] = useState(false);
  const [extractedSnapshot, setExtractedSnapshot] = useState<FeatureSnapshot | null>(null);

  // Snapshot state
  const [snapshotJson, setSnapshotJson] = useState('');
  const [snapshotError, setSnapshotError] = useState<string | null>(null);
  const [parsedSnapshot, setParsedSnapshot] = useState<FeatureSnapshot | null>(null);

  const validateAndParseSnapshot = (jsonStr: string) => {
    setSnapshotError(null);
    setParsedSnapshot(null);

    if (!jsonStr.trim()) {
      return;
    }

    try {
      const parsed = JSON.parse(jsonStr);

      if (!parsed.snapshot_id) {
        setSnapshotError('Missing required field: snapshot_id');
        return;
      }
      if (!parsed.platform) {
        setSnapshotError('Missing required field: platform');
        return;
      }
      if (!Array.isArray(parsed.features_present)) {
        setSnapshotError('Missing or invalid field: features_present (must be array)');
        return;
      }

      setParsedSnapshot(parsed as FeatureSnapshot);
    } catch (err) {
      setSnapshotError('Invalid JSON format');
    }
  };

  const handleSnapshotChange = (value: string) => {
    setSnapshotJson(value);
    validateAndParseSnapshot(value);
  };

  const handleExtractFeatures = async () => {
    if (!deviceHost || !deviceUsername || !devicePassword) {
      return;
    }

    setExtracting(true);
    setExtractedSnapshot(null);

    try {
      const snapshot = await onExtractFeatures(
        {
          host: deviceHost,
          username: deviceUsername,
          password: devicePassword,
          device_type: 'cisco_ios',
        },
        platform
      );
      setExtractedSnapshot(snapshot);
      if (snapshot.version) {
        setVersion(snapshot.version);
      }
      if (snapshot.hardware_model) {
        setHardwareModel(snapshot.hardware_model);
      }
    } catch (error) {
      // Error handled by parent
    } finally {
      setExtracting(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    let features: string[] | undefined;

    if (featureMode === 'device' && extractedSnapshot) {
      features = extractedSnapshot.features_present;
    } else if (featureMode === 'snapshot' && parsedSnapshot) {
      features = parsedSnapshot.features_present;
    }

    const severity = severityFilter.length > 0 ? severityFilter : undefined;

    onScan(platform, version, hardwareModel, features, severity);
  };

  const toggleSeverity = (sev: number) => {
    setSeverityFilter(prev =>
      prev.includes(sev) ? prev.filter(s => s !== sev) : [...prev, sev]
    );
  };

  const resetFeatureMode = () => {
    setFeatureMode('none');
    setExtractedSnapshot(null);
    setParsedSnapshot(null);
    setSnapshotJson('');
    setSnapshotError(null);
    setDeviceHost('');
    setDeviceUsername('');
    setDevicePassword('');
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* Platform & Version */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            Platform *
          </label>
          <select
            value={platform}
            onChange={(e) => {
              const newPlatform = e.target.value as Platform;
              setPlatform(newPlatform);
              setHardwareModel(null); // Reset hardware when platform changes
            }}
            className="input"
            required
          >
            {PLATFORMS.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            Software Version *
          </label>
          <input
            type="text"
            value={version}
            onChange={(e) => setVersion(e.target.value)}
            placeholder="e.g., 17.10.1"
            className="input"
            required
          />
        </div>
      </div>

      {/* Hardware Model Selector */}
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
          Hardware Model (optional - NEW: 40-60% false positive reduction)
        </label>
        <select
          value={hardwareModel || ''}
          onChange={(e) => setHardwareModel(e.target.value === '' ? null : e.target.value)}
          className="input"
        >
          {HARDWARE_CHOICES_BY_PLATFORM[platform].map((choice) => (
            <option key={choice.value || 'null'} value={choice.value || ''}>
              {choice.label}
            </option>
          ))}
        </select>
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">
          Select your hardware platform to filter out bugs that don't apply to your specific device.
          {hardwareModel && (
            <span className="text-green-600 dark:text-green-400 font-semibold">
              {' '}✓ Hardware filtering enabled
            </span>
          )}
        </p>
      </div>

      {/* Feature Mode Selection */}
      {featureMode === 'none' && (
        <div className="border border-gray-300 dark:border-gray-600 rounded-lg p-6 bg-gray-50 dark:bg-gray-800">
          <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-4">
            Choose Scan Mode
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Version-Only */}
            <button
              type="button"
              onClick={() => setFeatureMode('none')}
              className="p-4 border-2 border-blue-500 dark:border-blue-400 bg-blue-50 dark:bg-blue-900/20 rounded-lg text-left"
            >
              <div className="text-lg font-semibold mb-2">📋 Version-Only</div>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                Scan without feature filtering
              </p>
              <ul className="mt-2 text-xs text-gray-500 dark:text-gray-300 space-y-1">
                <li>✓ Quick scan (1-2ms)</li>
                <li>⚠️  May include false positives</li>
              </ul>
            </button>

            {/* Live Device */}
            <button
              type="button"
              onClick={() => setFeatureMode('device')}
              className="p-4 border-2 border-gray-300 dark:border-gray-600 rounded-lg hover:border-blue-500 dark:hover:border-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-colors text-left"
            >
              <div className="text-lg font-semibold mb-2">🔌 Live Device</div>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                Extract features via SSH
              </p>
              <ul className="mt-2 text-xs text-gray-500 dark:text-gray-300 space-y-1">
                <li>✓ 40-80% fewer false positives</li>
                <li>⚠️  Requires SSH access</li>
              </ul>
            </button>

            {/* JSON Snapshot */}
            <button
              type="button"
              onClick={() => setFeatureMode('snapshot')}
              className="p-4 border-2 border-gray-300 dark:border-gray-600 rounded-lg hover:border-green-500 dark:hover:border-green-400 hover:bg-green-50 dark:hover:bg-green-900/20 transition-colors text-left"
            >
              <div className="text-lg font-semibold mb-2">📦 JSON Snapshot</div>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                Use pre-extracted features
              </p>
              <ul className="mt-2 text-xs text-gray-500 dark:text-gray-300 space-y-1">
                <li>✓ 40-80% fewer false positives</li>
                <li>✓ Works offline/air-gapped</li>
              </ul>
            </button>
          </div>
        </div>
      )}

      {/* Live Device Mode */}
      {featureMode === 'device' && !extractedSnapshot && (
        <div className="border border-gray-300 dark:border-gray-600 rounded-lg p-4 bg-gray-50 dark:bg-gray-800">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-gray-900 dark:text-gray-100">
              🔌 Live Device Feature Extraction
            </h3>
            <button
              type="button"
              onClick={resetFeatureMode}
              className="text-sm text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
            >
              ← Back to mode selection
            </button>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Device IP/Hostname *
              </label>
              <input
                type="text"
                value={deviceHost}
                onChange={(e) => setDeviceHost(e.target.value)}
                placeholder="192.168.1.1"
                className="input"
                required={featureMode === 'device'}
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Username *
                </label>
                <input
                  type="text"
                  value={deviceUsername}
                  onChange={(e) => setDeviceUsername(e.target.value)}
                  placeholder="admin"
                  className="input"
                  required={featureMode === 'device'}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Password *
                </label>
                <input
                  type="password"
                  value={devicePassword}
                  onChange={(e) => setDevicePassword(e.target.value)}
                  className="input"
                  required={featureMode === 'device'}
                />
              </div>
            </div>

            <button
              type="button"
              onClick={handleExtractFeatures}
              disabled={extracting || !deviceHost || !deviceUsername || !devicePassword}
              className="btn btn-primary w-full"
            >
              {extracting ? (
                <>
                  <span className="inline-block animate-spin mr-2">⏳</span>
                  Extracting Features...
                </>
              ) : (
                '🔍 Extract Features from Device'
              )}
            </button>
          </div>
        </div>
      )}

      {/* Extracted Features Display */}
      {featureMode === 'device' && extractedSnapshot && (
        <div className="border border-green-300 dark:border-green-700 rounded-lg p-4 bg-green-50 dark:bg-green-900/20">
          <div className="flex items-start justify-between mb-3">
            <div className="flex items-center gap-2">
              <span className="text-green-600 dark:text-green-400">✓</span>
              <h3 className="font-semibold text-green-900 dark:text-green-200">
                Features Extracted Successfully
              </h3>
            </div>
            <button
              type="button"
              onClick={resetFeatureMode}
              className="text-sm text-green-700 dark:text-green-300 hover:underline"
            >
              Change mode
            </button>
          </div>
          <div className="text-sm text-green-800 dark:text-green-300 space-y-1">
            <div>Platform: {extractedSnapshot.platform}</div>
            <div>Features: {extractedSnapshot.feature_count} detected</div>
            <div>Snapshot ID: {extractedSnapshot.snapshot_id}</div>
          </div>
        </div>
      )}

      {/* JSON Snapshot Mode */}
      {featureMode === 'snapshot' && (
        <div className="border border-gray-300 dark:border-gray-600 rounded-lg p-4 bg-gray-50 dark:bg-gray-800">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-gray-900 dark:text-gray-100">
              📦 JSON Snapshot
            </h3>
            <button
              type="button"
              onClick={resetFeatureMode}
              className="text-sm text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
            >
              ← Back to mode selection
            </button>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Feature Snapshot JSON
            </label>
            <textarea
              value={snapshotJson}
              onChange={(e) => handleSnapshotChange(e.target.value)}
              placeholder={`{\n  "snapshot_id": "snapshot-20251009-140153",\n  "platform": "IOS-XE",\n  "features_present": ["MGMT_SSH_HTTP", "SEC_CoPP"],\n  ...\n}`}
              rows={8}
              className={`input font-mono text-sm ${snapshotError ? 'border-red-500 dark:border-red-400' : ''
                }`}
            />

            {snapshotJson && (
              <div className="mt-2">
                {snapshotError ? (
                  <div className="text-sm text-red-600 dark:text-red-400 flex items-center gap-2">
                    <span>❌</span>
                    <span>{snapshotError}</span>
                  </div>
                ) : parsedSnapshot ? (
                  <div className="text-sm text-green-600 dark:text-green-400 flex items-start gap-2">
                    <span>✓</span>
                    <div>
                      <div className="font-semibold">Valid snapshot detected</div>
                      <div className="text-xs mt-1">
                        Platform: {parsedSnapshot.platform} |
                        Features: {parsedSnapshot.features_present.length} |
                        ID: {parsedSnapshot.snapshot_id}
                      </div>
                    </div>
                  </div>
                ) : null}
              </div>
            )}

            <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">
              Paste JSON from <code className="bg-gray-200 dark:bg-gray-700 px-1 rounded">extract_iosxe_features_standalone.py</code>
            </p>
          </div>
        </div>
      )}

      {/* Severity Filter */}
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
          Severity Filter (optional)
        </label>
        <div className="flex flex-wrap gap-2">
          {[
            { value: 1, label: 'Critical (1)', color: 'bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-200 border-red-300 dark:border-red-700' },
            { value: 2, label: 'High (2)', color: 'bg-orange-100 dark:bg-orange-900 text-orange-800 dark:text-orange-200 border-orange-300 dark:border-orange-700' },
            { value: 3, label: 'Medium (3)', color: 'bg-yellow-100 dark:bg-yellow-900 text-yellow-800 dark:text-yellow-200 border-yellow-300 dark:border-yellow-700' },
            { value: 4, label: 'Low (4+)', color: 'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-200 border-gray-300 dark:border-gray-600' },
          ].map(({ value, label, color }) => (
            <button
              key={value}
              type="button"
              onClick={() => toggleSeverity(value)}
              className={`px-3 py-1 text-sm rounded-md border-2 transition-all ${severityFilter.includes(value)
                ? `${color} ring-2 ring-offset-1 ring-blue-500`
                : 'bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 border-gray-300 dark:border-gray-600 hover:border-blue-400'
                }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Submit Button */}
      <button
        type="submit"
        disabled={loading || !version.trim()}
        className="btn btn-primary w-full"
      >
        {loading ? (
          <>
            <span className="inline-block animate-spin mr-2">⏳</span>
            Scanning Database...
          </>
        ) : (
          '🔍 Scan for Known Defects'
        )}
      </button>

      {/* Info Box */}
      <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4 text-sm">
        <p className="font-semibold text-blue-900 dark:text-blue-200 mb-2">Database Scan:</p>
        <ul className="text-blue-800 dark:text-blue-300 space-y-1 text-xs">
          <li>• <strong>Version-only:</strong> Returns all bugs for this version (fast but may have false positives)</li>
          <li>• <strong>Feature-aware:</strong> Filters by configured features (40-80% fewer false positives)</li>
          <li>• <strong>Speed:</strong> 1-2ms typical scan (729 Cat9K bugs in database)</li>
        </ul>
      </div>
    </form>
  );
}
