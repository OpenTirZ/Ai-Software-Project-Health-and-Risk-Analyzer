import React, { useState, useEffect } from 'react';
import type { PageView, ActivityTab } from '../types';
import {
  dataSyncApi,
  type ProjectResponse,
} from '../services/api';
import {
  GitCommit,
  GitPullRequest,
  AlertCircle,
  Search,
  RefreshCw,
  Clock,
  ArrowLeft,
  ExternalLink,
  CheckCircle2,
  Tag,
} from 'lucide-react';

interface ActivityProps {
  project: ProjectResponse | null;
  onNavigate: (view: PageView) => void;
}

export const Activity: React.FC<ActivityProps> = ({ project, onNavigate }) => {
  const [activeTab, setActiveTab] = useState<ActivityTab>('commits');
  const [commits, setCommits] = useState<any[]>([]);
  const [prs, setPrs] = useState<any[]>([]);
  const [issues, setIssues] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isSyncing, setIsSyncing] = useState<boolean>(false);
  const [syncFeedback, setSyncFeedback] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  const loadTabData = async (projectId: string, tab: ActivityTab) => {
    setIsLoading(true);
    try {
      if (tab === 'commits') {
        const data = await dataSyncApi.getCommits(projectId, 100);
        setCommits(Array.isArray(data) ? data : []);
      } else if (tab === 'pull-requests') {
        const data = await dataSyncApi.getPRs(projectId);
        setPrs(Array.isArray(data) ? data : []);
      } else if (tab === 'issues') {
        const data = await dataSyncApi.getIssues(projectId);
        setIssues(Array.isArray(data) ? data : []);
      }
    } catch (err: any) {
      console.warn(`Could not load ${tab}:`, err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (project?.id) {
      loadTabData(project.id, activeTab);
    }
  }, [project?.id, activeTab]);

  const handleSyncCurrent = async () => {
    if (!project?.id) return;
    setIsSyncing(true);
    setSyncFeedback(`Syncing latest ${activeTab} from GitHub...`);
    try {
      if (activeTab === 'commits') {
        await dataSyncApi.syncCommits(project.id, project.default_branch || 'main');
        setSyncFeedback('Commits synchronized successfully!');
      } else if (activeTab === 'pull-requests') {
        await dataSyncApi.syncPRs(project.id);
        setSyncFeedback('Pull Requests synchronized successfully!');
      } else if (activeTab === 'issues') {
        await dataSyncApi.syncIssues(project.id);
        setSyncFeedback('Issues synchronized successfully!');
      }
      await loadTabData(project.id, activeTab);
      setTimeout(() => setSyncFeedback(null), 3500);

    } catch (err: any) {
      const status =
        err.status ||
        Number(err.message?.match(/\((\d{3})\)$/)?.[1]);

      let message = err.message || 'Synchronization failed.';

      if (status === 403) {
        message = 'You do not have permission to sync this data. Please check your project role and membership.';
      } else if (status === 404) {
        message = 'The requested project or GitHub repository could not be found.';
      } else if (status === 429) {
        message = 'GitHub API rate limit exceeded. Please try again later.';
      }

      setSyncFeedback(`Sync failed: ${message}`);
      setTimeout(() => setSyncFeedback(null), 5000);
    } finally {
      setIsSyncing(false);
    }
  };

  if (!project) {
    return (
      <div className="p-8 max-w-4xl mx-auto text-center space-y-4">
        <p className="text-slate-500">Please select an active project to view activity telemetry.</p>
        <button
          onClick={() => onNavigate('projects')}
          className="px-4 py-2 bg-indigo-600 text-white rounded-xl text-xs font-bold"
        >
          View Projects
        </button>
      </div>
    );
  }

  // Filter items
  const filteredCommits = commits.filter((c) => {
    const q = searchQuery.toLowerCase();
    const msg = (c.message || '').toLowerCase();
    const author = (c.author?.name || c.author_name || '').toLowerCase();
    const sha = (c.sha || '').toLowerCase();
    return msg.includes(q) || author.includes(q) || sha.includes(q);
  });

  const filteredPRs = prs.filter((p) => {
    const q = searchQuery.toLowerCase();
    const title = (p.title || '').toLowerCase();
    const author = (p.author?.login || p.author || '').toLowerCase();
    const num = String(p.number || p.pr_number || '');
    return title.includes(q) || author.includes(q) || num.includes(q);
  });

  const filteredIssues = issues.filter((i) => {
    const q = searchQuery.toLowerCase();
    const title = (i.title || '').toLowerCase();
    const author = (i.author?.login || i.author || '').toLowerCase();
    const num = String(i.number || i.issue_number || '');
    return title.includes(q) || author.includes(q) || num.includes(q);
  });

  return (
    <div className="p-6 md:p-8 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <button
            onClick={() => onNavigate('overview')}
            className="inline-flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-800 font-medium mb-1 cursor-pointer"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Back to Project Overview</span>
          </button>
          <h1 className="text-2xl md:text-3xl font-bold text-slate-900 tracking-tight">
            Activity Telemetry
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Raw ingested GitHub telemetry for <span className="font-semibold text-slate-700">{project.name}</span>.
          </p>
        </div>

        {/* Sync Current Tab Button */}
        <button
          onClick={handleSyncCurrent}
          disabled={isSyncing}
          className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-xs font-bold shadow-md shadow-indigo-600/20 transition-all cursor-pointer disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isSyncing ? 'animate-spin' : ''}`} />
          <span>{isSyncing ? 'Synchronizing...' : `Sync ${activeTab.replace('-', ' ').toUpperCase()}`}</span>
        </button>
      </div>

      {syncFeedback && (
        <div className="p-3 bg-indigo-50 border border-indigo-200 rounded-xl text-xs text-indigo-900 animate-fadeIn">
          {syncFeedback}
        </div>
      )}

      {/* Tabs & Search Filter */}
      <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4">
        {/* Tabs Control */}
        <div className="flex items-center gap-2 p-1 bg-slate-100 rounded-xl max-w-md">
          <button
            onClick={() => {
              setActiveTab('commits');
              setSearchQuery('');
            }}
            className={`flex-1 flex items-center justify-center gap-2 py-2 px-3 rounded-lg text-xs font-bold transition-all cursor-pointer ${
              activeTab === 'commits'
                ? 'bg-white text-blue-600 shadow-sm'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <GitCommit className="w-3.5 h-3.5" />
            <span>Commits ({commits.length})</span>
          </button>

          <button
            onClick={() => {
              setActiveTab('pull-requests');
              setSearchQuery('');
            }}
            className={`flex-1 flex items-center justify-center gap-2 py-2 px-3 rounded-lg text-xs font-bold transition-all cursor-pointer ${
              activeTab === 'pull-requests'
                ? 'bg-white text-blue-600 shadow-sm'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <GitPullRequest className="w-3.5 h-3.5" />
            <span>Pull Requests ({prs.length})</span>
          </button>

          <button
            onClick={() => {
              setActiveTab('issues');
              setSearchQuery('');
            }}
            className={`flex-1 flex items-center justify-center gap-2 py-2 px-3 rounded-lg text-xs font-bold transition-all cursor-pointer ${
              activeTab === 'issues'
                ? 'bg-white text-blue-600 shadow-sm'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <AlertCircle className="w-3.5 h-3.5" />
            <span>Issues ({issues.length})</span>
          </button>
        </div>

        {/* Search Bar */}
        <div className="flex items-center gap-2 bg-white px-3 py-2 rounded-xl border border-slate-200 shadow-sm w-full md:w-80">
          <Search className="w-4 h-4 text-slate-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder={`Search ${activeTab.replace('-', ' ')}...`}
            className="w-full text-xs text-slate-800 focus:outline-none bg-transparent placeholder:text-slate-400"
          />
        </div>
      </div>

      {/* COMMITS VIEW */}
      {activeTab === 'commits' && (
        <div className="bg-white rounded-2xl border border-slate-200/90 shadow-sm overflow-hidden">
          {filteredCommits.length === 0 ? (
            <div className="p-12 text-center text-slate-400 text-xs space-y-2">
              <GitCommit className="w-8 h-8 text-slate-300 mx-auto" />
              <p>No commits found. Click "Sync Commits" above to pull commit history from GitHub.</p>
            </div>
          ) : (
            <div className="divide-y divide-slate-100">
              {filteredCommits.map((c, i) => {
                const authorName = c.author?.name || c.author_name || c.author?.login || 'Developer';
                const dateStr = c.date || c.authored_date || c.created_at;
                const shortSha = (c.sha || '').substring(0, 7);

                return (
                  <div key={c._id || c.sha || i} className="p-4 hover:bg-slate-50/80 transition-colors flex items-start justify-between gap-4">
                    <div className="space-y-1">
                      <p className="text-sm font-semibold text-slate-900">
                        {c.message || 'Commit with no message'}
                      </p>
                      <div className="flex items-center gap-3 text-xs text-slate-500 font-mono">
                        <span className="font-sans font-medium text-slate-700">{authorName}</span>
                        <span>•</span>
                        <span>{dateStr ? new Date(dateStr).toLocaleString() : 'N/A'}</span>
                        {c.branch && (
                          <>
                            <span>•</span>
                            <span className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 text-[10px]">
                              {c.branch}
                            </span>
                          </>
                        )}
                      </div>
                    </div>

                    <div className="shrink-0 flex items-center gap-2">
                      <span className="px-2 py-1 rounded bg-slate-100 border border-slate-200 text-xs font-mono text-slate-700">
                        {shortSha}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* PULL REQUESTS VIEW */}
      {activeTab === 'pull-requests' && (
        <div className="bg-white rounded-2xl border border-slate-200/90 shadow-sm overflow-hidden">
          {filteredPRs.length === 0 ? (
            <div className="p-12 text-center text-slate-400 text-xs space-y-2">
              <GitPullRequest className="w-8 h-8 text-slate-300 mx-auto" />
              <p>No pull requests found. Click "Sync Pull Requests" to ingest PR telemetry.</p>
            </div>
          ) : (
            <div className="divide-y divide-slate-100">
              {filteredPRs.map((p, i) => {
                const state = String(p.state || 'open').toLowerCase();
                const badgeColor =
                  state === 'merged'
                    ? 'text-purple-700 bg-purple-50 border-purple-200'
                    : state === 'closed'
                    ? 'text-rose-700 bg-rose-50 border-rose-200'
                    : 'text-emerald-700 bg-emerald-50 border-emerald-200';

                return (
                  <div key={p._id || p.number || i} className="p-4 hover:bg-slate-50/80 transition-colors flex items-start justify-between gap-4">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-bold text-xs text-slate-500">
                          #{p.number || p.pr_number}
                        </span>
                        <h4 className="text-sm font-semibold text-slate-900">
                          {p.title}
                        </h4>
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase border ${badgeColor}`}>
                          {state}
                        </span>
                      </div>
                      <p className="text-xs text-slate-500">
                        Author: <span className="font-medium text-slate-700">{p.author?.login || p.author || 'contributor'}</span>
                        {' '}&bull; Created: {p.created_at ? new Date(p.created_at).toLocaleDateString() : 'N/A'}
                      </p>
                    </div>

                    {p.html_url && (
                      <a
                        href={p.html_url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-xs text-indigo-600 hover:text-indigo-800 inline-flex items-center gap-1"
                      >
                        <span>GitHub</span>
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* ISSUES VIEW */}
      {activeTab === 'issues' && (
        <div className="bg-white rounded-2xl border border-slate-200/90 shadow-sm overflow-hidden">
          {filteredIssues.length === 0 ? (
            <div className="p-12 text-center text-slate-400 text-xs space-y-2">
              <AlertCircle className="w-8 h-8 text-slate-300 mx-auto" />
              <p>No issues found. Click "Sync Issues" to pull issue records from GitHub.</p>
            </div>
          ) : (
            <div className="divide-y divide-slate-100">
              {filteredIssues.map((issue, i) => {
                const state = String(issue.state || 'open').toLowerCase();
                const badgeColor =
                  state === 'closed'
                    ? 'text-slate-600 bg-slate-100 border-slate-200'
                    : 'text-emerald-700 bg-emerald-50 border-emerald-200';

                return (
                  <div key={issue._id || issue.number || i} className="p-4 hover:bg-slate-50/80 transition-colors flex items-start justify-between gap-4">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-bold text-xs text-slate-500">
                          #{issue.number || issue.issue_number}
                        </span>
                        <h4 className="text-sm font-semibold text-slate-900">
                          {issue.title}
                        </h4>
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase border ${badgeColor}`}>
                          {state}
                        </span>
                      </div>
                      <p className="text-xs text-slate-500">
                        Author: <span className="font-medium text-slate-700">{issue.author?.login || issue.author || 'user'}</span>
                        {' '}&bull; Last updated: {issue.updated_at ? new Date(issue.updated_at).toLocaleDateString() : 'N/A'}
                      </p>
                    </div>

                    {issue.html_url && (
                      <a
                        href={issue.html_url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-xs text-indigo-600 hover:text-indigo-800 inline-flex items-center gap-1"
                      >
                        <span>GitHub</span>
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
