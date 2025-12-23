import { useState } from 'react';
import type { VerificationResult } from '../types';

interface VerificationReportProps {
  result: VerificationResult;
  onExport?: (format: 'json') => void;
}

export function VerificationReport({ result, onExport }: VerificationReportProps) {
  const [showEvidence, setShowEvidence] = useState(false);

  const getStatusBadge = () => {
    switch (result.overall_status) {
      case 'VULNERABLE':
        return <span className="badge badge-danger text-lg px-4 py-2">🔴 VULNERABLE</span>;
      case 'NOT_VULNERABLE':
        return <span className="badge badge-success text-lg px-4 py-2">✅ NOT VULNERABLE</span>;
      case 'POTENTIALLY VULNERABLE':
        return <span className="badge badge-warning text-lg px-4 py-2">⚠️ POTENTIALLY VULNERABLE</span>;
      case 'LIKELY NOT VULNERABLE':
        return <span className="badge badge-success text-lg px-4 py-2">✅ LIKELY NOT VULNERABLE</span>;
      case 'ERROR':
        return <span className="badge badge-warning text-lg px-4 py-2">⚠️ ERROR</span>;
      default:
        return <span className="badge badge-gray text-lg px-4 py-2">❓ UNKNOWN</span>;
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="text-center">
        {getStatusBadge()}
        <h3 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mt-4">Verification Complete</h3>
      </div>

      {/* Device Info */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 p-4 bg-gray-50 dark:bg-gray-900/50 rounded-md border border-gray-200 dark:border-gray-700">
        <div>
          <p className="text-sm text-gray-500 dark:text-gray-400">Device</p>
          <p className="font-medium text-gray-900 dark:text-gray-100">{result.device_hostname || 'Unknown'}</p>
        </div>
        <div>
          <p className="text-sm text-gray-500 dark:text-gray-400">Version</p>
          <p className="font-medium text-gray-900 dark:text-gray-100">{result.device_version || 'Unknown'}</p>
        </div>
        <div>
          <p className="text-sm text-gray-500 dark:text-gray-400">Platform</p>
          <p className="font-medium text-gray-900 dark:text-gray-100">{result.device_platform || 'Unknown'}</p>
        </div>
      </div>

      {/* Error Message (if any) */}
      {result.error && (
        <div className="alert alert-error">
          <p className="font-semibold">Error:</p>
          <p className="text-sm">{result.error}</p>
        </div>
      )}

      {/* Version Check */}
      {result.version_check && (
        <div>
          <h4 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">Version Check</h4>
          <div className="p-4 bg-gray-50 dark:bg-gray-900/50 rounded-md border border-gray-200 dark:border-gray-700">
            <div className="flex items-center gap-2 mb-2">
              {result.version_check.affected ? (
                <span className="text-red-600 dark:text-red-400 font-bold">❌ Version Affected</span>
              ) : (
                <span className="text-green-600 dark:text-green-400 font-bold">✅ Version Not Affected</span>
              )}
            </div>
            <p className="text-sm text-gray-700 dark:text-gray-300">{result.version_check.reason}</p>
            {result.version_check.matched_versions && result.version_check.matched_versions.length > 0 && (
              <div className="mt-2">
                <p className="text-xs text-gray-500 dark:text-gray-400">Matched versions:</p>
                <div className="flex flex-wrap gap-1 mt-1">
                  {result.version_check.matched_versions.map((v) => (
                    <span key={v} className="badge badge-gray text-xs">
                      {v}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Feature Check */}
      {result.feature_check && (
        <div>
          <h4 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">Feature Detection</h4>
          <div className="space-y-3">
            {result.feature_check.present.length > 0 && (
              <div>
                <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  ✅ Features Present ({result.feature_check.present.length})
                </p>
                <div className="flex flex-wrap gap-2">
                  {result.feature_check.present.map((feature) => (
                    <span key={feature} className="badge badge-success">
                      {feature}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {result.feature_check.absent.length > 0 && (
              <div>
                <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  ❌ Features Absent ({result.feature_check.absent.length})
                </p>
                <div className="flex flex-wrap gap-2">
                  {result.feature_check.absent.map((feature) => (
                    <span key={feature} className="badge badge-gray">
                      {feature}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Reason */}
      <div>
        <h4 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">Analysis</h4>
        <div className="p-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-md">
          <p className="text-gray-800 dark:text-gray-200">{result.reason}</p>
        </div>
      </div>

      {/* Evidence (Collapsible) */}
      {result.evidence && Object.keys(result.evidence).length > 0 && (
        <div>
          <button
            onClick={() => setShowEvidence(!showEvidence)}
            className="text-sm font-medium text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100 flex items-center gap-1"
          >
            <span>{showEvidence ? '▼' : '▶'}</span>
            Command Evidence ({Object.keys(result.evidence).length} commands)
          </button>
          {showEvidence && (
            <div className="mt-2 space-y-3">
              {Object.entries(result.evidence).map(([cmd, output]) => (
                <div key={cmd} className="p-3 bg-gray-50 dark:bg-gray-800 rounded-md">
                  <p className="text-xs font-semibold text-gray-600 dark:text-gray-400 mb-1 font-mono">{cmd}</p>
                  <pre className="text-xs text-gray-700 dark:text-gray-300 whitespace-pre-wrap font-mono bg-white dark:bg-gray-900 p-2 rounded border border-gray-200 dark:border-gray-700 max-h-40 overflow-y-auto">
                    {output}
                  </pre>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Export Options */}
      {onExport && (
        <div className="flex gap-2 pt-4 border-t">
          <button
            onClick={() => onExport('json')}
            className="btn btn-secondary flex-1"
          >
            Export as JSON
          </button>
        </div>
      )}

      {/* Timestamp */}
      <p className="text-xs text-gray-500 dark:text-gray-400 text-center">
        Verified at {new Date(result.timestamp).toLocaleString()}
      </p>
    </div>
  );
}
