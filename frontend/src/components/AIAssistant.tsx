import { useState, useRef, useEffect } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { reasoningApi } from '../api/client';
import type { AskResponse } from '../types/reasoning';

interface Message {
  id: string;
  type: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  reasoning_time_ms?: number;
  sources?: { type: string }[];
  suggested_actions?: string[] | null;
}

const SUGGESTED_QUESTIONS = [
  'Which devices have critical bugs?',
  'What bugs affect C9200L?',
  'What should I prioritize?',
  'Give me a security summary',
  'List critical IOS-XE bugs',
];

export function AIAssistant() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [dashboardMode, setDashboardMode] = useState<'bugs' | 'psirts'>('bugs');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Fetch summary on load
  const summaryQuery = useQuery({
    queryKey: ['reasoning-summary'],
    queryFn: () => reasoningApi.getSummary('week', 'brief'),
    staleTime: 60000, // 1 minute
  });

  // Ask mutation
  const askMutation = useMutation({
    mutationFn: (question: string) => reasoningApi.ask({ question }),
    onSuccess: (data: AskResponse) => {
      const assistantMessage: Message = {
        id: `assistant-${Date.now()}`,
        type: 'assistant',
        content: data.answer,
        timestamp: new Date(),
        reasoning_time_ms: data.reasoning_time_ms,
        sources: data.sources,
        suggested_actions: data.suggested_actions,
      };
      setMessages(prev => [...prev, assistantMessage]);
    },
    onError: (error: Error) => {
      const errorMessage: Message = {
        id: `error-${Date.now()}`,
        type: 'assistant',
        content: `Error: ${error.message}`,
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, errorMessage]);
    },
  });

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || askMutation.isPending) return;

    const userMessage: Message = {
      id: `user-${Date.now()}`,
      type: 'user',
      content: input.trim(),
      timestamp: new Date(),
    };
    setMessages(prev => [...prev, userMessage]);
    askMutation.mutate(input.trim());
    setInput('');
  };

  const handleSuggestionClick = (question: string) => {
    setInput(question);
  };

  const handleQuickAction = (action: string) => {
    // Convert action to a question format and auto-submit
    const userMessage: Message = {
      id: `user-${Date.now()}`,
      type: 'user',
      content: action,
      timestamp: new Date(),
    };
    setMessages(prev => [...prev, userMessage]);
    askMutation.mutate(action);
  };

  const getRiskLevelColor = (level: string) => {
    switch (level) {
      case 'critical': return 'text-red-600 dark:text-red-400 bg-red-100 dark:bg-red-900/30';
      case 'elevated': return 'text-orange-600 dark:text-orange-400 bg-orange-100 dark:bg-orange-900/30';
      case 'moderate': return 'text-yellow-600 dark:text-yellow-400 bg-yellow-100 dark:bg-yellow-900/30';
      case 'low': return 'text-green-600 dark:text-green-400 bg-green-100 dark:bg-green-900/30';
      default: return 'text-gray-600 dark:text-gray-400 bg-gray-100 dark:bg-gray-800';
    }
  };

  return (
    <div className="space-y-6">
      {/* Summary Dashboard */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="card-header mb-0">Security Posture Summary</h2>
          {/* Mode Toggle */}
          <div className="flex gap-2">
            <button
              className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
                dashboardMode === 'bugs'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-400 hover:bg-gray-300 dark:hover:bg-gray-600'
              }`}
              onClick={() => setDashboardMode('bugs')}
            >
              Bugs
            </button>
            <button
              className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
                dashboardMode === 'psirts'
                  ? 'bg-purple-600 text-white'
                  : 'bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-400 hover:bg-gray-300 dark:hover:bg-gray-600'
              }`}
              onClick={() => setDashboardMode('psirts')}
            >
              PSIRTs
            </button>
          </div>
        </div>

        {summaryQuery.isLoading ? (
          <div className="animate-pulse space-y-3">
            <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-3/4"></div>
            <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/2"></div>
          </div>
        ) : summaryQuery.error ? (
          <div className="text-red-600 dark:text-red-400">
            Failed to load summary: {(summaryQuery.error as Error).message}
          </div>
        ) : summaryQuery.data ? (
          <>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {/* Risk Level */}
            <div className={`p-4 rounded-lg ${getRiskLevelColor(summaryQuery.data.risk_assessment)}`}>
              <div className="text-2xl font-bold uppercase">
                {summaryQuery.data.risk_assessment}
              </div>
              <div className="text-sm opacity-80">Risk Level</div>
            </div>

            {/* Affecting Inventory - Dynamic based on mode */}
            <div className={`p-4 rounded-lg ${dashboardMode === 'bugs' ? 'bg-blue-100 dark:bg-blue-900/30' : 'bg-purple-100 dark:bg-purple-900/30'}`}>
              <div className={`text-2xl font-bold ${dashboardMode === 'bugs' ? 'text-blue-600 dark:text-blue-400' : 'text-purple-600 dark:text-purple-400'}`}>
                {dashboardMode === 'bugs'
                  ? summaryQuery.data.total_advisories?.toLocaleString() || 0
                  : (summaryQuery.data.psirts?.affecting_inventory || 0).toLocaleString()
                }
              </div>
              <div className={`text-sm opacity-80 ${dashboardMode === 'bugs' ? 'text-blue-600 dark:text-blue-400' : 'text-purple-600 dark:text-purple-400'}`}>
                {dashboardMode === 'bugs'
                  ? (summaryQuery.data.inventory_devices_scanned && summaryQuery.data.inventory_devices_scanned > 0
                      ? 'Bugs Affecting Inventory'
                      : 'Run scans to see impact')
                  : 'PSIRTs Affecting Inventory'
                }
              </div>
              {summaryQuery.data.inventory_devices_scanned !== undefined && (
                <div className={`text-xs opacity-70 mt-1 ${dashboardMode === 'bugs' ? 'text-blue-600 dark:text-blue-400' : 'text-purple-600 dark:text-purple-400'}`}>
                  {dashboardMode === 'bugs'
                    ? `${summaryQuery.data.inventory_devices_scanned} devices scanned`
                    : `Based on ${(summaryQuery.data.inventory_platforms || []).length} platform(s)`
                  }
                </div>
              )}
            </div>

            {/* Critical + High from inventory */}
            <div className="p-4 rounded-lg bg-orange-100 dark:bg-orange-900/30">
              <div className="text-2xl font-bold text-orange-600 dark:text-orange-400">
                {dashboardMode === 'bugs'
                  ? (summaryQuery.data.inventory_critical_high || 0).toLocaleString()
                  : (summaryQuery.data.psirts?.inventory_critical_high || 0).toLocaleString()
                }
              </div>
              <div className="text-sm text-orange-600 dark:text-orange-400 opacity-80">
                Critical + High
              </div>
              <div className="text-xs text-orange-600 dark:text-orange-400 opacity-70 mt-1">
                {dashboardMode === 'bugs' ? 'From inventory scans' : 'From platform match'}
              </div>
            </div>

            {/* Period */}
            <div className="p-4 rounded-lg bg-gray-100 dark:bg-gray-800">
              <div className="text-2xl font-bold text-gray-700 dark:text-gray-300">
                {summaryQuery.data.period}
              </div>
              <div className="text-sm text-gray-600 dark:text-gray-400 opacity-80">
                Analysis Period
              </div>
            </div>
          </div>

          {/* Database Breakdown - Toggle between Bugs and PSIRTs */}
          {(summaryQuery.data.bugs || summaryQuery.data.psirts) && (
            <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
                  Database Totals (Reference)
                </h3>
                <div className="flex gap-2">
                  <button
                    className={`px-2 py-1 text-xs rounded transition-colors ${
                      dashboardMode === 'bugs'
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-400'
                    }`}
                    onClick={() => setDashboardMode('bugs')}
                  >
                    Bugs
                  </button>
                  <button
                    className={`px-2 py-1 text-xs rounded transition-colors ${
                      dashboardMode === 'psirts'
                        ? 'bg-purple-600 text-white'
                        : 'bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-400'
                    }`}
                    onClick={() => setDashboardMode('psirts')}
                  >
                    PSIRTs
                  </button>
                </div>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-7 gap-2 text-sm">
                {(() => {
                  const metrics = dashboardMode === 'bugs' ? summaryQuery.data.bugs : summaryQuery.data.psirts;
                  const isBugs = dashboardMode === 'bugs';
                  return (
                    <>
                      <div className="bg-gray-50 dark:bg-gray-800 p-2 rounded">
                        <div className={isBugs ? 'text-lg font-bold text-blue-600 dark:text-blue-400' : 'text-lg font-bold text-purple-600 dark:text-purple-400'}>
                          {metrics?.total.toLocaleString() || 0}
                        </div>
                        <div className="text-xs text-gray-500 dark:text-gray-400">
                          Total {isBugs ? 'Bugs' : 'PSIRTs'}
                        </div>
                      </div>
                      <div className="bg-gray-50 dark:bg-gray-800 p-2 rounded">
                        <div className="text-lg font-bold text-red-600 dark:text-red-400">
                          {metrics?.critical_high.toLocaleString() || 0}
                        </div>
                        <div className="text-xs text-gray-500 dark:text-gray-400">Critical/High</div>
                      </div>
                      {Object.entries(metrics?.by_platform || {}).map(([platform, count]) => (
                        <div key={platform} className="bg-gray-50 dark:bg-gray-800 p-2 rounded">
                          <div className="text-lg font-bold text-gray-700 dark:text-gray-300">
                            {(count as number).toLocaleString()}
                          </div>
                          <div className="text-xs text-gray-500 dark:text-gray-400">{platform}</div>
                        </div>
                      ))}
                    </>
                  );
                })()}
              </div>
            </div>
          )}
        </>
        ) : null}

        {/* Critical Actions */}
        {summaryQuery.data?.critical_actions && summaryQuery.data.critical_actions.length > 0 && (
          <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
            <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
              Recommended Actions
            </h3>
            <ul className="space-y-1">
              {summaryQuery.data.critical_actions.map((action, i) => (
                <li key={i} className="flex items-center text-sm">
                  <span className="w-6 h-6 flex items-center justify-center bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400 rounded-full text-xs font-bold mr-2">
                    {action.priority}
                  </span>
                  <span className="text-gray-700 dark:text-gray-300">{action.action}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* Chat Interface */}
      <div className="card">
        <h2 className="card-header">Ask the AI</h2>

        {/* Messages Area */}
        <div className="h-96 overflow-y-auto border border-gray-200 dark:border-gray-700 rounded-lg mb-4 p-4 space-y-4 bg-gray-50 dark:bg-gray-900">
          {messages.length === 0 ? (
            <div className="text-center text-gray-500 dark:text-gray-400 py-8">
              <div className="text-4xl mb-2">Ask me about your security posture</div>
              <p className="text-sm">
                I can help you understand bugs affecting your devices, explain PSIRTs,
                and provide remediation guidance.
              </p>
            </div>
          ) : (
            messages.map(message => (
              <div
                key={message.id}
                className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[80%] p-3 rounded-lg ${
                    message.type === 'user'
                      ? 'bg-blue-600 text-white'
                      : 'bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 border border-gray-200 dark:border-gray-700'
                  }`}
                >
                  {/* Message content - preserve markdown-like formatting */}
                  <div className="whitespace-pre-wrap text-sm">
                    {message.content}
                  </div>

                  {/* Metadata for assistant messages */}
                  {message.type === 'assistant' && (
                    <div className="mt-2 pt-2 border-t border-gray-200 dark:border-gray-700 text-xs text-gray-500 dark:text-gray-400">
                      {message.reasoning_time_ms !== undefined && (
                        <span>
                          {message.reasoning_time_ms < 1000
                            ? `${message.reasoning_time_ms.toFixed(1)}ms`
                            : `${(message.reasoning_time_ms / 1000).toFixed(1)}s`}
                        </span>
                      )}
                      {message.sources && message.sources.length > 0 && (
                        <span className="ml-2">
                          Source: {message.sources.map(s => s.type).join(', ')}
                        </span>
                      )}
                    </div>
                  )}

                  {/* Suggested follow-up actions */}
                  {message.type === 'assistant' && message.suggested_actions && message.suggested_actions.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {message.suggested_actions.map((action, i) => (
                        <button
                          key={i}
                          onClick={() => handleQuickAction(action)}
                          disabled={askMutation.isPending}
                          className="px-2 py-1 text-xs bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 rounded hover:bg-blue-100 dark:hover:bg-blue-900/50 transition-colors disabled:opacity-50"
                        >
                          {action}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))
          )}

          {/* Loading indicator */}
          {askMutation.isPending && (
            <div className="flex justify-start">
              <div className="bg-white dark:bg-gray-800 p-3 rounded-lg border border-gray-200 dark:border-gray-700">
                <div className="flex space-x-2">
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Suggested Questions */}
        {messages.length === 0 && (
          <div className="mb-4">
            <div className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">
              Try asking:
            </div>
            <div className="flex flex-wrap gap-2">
              {SUGGESTED_QUESTIONS.map((question, i) => (
                <button
                  key={i}
                  onClick={() => handleSuggestionClick(question)}
                  className="px-3 py-1.5 text-sm bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 rounded-full hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
                >
                  {question}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Input Form */}
        <form onSubmit={handleSubmit} className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about bugs, devices, or security posture..."
            className="flex-1 px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            disabled={askMutation.isPending}
          />
          <button
            type="submit"
            disabled={!input.trim() || askMutation.isPending}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {askMutation.isPending ? 'Thinking...' : 'Ask'}
          </button>
        </form>
      </div>
    </div>
  );
}
