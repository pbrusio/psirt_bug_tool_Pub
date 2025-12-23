import { useState } from 'react';
import type { FeatureSnapshot } from '../types';

interface SnapshotFormProps {
  onVerify: (snapshot: FeatureSnapshot) => void;
  loading: boolean;
}

export function SnapshotForm({ onVerify, loading }: SnapshotFormProps) {
  const [snapshotText, setSnapshotText] = useState('');
  const [parseError, setParseError] = useState<string | null>(null);
  const [parsedSnapshot, setParsedSnapshot] = useState<FeatureSnapshot | null>(null);

  const handleParse = () => {
    setParseError(null);
    setParsedSnapshot(null);

    try {
      const parsed = JSON.parse(snapshotText);

      // Validate snapshot structure
      const requiredFields = [
        'snapshot_id',
        'platform',
        'extracted_at',
        'features_present',
        'feature_count',
        'total_checked',
        'extractor_version',
      ];

      for (const field of requiredFields) {
        if (!(field in parsed)) {
          throw new Error(`Missing required field: ${field}`);
        }
      }

      if (!Array.isArray(parsed.features_present)) {
        throw new Error('features_present must be an array');
      }

      setParsedSnapshot(parsed as FeatureSnapshot);
    } catch (err) {
      setParseError(err instanceof Error ? err.message : 'Invalid JSON');
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (parsedSnapshot) {
      onVerify(parsedSnapshot);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label htmlFor="snapshot" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
          Feature Snapshot JSON
        </label>
        <textarea
          id="snapshot"
          value={snapshotText}
          onChange={(e) => setSnapshotText(e.target.value)}
          placeholder={'Paste feature snapshot JSON here...\n\nExample:\n{\n  "snapshot_id": "snapshot-20251009-140153",\n  "platform": "IOS-XE",\n  "features_present": ["MGMT_SSH_HTTP", "SEC_CoPP"],\n  ...\n}'}
          className="w-full h-64 px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent dark:bg-gray-700 dark:text-gray-100 font-mono"
          disabled={loading}
          required
        />
        <p className="mt-1 text-xs text-gray-500 dark:text-gray-300">
          💡 Extract snapshot with: <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded text-gray-800 dark:text-gray-200">python extract_iosxe_features_standalone.py --config config.txt -o snapshot.json</code>
        </p>
      </div>

      {parseError && (
        <div className="alert alert-error">
          <p className="font-semibold">Invalid Snapshot JSON:</p>
          <p className="text-sm">{parseError}</p>
        </div>
      )}

      {parsedSnapshot && (
        <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-md p-4">
          <h4 className="text-sm font-semibold text-green-800 dark:text-green-300 mb-2">
            ✓ Snapshot Validated
          </h4>
          <div className="text-sm space-y-1 text-green-700 dark:text-green-400">
            <p><strong>Platform:</strong> {parsedSnapshot.platform}</p>
            <p><strong>Extracted:</strong> {new Date(parsedSnapshot.extracted_at).toLocaleString()}</p>
            <p><strong>Features:</strong> {parsedSnapshot.feature_count} detected (from {parsedSnapshot.total_checked} checked)</p>
            <p><strong>Version:</strong> {parsedSnapshot.extractor_version}</p>
          </div>
          {parsedSnapshot.features_present.length > 0 && (
            <details className="mt-3">
              <summary className="text-sm font-medium text-green-800 dark:text-green-300 cursor-pointer hover:underline">
                View {parsedSnapshot.features_present.length} features
              </summary>
              <div className="mt-2 pl-4 text-xs text-green-700 dark:text-green-400 space-y-0.5">
                {parsedSnapshot.features_present.map((feature) => (
                  <div key={feature}>• {feature}</div>
                ))}
              </div>
            </details>
          )}
        </div>
      )}

      <div className="flex gap-3">
        <button
          type="button"
          onClick={handleParse}
          disabled={!snapshotText || loading}
          className="btn btn-secondary flex-shrink-0"
        >
          Validate JSON
        </button>

        <button
          type="submit"
          disabled={!parsedSnapshot || loading}
          className="btn btn-primary flex-1"
        >
          {loading ? (
            <>
              <svg
                className="animate-spin -ml-1 mr-3 h-5 w-5 text-white"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                ></circle>
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                ></path>
              </svg>
              Verifying...
            </>
          ) : (
            'Verify with Snapshot'
          )}
        </button>
      </div>

      {!parsedSnapshot && snapshotText && (
        <p className="text-xs text-gray-500 dark:text-gray-300">
          👆 Click "Validate JSON" first to check the snapshot format
        </p>
      )}
    </form>
  );
}
