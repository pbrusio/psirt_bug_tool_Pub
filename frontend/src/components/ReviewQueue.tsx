import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

// Types
interface BronzeItem {
  id: number;
  bug_id: string;
  platform: string;
  summary: string;
  predicted_labels: string[];
  reasoning: string | null;
  confidence: number;
  similarity_scores: number[];
  timestamp: string;
  status: 'pending' | 'approved' | 'rejected';
}

interface ReviewQueueResponse {
  items: BronzeItem[];
  total: number;
  offset: number;
  limit: number;
  pending_count: number;
  approved_count: number;
  rejected_count: number;
}

interface ReviewStats {
  total_bronze: number;
  pending: number;
  approved: number;
  rejected: number;
  platforms: Record<string, { total: number; pending: number }>;
}

// API functions
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

async function fetchReviewQueue(params: {
  offset?: number;
  limit?: number;
  platform?: string;
  status_filter?: string;
}): Promise<ReviewQueueResponse> {
  const searchParams = new URLSearchParams();
  if (params.offset) searchParams.set('offset', params.offset.toString());
  if (params.limit) searchParams.set('limit', params.limit.toString());
  if (params.platform) searchParams.set('platform', params.platform);
  if (params.status_filter) searchParams.set('status_filter', params.status_filter);

  const response = await fetch(`${API_BASE}/review/queue?${searchParams}`);
  if (!response.ok) throw new Error('Failed to fetch review queue');
  return response.json();
}

async function fetchReviewStats(): Promise<ReviewStats> {
  const response = await fetch(`${API_BASE}/review/stats`);
  if (!response.ok) throw new Error('Failed to fetch stats');
  return response.json();
}

async function approveItem(itemId: number, labels: string[], reasoning?: string): Promise<void> {
  const response = await fetch(`${API_BASE}/review/queue/${itemId}/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ labels, reasoning }),
  });
  if (!response.ok) throw new Error('Failed to approve item');
}

async function rejectItem(itemId: number, reason?: string): Promise<void> {
  const response = await fetch(`${API_BASE}/review/queue/${itemId}/reject?reason=${encodeURIComponent(reason || '')}`, {
    method: 'POST',
  });
  if (!response.ok) throw new Error('Failed to reject item');
}

async function batchApprove(itemIds: number[]): Promise<{ approved_count: number; failed_count: number }> {
  const response = await fetch(`${API_BASE}/review/batch/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(itemIds),
  });
  if (!response.ok) throw new Error('Failed to batch approve');
  return response.json();
}

// Components

function StatCard({ label, value, color }: { label: string; value: number; color: string }) {
  const colorClasses: Record<string, string> = {
    blue: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
    yellow: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
    green: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
    red: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
  };

  return (
    <div className={`rounded-lg p-4 ${colorClasses[color]}`}>
      <div className="text-2xl font-bold">{value.toLocaleString()}</div>
      <div className="text-sm opacity-75">{label}</div>
    </div>
  );
}

