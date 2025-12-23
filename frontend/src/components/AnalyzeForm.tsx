import { useState } from 'react';
import type { Platform } from '../types';
import { PLATFORMS } from '../types';

interface AnalyzeFormProps {
  onAnalyze: (summary: string, platform: Platform, advisoryId?: string) => void;
  loading?: boolean;
}

export function AnalyzeForm({ onAnalyze, loading = false }: AnalyzeFormProps) {
  const [summary, setSummary] = useState('');
  const [platform, setPlatform] = useState<Platform>('IOS-XE');
  const [advisoryId, setAdvisoryId] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (summary.trim()) {
      onAnalyze(summary.trim(), platform, advisoryId.trim() || undefined);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label htmlFor="platform" className="label">
          Platform *
        </label>
        <select
          id="platform"
          value={platform}
          onChange={(e) => setPlatform(e.target.value as Platform)}
          className="input"
          disabled={loading}
        >
          {PLATFORMS.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label htmlFor="advisoryId" className="label">
          Advisory / Bug ID (optional)
        </label>
        <input
          id="advisoryId"
          type="text"
          value={advisoryId}
          onChange={(e) => setAdvisoryId(e.target.value)}
          placeholder="e.g., cisco-sa-iox-dos-95Fqnf7b or CSCwe12345"
          className="input"
          disabled={loading}
        />
      </div>

      <div>
        <label htmlFor="summary" className="label">
          PSIRT / Bug Summary *
        </label>
        <textarea
          id="summary"
          value={summary}
          onChange={(e) => setSummary(e.target.value)}
          placeholder="Paste the PSIRT or bug description here..."
          rows={8}
          maxLength={10000}
          className="input resize-y"
          disabled={loading}
          required
        />
        <p className="text-sm text-gray-500 mt-1">
          {summary.length} / 10,000 characters
        </p>
      </div>

      <button
        type="submit"
        disabled={loading || !summary.trim()}
        className={`btn w-full ${
          loading || !summary.trim() ? 'btn-disabled' : 'btn-primary'
        }`}
      >
        {loading ? (
          <span className="flex items-center justify-center">
            <span className="spinner h-5 w-5 mr-2"></span>
            Analyzing with SEC-8B...
          </span>
        ) : (
          'Analyze'
        )}
      </button>
    </form>
  );
}
