import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { reasoningApi } from '../api/client';
import type { AnalysisResult } from '../types';
import type { ExplainResponse } from '../types/reasoning';

interface ResultsDisplayProps {
  analysis: AnalysisResult;
  onVerifyDevice: () => void;
}

export function ResultsDisplay({ analysis, onVerifyDevice }: ResultsDisplayProps) {
  const [showRegex, setShowRegex] = useState(false);
  const [showCommands, setShowCommands] = useState(false);
  const [showExplanation, setShowExplanation] = useState(false);
  const [explanation, setExplanation] = useState<ExplainResponse | null>(null);

  // Explain mutation
  const explainMutation = useMutation({
    mutationFn: () => reasoningApi.explain({
      psirt_id: analysis.advisory_id || undefined,
      psirt_summary: analysis.psirt_summary,
      labels: analysis.predicted_labels,
      platform: analysis.platform,
      question_type: 'why',
    }),
    onSuccess: (data: ExplainResponse) => {
      setExplanation(data);
      setShowExplanation(true);
    },
  });

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-xl font-bold text-slate-900 dark:text-white">Analysis Complete</h3>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Platform: <span className="font-medium text-slate-700 dark:text-slate-300">{analysis.platform}</span>
          </p>
          {analysis.advisory_id && (
            <p className="text-sm text-slate-500 dark:text-slate-400">
              Advisory: <span className="font-medium text-slate-700 dark:text-slate-300">{analysis.advisory_id}</span>
            </p>
          )}
        </div>
        {analysis.confidence !== undefined && analysis.confidence > 0 && (
          <div className="text-right">
            <p className="text-sm font-medium text-slate-500 dark:text-slate-400">Confidence</p>
            <div className="flex items-center gap-2">
              <p className={`text-2xl font-bold ${analysis.confidence >= 0.75 ? 'text-green-600' :
                  analysis.confidence >= 0.60 ? 'text-yellow-600' :
                    'text-red-600'
                }`}>
                {(analysis.confidence * 100).toFixed(0)}%
              </p>
              {analysis.confidence >= 0.75 ? (
                <span className="text-green-600">✓</span>
              ) : analysis.confidence >= 0.60 ? (
                <span className="text-yellow-600">⚠</span>
              ) : (
                <span className="text-red-600">!</span>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Low Confidence Warning */}
      {analysis.confidence !== undefined && analysis.confidence < 0.75 && (
        <div className={`alert ${analysis.confidence < 0.60 ? 'alert-error' : 'bg-yellow-50 dark:bg-yellow-900/20 text-yellow-800 dark:text-yellow-200 border border-yellow-200 dark:border-yellow-800'
          }`}>
          <p className="font-semibold">
            {analysis.confidence < 0.60 ? '🔴 Low Confidence - Analyst Review Required' : '⚠️ Medium Confidence - Review Recommended'}
          </p>
          <p className="text-sm mt-1">
            {analysis.confidence < 0.60
              ? 'This PSIRT does not match known patterns well. Please manually verify the predicted labels before proceeding.'
              : 'Please review the predicted labels to ensure accuracy before device verification.'}
          </p>
        </div>
      )}

      {/* Predicted Labels */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h4 className="text-base font-semibold text-slate-800 dark:text-slate-200">
            Predicted Labels ({analysis.predicted_labels.length})
          </h4>
          {analysis.predicted_labels.length > 0 && (
            <button
              onClick={() => explainMutation.mutate()}
              disabled={explainMutation.isPending}
              className="text-sm px-3 py-1 bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 rounded-md hover:bg-purple-200 dark:hover:bg-purple-900/50 disabled:opacity-50 transition-colors flex items-center gap-1"
            >
              {explainMutation.isPending ? (
                <>
                  <span className="animate-spin">⏳</span> Explaining...
                </>
              ) : (
                <>💡 Explain Labels</>
              )}
            </button>
          )}
        </div>
        {analysis.predicted_labels.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {analysis.predicted_labels.map((label) => (
              <span key={label} className="badge badge-primary">
                {label}
              </span>
            ))}
          </div>
        ) : (
          <p className="text-gray-500 italic">No labels predicted</p>
        )}
      </div>

      {/* Explanation Section */}
      {explainMutation.isError && (
        <div className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-md">
          <p className="text-red-700 dark:text-red-300 text-sm">
            Failed to get explanation: {(explainMutation.error as Error).message}
          </p>
        </div>
      )}

      {showExplanation && explanation && (
        <div className="p-4 bg-purple-50 dark:bg-purple-900/20 border border-purple-200 dark:border-purple-800 rounded-lg">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-base font-semibold text-purple-800 dark:text-purple-200 flex items-center gap-2">
              💡 AI Explanation
            </h4>
            <div className="flex items-center gap-3 text-xs text-purple-600 dark:text-purple-400">
              <span>
                {explanation.reasoning_time_ms < 1000
                  ? `${explanation.reasoning_time_ms.toFixed(0)}ms`
                  : `${(explanation.reasoning_time_ms / 1000).toFixed(1)}s`}
              </span>
              <span>
                {(explanation.confidence * 100).toFixed(0)}% confidence
              </span>
              <button
                onClick={() => setShowExplanation(false)}
                className="text-purple-500 hover:text-purple-700 dark:hover:text-purple-300"
              >
                ✕
              </button>
            </div>
          </div>
          <div className="text-sm text-purple-900 dark:text-purple-100 whitespace-pre-wrap leading-relaxed">
            {explanation.explanation}
          </div>
          {explanation.device_context && (
            <div className="mt-3 pt-3 border-t border-purple-200 dark:border-purple-700">
              <p className="text-xs font-medium text-purple-700 dark:text-purple-300 mb-1">
                Device Context:
              </p>
              <p className="text-sm text-purple-800 dark:text-purple-200">
                {explanation.device_context}
              </p>
            </div>
          )}
        </div>
      )}

      {/* Config Regex Patterns (Collapsible) */}
      {analysis.config_regex.length > 0 && (
        <div>
          <button
            onClick={() => setShowRegex(!showRegex)}
            className="text-base font-semibold text-slate-700 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white flex items-center gap-2 transition-colors"
          >
            <span>{showRegex ? '▼' : '▶'}</span>
            Config Regex Patterns ({analysis.config_regex.length})
          </button>
          {showRegex && (
            <div className="mt-2 p-3 bg-gray-50 dark:bg-gray-900/50 rounded-md border border-gray-200 dark:border-gray-700">
              <ul className="space-y-1 text-sm font-mono">
                {analysis.config_regex.map((regex, idx) => (
                  <li key={idx} className="text-gray-700 dark:text-gray-300">
                    {regex}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Show Commands (Collapsible) */}
      {analysis.show_commands.length > 0 && (
        <div>
          <button
            onClick={() => setShowCommands(!showCommands)}
            className="text-base font-semibold text-slate-700 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white flex items-center gap-2 transition-colors"
          >
            <span>{showCommands ? '▼' : '▶'}</span>
            Show Commands ({analysis.show_commands.length})
          </button>
          {showCommands && (
            <div className="mt-2 p-3 bg-gray-50 dark:bg-gray-900/50 rounded-md border border-gray-200 dark:border-gray-700">
              <ul className="space-y-1 text-sm font-mono">
                {analysis.show_commands.map((cmd, idx) => (
                  <li key={idx} className="text-gray-700 dark:text-gray-300">
                    {cmd}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Summary (Truncated) */}
      <div>
        <h4 className="text-base font-semibold text-slate-800 dark:text-slate-200 mb-2">Summary</h4>
        <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-300 line-clamp-3">{analysis.psirt_summary}</p>
      </div>

      {/* Verify Device Button */}
      <button onClick={onVerifyDevice} className="btn btn-success w-full">
        Proceed to Device Verification →
      </button>
    </div>
  );
}
