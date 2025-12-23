import { useState } from 'react';
import type { ScanResult } from '../types';
import { buildApiUrl, getApiHeaders } from '../api/config';

interface ScanResultsProps {
  result: ScanResult;
  onNewScan: () => void;
}

export function ScanResults({ result, onNewScan }: ScanResultsProps) {
  const [expandedBugs, setExpandedBugs] = useState<Set<string>>(new Set());
  const [showFilteredBugs, setShowFilteredBugs] = useState(false);
  const [exporting, setExporting] = useState(false);

  // Clean HTML tags from text
  const cleanHtml = (text: string | null | undefined): string => {
    if (!text) return 'No summary available';
    return text
      .replace(/<B>/g, '')
      .replace(/<\/B>/g, '')
      .replace(/<b>/g, '')
      .replace(/<\/b>/g, '')
      .replace(/<BR>/g, '\n')
      .replace(/<br>/g, '\n')
      .trim();
  };

  const toggleBug = (bugId: string) => {
    setExpandedBugs(prev => {
      const next = new Set(prev);
      if (next.has(bugId)) {
        next.delete(bugId);
      } else {
        next.add(bugId);
      }
      return next;
    });
  };

  const getSeverityColor = (severity: number) => {
    if (severity === 1) return 'bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-200 border-red-300 dark:border-red-700';
    if (severity === 2) return 'bg-orange-100 dark:bg-orange-900 text-orange-800 dark:text-orange-200 border-orange-300 dark:border-orange-700';
    if (severity === 3) return 'bg-yellow-100 dark:bg-yellow-900 text-yellow-800 dark:text-yellow-200 border-yellow-300 dark:border-yellow-700';
    return 'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-200 border-gray-300 dark:border-gray-600';
  };

  const getSeverityLabel = (severity: number) => {
    if (severity === 1) return 'Critical';
    if (severity === 2) return 'High';
    if (severity === 3) return 'Medium';
    return 'Low';
  };

  const featureReductionPercent = result.feature_filtered !== undefined && result.version_matches > 0
    ? Math.round((1 - result.feature_filtered / result.version_matches) * 100)
    : null;

  const hardwareReductionPercent = result.hardware_filtered !== undefined && result.version_matches > 0
    ? Math.round((1 - result.hardware_filtered / result.version_matches) * 100)
    : null;

  const handleExport = async (format: 'csv' | 'pdf' | 'json') => {
    setExporting(true);

    try {
      const response = await fetch(buildApiUrl(`export/${format}`), {
        method: 'POST',
        headers: getApiHeaders(),
        body: JSON.stringify(result),
      });

      if (!response.ok) {
        throw new Error(`Export failed: ${response.statusText}`);
      }

      // Get the blob from response
      const blob = await response.blob();

      // Create download link
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `vuln_scan_${result.platform}_${result.version}_${result.scan_id}.${format}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      console.error('Export failed:', error);
      alert(`Export failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header with Export and New Scan Buttons */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h3 className="text-xl font-bold text-slate-900 dark:text-white">
          Scan Results
        </h3>
        <div className="flex items-center gap-2">
          {/* Export Dropdown */}
          <div className="relative group">
            <button
              disabled={exporting || result.bugs.length === 0}
              className="btn btn-primary text-sm flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {exporting ? (
                <>
                  <span className="inline-block animate-spin">⏳</span>
                  Exporting...
                </>
              ) : (
                <>
                  📥 Export
                  <span className="text-xs">▼</span>
                </>
              )}
            </button>
            {/* Dropdown Menu */}
            {!exporting && result.bugs.length > 0 && (
              <div className="absolute right-0 mt-1 w-40 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-10">
                <button
                  onClick={() => handleExport('csv')}
                  className="w-full text-left px-4 py-2 text-sm hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-t-lg"
                >
                  📄 Export CSV
                </button>
                <button
                  onClick={() => handleExport('pdf')}
                  className="w-full text-left px-4 py-2 text-sm hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300"
                >
                  📑 Export PDF
                </button>
                <button
                  onClick={() => handleExport('json')}
                  className="w-full text-left px-4 py-2 text-sm hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-b-lg"
                >
                  🔗 Export JSON
                </button>
              </div>
            )}
          </div>

          <button
            onClick={onNewScan}
            className="btn btn-secondary text-sm"
          >
            New Scan
          </button>
        </div>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white dark:bg-gray-800 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
          <div className="text-2xl font-bold text-gray-900 dark:text-gray-100">{result.total_bugs_checked}</div>
          <div className="text-xs text-gray-500 dark:text-gray-400">Bugs Checked</div>
        </div>

        <div className="bg-white dark:bg-gray-800 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
          <div className="text-2xl font-bold text-orange-600 dark:text-orange-400">{result.version_matches}</div>
          <div className="text-xs text-gray-500 dark:text-gray-400">Version Matches</div>
        </div>

        <div className="bg-white dark:bg-gray-800 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
          <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">{result.bugs.length}</div>
          <div className="text-xs text-gray-500 dark:text-gray-400">Final Matches</div>
        </div>

        <div className="bg-white dark:bg-gray-800 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
          <div className="text-2xl font-bold text-green-600 dark:text-green-400">{result.query_time_ms.toFixed(1)}ms</div>
          <div className="text-xs text-gray-500 dark:text-gray-400">Query Time</div>
        </div>
      </div>

      {/* Hardware Filtering Impact */}
      {hardwareReductionPercent !== null && hardwareReductionPercent > 0 && (
        <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
          <div>
            <p className="font-semibold text-blue-900 dark:text-blue-200">
              🔧 Hardware Filtering Active - {result.hardware_model}
            </p>
            <p className="text-sm text-blue-800 dark:text-blue-300 mt-1">
              Reduced hardware-specific false positives by <strong>{hardwareReductionPercent}%</strong> ({result.version_matches} → {result.hardware_filtered} bugs)
            </p>
          </div>
        </div>
      )}

      {/* Feature Filtering Impact */}
      {featureReductionPercent !== null && featureReductionPercent > 0 && (
        <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-semibold text-green-900 dark:text-green-200">
                Feature-Aware Filtering Active
              </p>
              <p className="text-sm text-green-800 dark:text-green-300 mt-1">
                Reduced feature-specific false positives by <strong>{featureReductionPercent}%</strong> ({result.hardware_filtered || result.version_matches} → {result.feature_filtered} bugs)
              </p>
            </div>
            {result.filtered_bugs && result.filtered_bugs.length > 0 && (
              <button
                onClick={() => setShowFilteredBugs(!showFilteredBugs)}
                className="text-sm text-green-700 dark:text-green-300 underline hover:no-underline"
              >
                {showFilteredBugs ? 'Hide' : 'Show'} filtered bugs
              </button>
            )}
          </div>
        </div>
      )}

      {/* Severity Breakdown */}
      <div className="bg-white dark:bg-gray-800 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
        <h4 className="text-base font-semibold text-slate-900 dark:text-white mb-3">Severity Breakdown</h4>
        <div className="flex gap-4 text-sm">
          <div className="flex items-center gap-2">
            <span className="px-2 py-1 rounded text-xs font-semibold bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-200">
              Critical/High
            </span>
            <span className="text-gray-700 dark:text-gray-300">{result.critical_high}</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-1 rounded text-xs font-semibold bg-yellow-100 dark:bg-yellow-900 text-yellow-800 dark:text-yellow-200">
              Medium/Low
            </span>
            <span className="text-gray-700 dark:text-gray-300">{result.medium_low}</span>
          </div>
        </div>
      </div>

      {/* Vulnerabilities List */}
      <div>
        <h4 className="text-lg font-bold text-slate-900 dark:text-white mb-3">
          Known Defects ({result.bugs.length})
        </h4>

        {result.bugs.length === 0 ? (
          <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-6 text-center">
            <p className="text-green-800 dark:text-green-300 font-semibold">
              ✓ No known defects found for this configuration
            </p>
            <p className="text-sm text-green-700 dark:text-green-400 mt-1">
              Your device appears safe based on version and configured features
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {result.bugs.map((bug) => (
              <div
                key={bug.bug_id}
                className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden"
              >
                {/* Bug Header */}
                <div
                  className="p-4 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
                  onClick={() => toggleBug(bug.bug_id)}
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <span className={`px-2 py-1 text-xs font-semibold rounded border ${getSeverityColor(bug.severity)}`}>
                          Sev {bug.severity} - {getSeverityLabel(bug.severity)}
                        </span>
                        <a
                          href={bug.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-blue-600 dark:text-blue-400 hover:underline font-mono text-sm"
                          onClick={(e) => e.stopPropagation()}
                        >
                          {bug.bug_id}
                        </a>
                        <span className="text-xs text-gray-500 dark:text-gray-400">
                          {bug.status}
                        </span>
                      </div>
                      <p className="text-sm text-gray-900 dark:text-gray-100 line-clamp-2">
                        {cleanHtml(bug.headline)}
                      </p>
                      {bug.labels && bug.labels.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-2">
                          {bug.labels.map((label) => (
                            <span
                              key={label}
                              className="px-2 py-0.5 bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200 text-xs rounded"
                            >
                              {label}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                    <button className="text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300">
                      {expandedBugs.has(bug.bug_id) ? '▼' : '▶'}
                    </button>
                  </div>
                </div>

                {/* Bug Details */}
                {expandedBugs.has(bug.bug_id) && (
                  <div className="px-4 pb-4 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/50">
                    <div className="mt-3 space-y-3">
                      <div>
                        <p className="text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">Summary:</p>
                        <p className="text-sm text-gray-600 dark:text-gray-400 whitespace-pre-wrap max-h-48 overflow-y-auto">
                          {cleanHtml(bug.summary)}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">Affected Versions:</p>
                        <p className="text-sm text-gray-600 dark:text-gray-400 font-mono">
                          {bug.affected_versions || 'N/A'}
                        </p>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Filtered Bugs (if feature-aware filtering was used) */}
      {showFilteredBugs && result.filtered_bugs && result.filtered_bugs.length > 0 && (
        <div className="border-t border-gray-200 dark:border-gray-700 pt-6">
          <h4 className="text-lg font-bold text-slate-900 dark:text-white mb-3">
            Filtered Out ({result.filtered_bugs.length} of {result.version_matches})
          </h4>
          <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
            These bugs affect your version but don't match your configured features (false positives avoided)
          </p>
          <div className="space-y-2">
            {result.filtered_bugs.map((vuln) => (
              <div
                key={vuln.bug_id}
                className="bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded p-3 opacity-60"
              >
                <div className="flex items-center gap-2 text-sm">
                  <span className={`px-2 py-0.5 text-xs font-semibold rounded ${getSeverityColor(vuln.severity)}`}>
                    Sev {vuln.severity}
                  </span>
                  <a
                    href={vuln.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 dark:text-blue-400 hover:underline font-mono"
                  >
                    {vuln.bug_id}
                  </a>
                  <span className="text-gray-600 dark:text-gray-400 truncate">
                    {cleanHtml(vuln.headline).substring(0, 100)}...
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Scan Metadata */}
      <div className="text-xs text-gray-500 dark:text-gray-400 border-t border-gray-200 dark:border-gray-700 pt-4">
        <p>Scan ID: {result.scan_id}</p>
        <p>Platform: {result.platform} | Version: {result.version}</p>
        {result.hardware_model && (
          <p>Hardware Model: {result.hardware_model}</p>
        )}
        <p>Timestamp: {new Date(result.timestamp).toLocaleString()}</p>
        {result.features && result.features.length > 0 && (
          <p>Features: {result.features.join(', ')}</p>
        )}
      </div>
    </div>
  );
}