function ReviewItemCard({
  item,
  onApprove,
  onReject,
  onSelect,
  isSelected,
}: {
  item: BronzeItem;
  onApprove: (labels: string[], reasoning?: string) => void;
  onReject: (reason?: string) => void;
  onSelect: (selected: boolean) => void;
  isSelected: boolean;
}) {
  const [editedLabels, setEditedLabels] = useState<string[]>(item.predicted_labels);
  const [editedReasoning, setEditedReasoning] = useState(item.reasoning || '');
  const [isEditing, setIsEditing] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);

  const confidenceColor =
    item.confidence >= 0.65 ? 'text-green-600 dark:text-green-400' :
    item.confidence >= 0.55 ? 'text-yellow-600 dark:text-yellow-400' :
    'text-red-600 dark:text-red-400';

  const statusBadge = {
    pending: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
    approved: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
    rejected: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
  };

  return (
    <div className={`border rounded-lg p-4 mb-3 transition-all ${
      item.status === 'approved' ? 'border-green-300 bg-green-50/50 dark:border-green-800 dark:bg-green-900/20' :
      item.status === 'rejected' ? 'border-red-300 bg-red-50/50 dark:border-red-800 dark:bg-red-900/20' :
      'border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-800'
    }`}>
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          {item.status === 'pending' && (
            <input
              type="checkbox"
              checked={isSelected}
              onChange={(e) => onSelect(e.target.checked)}
              className="mt-1 h-4 w-4 rounded border-gray-300"
            />
          )}
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-mono font-semibold text-blue-600 dark:text-blue-400">
                {item.bug_id}
              </span>
              <span className="text-xs px-2 py-0.5 rounded bg-gray-100 dark:bg-gray-700">
                {item.platform}
              </span>
              <span className={`text-xs px-2 py-0.5 rounded ${statusBadge[item.status]}`}>
                {item.status}
              </span>
              <span className={`text-sm font-medium ${confidenceColor}`}>
                {(item.confidence * 100).toFixed(1)}%
              </span>
            </div>
          </div>
        </div>

        {item.status === 'pending' && (
          <div className="flex gap-2 shrink-0">
            <button
              onClick={() => onApprove(editedLabels, editedReasoning)}
              className="px-3 py-1 text-sm bg-green-600 text-white rounded hover:bg-green-700"
            >
              Accept
            </button>
            <button
              onClick={() => setIsEditing(!isEditing)}
              className="px-3 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded hover:bg-gray-100 dark:hover:bg-gray-700"
            >
              Edit
            </button>
            <button
              onClick={() => onReject()}
              className="px-3 py-1 text-sm bg-red-600 text-white rounded hover:bg-red-700"
            >
              Reject
            </button>
          </div>
        )}
      </div>

      {/* Labels */}
      <div className="mt-3">
        {isEditing ? (
          <input
            type="text"
            value={editedLabels.join(', ')}
            onChange={(e) => setEditedLabels(e.target.value.split(',').map(l => l.trim()).filter(Boolean))}
            className="w-full px-3 py-2 border rounded dark:bg-gray-700 dark:border-gray-600"
            placeholder="Comma-separated labels"
          />
        ) : (
          <div className="flex flex-wrap gap-1">
            {item.predicted_labels.map((label, i) => (
              <span
                key={i}
                className="px-2 py-0.5 text-xs bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200 rounded"
              >
                {label}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Reasoning */}
      {(item.reasoning || isEditing) && (
        <div className="mt-2">
          {isEditing ? (
            <textarea
              value={editedReasoning}
              onChange={(e) => setEditedReasoning(e.target.value)}
              className="w-full px-3 py-2 border rounded dark:bg-gray-700 dark:border-gray-600 text-sm"
              rows={2}
              placeholder="Reasoning for label assignment"
            />
          ) : (
            <p className="text-sm text-gray-600 dark:text-gray-400 italic">
              "{item.reasoning}"
            </p>
          )}
        </div>
      )}

      {/* Expandable Summary */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="mt-2 text-sm text-blue-600 dark:text-blue-400 hover:underline"
      >
        {isExpanded ? 'Hide summary' : 'Show summary'}
      </button>

      {isExpanded && (
        <div className="mt-2 p-3 bg-gray-50 dark:bg-gray-900 rounded text-sm">
          {item.summary}
        </div>
      )}
    </div>
  );
}

export function ReviewQueue() {
  const queryClient = useQueryClient();
  const [offset, setOffset] = useState(0);
  const [limit] = useState(20);
  const [platformFilter, setPlatformFilter] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('pending');
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

  // Queries
  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ['reviewStats'],
    queryFn: fetchReviewStats,
  });

  const { data: queue, isLoading: queueLoading } = useQuery({
    queryKey: ['reviewQueue', offset, limit, platformFilter, statusFilter],
    queryFn: () => fetchReviewQueue({
      offset,
      limit,
      platform: platformFilter || undefined,
      status_filter: statusFilter || undefined,
    }),
  });

  // Mutations
  const approveMutation = useMutation({
    mutationFn: ({ id, labels, reasoning }: { id: number; labels: string[]; reasoning?: string }) =>
      approveItem(id, labels, reasoning),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reviewQueue'] });
      queryClient.invalidateQueries({ queryKey: ['reviewStats'] });
    },
  });

  const rejectMutation = useMutation({
    mutationFn: ({ id, reason }: { id: number; reason?: string }) =>
      rejectItem(id, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reviewQueue'] });
      queryClient.invalidateQueries({ queryKey: ['reviewStats'] });
    },
  });

  const batchApproveMutation = useMutation({
    mutationFn: (ids: number[]) => batchApprove(ids),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['reviewQueue'] });
      queryClient.invalidateQueries({ queryKey: ['reviewStats'] });
      setSelectedIds(new Set());
      alert(`Approved: ${result.approved_count}, Failed: ${result.failed_count}`);
    },
  });

  const handleSelectItem = (id: number, selected: boolean) => {
    const newSelected = new Set(selectedIds);
    if (selected) {
      newSelected.add(id);
    } else {
      newSelected.delete(id);
    }
    setSelectedIds(newSelected);
  };

  const handleSelectAll = () => {
    if (!queue) return;
    const pendingItems = queue.items.filter(i => i.status === 'pending');
    if (selectedIds.size === pendingItems.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(pendingItems.map(i => i.id)));
    }
  };

  const handleBatchApprove = () => {
    if (selectedIds.size === 0) return;
    if (confirm(`Approve ${selectedIds.size} items with their predicted labels?`)) {
      batchApproveMutation.mutate(Array.from(selectedIds));
    }
  };

  return (
    <div className="space-y-6">
      {/* Stats Dashboard */}
      <div className="card">
        <h2 className="card-header">Review Queue Statistics</h2>
        {statsLoading ? (
          <div className="text-gray-500">Loading stats...</div>
        ) : stats ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard label="Total Bronze" value={stats.total_bronze} color="blue" />
            <StatCard label="Pending Review" value={stats.pending} color="yellow" />
            <StatCard label="Approved" value={stats.approved} color="green" />
            <StatCard label="Rejected" value={stats.rejected} color="red" />
          </div>
        ) : null}

        {/* Platform breakdown */}
        {stats && Object.keys(stats.platforms).length > 0 && (
          <div className="mt-4 pt-4 border-t dark:border-gray-700">
            <h3 className="text-sm font-medium mb-2">By Platform</h3>
            <div className="flex flex-wrap gap-2">
              {Object.entries(stats.platforms).map(([platform, counts]) => (
                <span
                  key={platform}
                  className="text-xs px-2 py-1 bg-gray-100 dark:bg-gray-700 rounded"
                >
                  {platform}: {counts.pending}/{counts.total} pending
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Filters and Actions */}
      <div className="card">
        <div className="flex flex-wrap items-center gap-4">
          {/* Platform Filter */}
          <div>
            <label className="text-sm font-medium block mb-1">Platform</label>
            <select
              value={platformFilter}
              onChange={(e) => { setPlatformFilter(e.target.value); setOffset(0); }}
              className="px-3 py-2 border rounded dark:bg-gray-700 dark:border-gray-600"
            >
              <option value="">All Platforms</option>
              <option value="IOS-XE">IOS-XE</option>
              <option value="IOS-XR">IOS-XR</option>
              <option value="ASA">ASA</option>
              <option value="FTD">FTD</option>
              <option value="NX-OS">NX-OS</option>
            </select>
          </div>

          {/* Status Filter */}
          <div>
            <label className="text-sm font-medium block mb-1">Status</label>
            <select
              value={statusFilter}
              onChange={(e) => { setStatusFilter(e.target.value); setOffset(0); }}
              className="px-3 py-2 border rounded dark:bg-gray-700 dark:border-gray-600"
            >
              <option value="">All Statuses</option>
              <option value="pending">Pending</option>
              <option value="approved">Approved</option>
              <option value="rejected">Rejected</option>
            </select>
          </div>

          {/* Batch Actions */}
          {selectedIds.size > 0 && (
            <div className="ml-auto flex items-center gap-2">
              <span className="text-sm text-gray-600 dark:text-gray-400">
                {selectedIds.size} selected
              </span>
              <button
                onClick={handleBatchApprove}
                disabled={batchApproveMutation.isPending}
                className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50"
              >
                {batchApproveMutation.isPending ? 'Processing...' : 'Approve Selected'}
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Review Items */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="card-header mb-0">
            Items to Review
            {queue && ` (${queue.total} total)`}
          </h2>
          {queue && queue.items.filter(i => i.status === 'pending').length > 0 && (
            <button
              onClick={handleSelectAll}
              className="text-sm text-blue-600 dark:text-blue-400 hover:underline"
            >
              {selectedIds.size === queue.items.filter(i => i.status === 'pending').length
                ? 'Deselect All'
                : 'Select All Pending'}
            </button>
          )}
        </div>

        {queueLoading ? (
          <div className="text-center py-8 text-gray-500">Loading review queue...</div>
        ) : queue && queue.items.length > 0 ? (
          <>
            <div className="space-y-2">
              {queue.items.map((item) => (
                <ReviewItemCard
                  key={item.id}
                  item={item}
                  isSelected={selectedIds.has(item.id)}
                  onSelect={(selected) => handleSelectItem(item.id, selected)}
                  onApprove={(labels, reasoning) =>
                    approveMutation.mutate({ id: item.id, labels, reasoning })
                  }
                  onReject={(reason) =>
                    rejectMutation.mutate({ id: item.id, reason })
                  }
                />
              ))}
            </div>

            {/* Pagination */}
            <div className="flex items-center justify-between mt-4 pt-4 border-t dark:border-gray-700">
              <button
                onClick={() => setOffset(Math.max(0, offset - limit))}
                disabled={offset === 0}
                className="px-4 py-2 border rounded disabled:opacity-50 dark:border-gray-600"
              >
                Previous
              </button>
              <span className="text-sm text-gray-600 dark:text-gray-400">
                Showing {offset + 1} - {Math.min(offset + limit, queue.total)} of {queue.total}
              </span>
              <button
                onClick={() => setOffset(offset + limit)}
                disabled={offset + limit >= queue.total}
                className="px-4 py-2 border rounded disabled:opacity-50 dark:border-gray-600"
              >
                Next
              </button>
            </div>
          </>
        ) : (
          <div className="text-center py-8 text-gray-500">
            No items found matching your filters.
          </div>
        )}
      </div>
    </div>
  );
}
