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
  ArrowLeft,
  ExternalLink,
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
  const [loadError, setLoadError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  const loadTabData = async (projectId: string, tab: ActivityTab) => {
    setIsLoading(true);
    setLoadError(null);

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
      setLoadError(err?.message || `Failed to load ${tab.replace('-', ' ')} telemetry.`);
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
    setSyncFeedback(`Syncing latest ${activeTab.replace('-', ' ')} from GitHub...`);

    try {
      if (activeTab === 'commits') {
        await dataSyncApi.syncCommits(
          project.id,
          project.default_branch || 'main',
        );
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
      <div className="mx-auto max-w-4xl p-8 text-center">
        <div className="rounded-xl border border-[#9ED4C8] bg-white p-8">
          <p className="text-sm text-[#3F5F5C]">
            Please select an active project to view activity telemetry.
          </p>
          <button
            onClick={() => onNavigate('projects')}
            className="mt-4 rounded-lg bg-[#0B6B63] px-4 py-2 text-sm font-semibold text-white hover:bg-[#084F49] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0B6B63]"
          >
            View Projects
          </button>
        </div>
      </div>
    );
  }

  const query = searchQuery.toLowerCase();

  const filteredCommits = commits.filter((c) => {
    const msg = (c.message || '').toLowerCase();
    const author = (
      (typeof c.author === 'string' ? c.author : c.author?.name) || c.author_name || ''
    ).toLowerCase();
    const sha = (c.sha || '').toLowerCase();

    return msg.includes(query) || author.includes(query) || sha.includes(query);
  });

  const filteredPRs = prs.filter((p) => {
    const title = (p.title || '').toLowerCase();
    const author = (p.author?.login || p.author || '').toLowerCase();
    const num = String(p.number || p.pr_number || '');

    return title.includes(query) || author.includes(query) || num.includes(query);
  });

  const filteredIssues = issues.filter((i) => {
    const title = (i.title || '').toLowerCase();
    const author = (i.author?.login || i.author || '').toLowerCase();
    const num = String(i.number || i.issue_number || '');

    return title.includes(query) || author.includes(query) || num.includes(query);
  });

  const tabs = [
    {
      id: 'commits' as const,
      label: 'Commits',
      count: commits.length,
      icon: GitCommit,
    },
    {
      id: 'pull-requests' as const,
      label: 'Pull Requests',
      count: prs.length,
      icon: GitPullRequest,
    },
    {
      id: 'issues' as const,
      label: 'Issues',
      count: issues.length,
      icon: AlertCircle,
    },
  ];

  const emptyState = (
    icon: React.ElementType,
    message: string,
  ) => {
    const Icon = icon;

    return (
      <div className="px-6 py-14 text-center">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-[#CDEFE6] text-[#0B6B63]">
          <Icon className="h-6 w-6" />
        </div>
        <p className="mt-4 text-sm font-medium text-[#3F5F5C]">
          {message}
        </p>
      </div>
    );
  };

  const stateBadge = (state: string, kind: 'pr' | 'issue') => {
    const normalized = state.toLowerCase();

    let styles = 'border-[#9ED4C8] bg-[#EAF8F3] text-[#3F5F5C]';

    if (normalized === 'open') {
      styles = 'border-[#0B6B63]/20 bg-[#0B6B63]/5 text-[#0B6B63]';
    } else if (normalized === 'merged') {
      styles = 'border-[#9ED4C8] bg-[#CDEFE6] text-[#0B6B63]';
    } else if (normalized === 'closed') {
      styles =
        kind === 'pr'
          ? 'border-[#CC1F2E]/20 bg-[#CC1F2E]/5 text-[#CC1F2E]'
          : 'border-[#9ED4C8] bg-[#EAF8F3] text-[#3F5F5C]';
    }

    return (
      <span
        className={`inline-flex shrink-0 rounded-md border px-2 py-1 text-[10px] font-bold uppercase ${styles}`}
      >
        {normalized}
      </span>
    );
  };

  const githubLink = (url?: string) => {
    if (!url) return null;

    return (
      <a
        href={url}
        target="_blank"
        rel="noreferrer"
        className="inline-flex shrink-0 items-center gap-1.5 rounded-md px-2 py-1.5 text-xs font-semibold text-[#0B6B63] hover:bg-[#CDEFE6] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0B6B63]"
      >
        GitHub
        <ExternalLink className="h-3.5 w-3.5" />
      </a>
    );
  };

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-5 md:p-8">

      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <button
            onClick={() => onNavigate('overview')}
            className="mb-2 inline-flex items-center gap-1.5 text-sm font-medium text-[#5F7C79] hover:text-[#0B6B63] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0B6B63]"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Project Overview
          </button>

          <h1 className="text-2xl font-bold tracking-tight text-[#0E2A2A] md:text-3xl">
            Activity Telemetry
          </h1>

          <p className="mt-1 text-sm text-[#3F5F5C]">
            Raw ingested GitHub telemetry for{' '}
            <span className="font-semibold text-[#0E2A2A]">
              {project.name}
            </span>
            .
          </p>
        </div>

        <button
          onClick={handleSyncCurrent}
          disabled={isSyncing}
          className="inline-flex shrink-0 items-center justify-center gap-2 rounded-lg bg-[#0B6B63] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#084F49] disabled:cursor-not-allowed disabled:opacity-60 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0B6B63]"
        >
          <RefreshCw className="h-4 w-4" />
          {isSyncing
            ? 'Synchronizing...'
            : `Sync ${activeTab.replace('-', ' ')}`}
        </button>
      </div>

      {syncFeedback && (
        <div
          role="status"
          className="rounded-lg border border-[#9ED4C8] bg-white px-4 py-3 text-sm text-[#3F5F5C]"
        >
          {syncFeedback}
        </div>
      )}

      {loadError && (
        <div
          role="alert"
          className="flex items-center gap-2 rounded-lg border border-[#CC1F2E]/30 bg-[#CC1F2E]/5 px-4 py-3 text-sm text-[#CC1F2E]"
        >
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{loadError}</span>
        </div>
      )}

      <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-center">
        <div
          className="grid grid-cols-3 gap-1 rounded-lg border border-[#9ED4C8] bg-white p-1"
          aria-label="Activity type"
        >
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;

            return (
              <button
                key={tab.id}
                onClick={() => {
                  setActiveTab(tab.id);
                  setSearchQuery('');
                }}
                aria-pressed={isActive}
                className={`flex min-w-0 items-center justify-center gap-2 rounded-md px-3 py-2.5 text-xs font-semibold sm:text-sm ${
                  isActive
                    ? 'bg-[#0B6B63] text-white'
                    : 'text-[#3F5F5C] hover:bg-[#CDEFE6] hover:text-[#0B6B63]'
                }`}
              >
                <Icon className="h-4 w-4 shrink-0" />
                <span>{tab.label}</span>
                <span className="tabular-nums opacity-80">
                  {tab.count}
                </span>
              </button>
            );
          })}
        </div>

        <div className="flex w-full items-center gap-2 rounded-lg border border-[#9ED4C8] bg-white px-3 py-2.5 lg:max-w-sm">
          <Search className="h-4 w-4 shrink-0 text-[#5F7C79]" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder={`Search ${activeTab.replace('-', ' ')}...`}
            aria-label={`Search ${activeTab.replace('-', ' ')}`}
            className="w-full bg-transparent text-sm text-[#0E2A2A] outline-none placeholder:text-[#5F7C79]"
          />
        </div>
      </div>

      {isLoading && (
        <div className="rounded-lg border border-[#9ED4C8] bg-white px-4 py-3 text-sm text-[#5F7C79]">
          Loading {activeTab.replace('-', ' ')}...
        </div>
      )}

      {activeTab === 'commits' && (
        <section className="overflow-hidden rounded-xl border border-[#9ED4C8] bg-white">
          <div className="border-b border-[#9ED4C8] px-5 py-4">
            <h2 className="text-sm font-semibold text-[#0E2A2A]">
              Commit History
            </h2>
            <p className="mt-1 text-xs text-[#5F7C79]">
              Repository commits and their authors.
            </p>
          </div>

          {filteredCommits.length === 0 ? (
            emptyState(
              GitCommit,
              searchQuery
                ? 'No commits match your search.'
                : 'No commits found. Use Sync Commits to retrieve commit history from GitHub.',
            )
          ) : (
            <div className="divide-y divide-[#9ED4C8]">
              {filteredCommits.map((c, i) => {
                const authorName =
                  (typeof c.author === 'string' ? c.author : c.author?.name) ||
                  c.author_name ||
                  c.author?.login ||
                  'Developer';
                const dateStr = c.timestamp || c.date || c.authored_date || c.created_at;
                const shortSha = (c.sha || '').substring(0, 7);

                return (
                  <div
                    key={c._id || c.sha || i}
                    className="flex flex-col justify-between gap-3 px-5 py-4 hover:bg-[#EAF8F3] sm:flex-row sm:items-start"
                  >
                    <div className="min-w-0 space-y-2">
                      <p className="break-words text-sm font-semibold leading-5 text-[#0E2A2A]">
                        {c.message || 'Commit with no message'}
                      </p>

                      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-[#5F7C79]">
                        <span className="font-medium text-[#3F5F5C]">
                          {authorName}
                        </span>
                        <span className="hidden sm:inline">•</span>
                        <span>
                          {dateStr
                            ? new Date(dateStr).toLocaleString()
                            : 'N/A'}
                        </span>
                        {c.branch && (
                          <span className="rounded-md border border-[#9ED4C8] bg-[#EAF8F3] px-2 py-1 font-mono text-[11px] text-[#3F5F5C]">
                            {c.branch}
                          </span>
                        )}
                      </div>
                    </div>

                    {shortSha && (
                      <span className="w-fit shrink-0 rounded-md border border-[#9ED4C8] bg-[#EAF8F3] px-2.5 py-1.5 font-mono text-xs text-[#3F5F5C]">
                        {shortSha}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </section>
      )}

      {activeTab === 'pull-requests' && (
        <section className="overflow-hidden rounded-xl border border-[#9ED4C8] bg-white">
          <div className="border-b border-[#9ED4C8] px-5 py-4">
            <h2 className="text-sm font-semibold text-[#0E2A2A]">
              Pull Requests
            </h2>
            <p className="mt-1 text-xs text-[#5F7C79]">
              Review requests and merge status from GitHub.
            </p>
          </div>

          {filteredPRs.length === 0 ? (
            emptyState(
              GitPullRequest,
              searchQuery
                ? 'No pull requests match your search.'
                : 'No pull requests found. Use Sync Pull Requests to retrieve them from GitHub.',
            )
          ) : (
            <div className="divide-y divide-[#9ED4C8]">
              {filteredPRs.map((p, i) => {
                const state = String(p.state || 'open').toLowerCase();

                return (
                  <div
                    key={p._id || p.number || i}
                    className="flex flex-col justify-between gap-3 px-5 py-4 hover:bg-[#EAF8F3] sm:flex-row sm:items-start"
                  >
                    <div className="min-w-0 space-y-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono text-xs font-bold text-[#5F7C79]">
                          #{p.number || p.pr_number}
                        </span>
                        <h3 className="break-words text-sm font-semibold text-[#0E2A2A]">
                          {p.title || 'Untitled pull request'}
                        </h3>
                        {stateBadge(state, 'pr')}
                      </div>

                      <p className="text-xs text-[#5F7C79]">
                        Author:{' '}
                        <span className="font-medium text-[#3F5F5C]">
                          {p.author?.login || p.author || 'contributor'}
                        </span>
                        {' • '}Created:{' '}
                        {p.created_at
                          ? new Date(p.created_at).toLocaleDateString()
                          : 'N/A'}
                      </p>
                    </div>

                    {githubLink(p.html_url)}
                  </div>
                );
              })}
            </div>
          )}
        </section>
      )}

      {activeTab === 'issues' && (
        <section className="overflow-hidden rounded-xl border border-[#9ED4C8] bg-white">
          <div className="border-b border-[#9ED4C8] px-5 py-4">
            <h2 className="text-sm font-semibold text-[#0E2A2A]">
              Project Issues
            </h2>
            <p className="mt-1 text-xs text-[#5F7C79]">
              Tracked repository issues and their current status.
            </p>
          </div>

          {filteredIssues.length === 0 ? (
            emptyState(
              AlertCircle,
              searchQuery
                ? 'No issues match your search.'
                : 'No issues found. Use Sync Issues to retrieve issue records from GitHub.',
            )
          ) : (
            <div className="divide-y divide-[#9ED4C8]">
              {filteredIssues.map((issue, i) => {
                const state = String(issue.state || 'open').toLowerCase();

                return (
                  <div
                    key={issue._id || issue.number || i}
                    className="flex flex-col justify-between gap-3 px-5 py-4 hover:bg-[#EAF8F3] sm:flex-row sm:items-start"
                  >
                    <div className="min-w-0 space-y-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono text-xs font-bold text-[#5F7C79]">
                          #{issue.number || issue.issue_number}
                        </span>
                        <h3 className="break-words text-sm font-semibold text-[#0E2A2A]">
                          {issue.title || 'Untitled issue'}
                        </h3>
                        {stateBadge(state, 'issue')}
                      </div>

                      <p className="text-xs text-[#5F7C79]">
                        Author:{' '}
                        <span className="font-medium text-[#3F5F5C]">
                          {issue.author?.login || issue.author || 'user'}
                        </span>
                        {' • '}Last updated:{' '}
                        {issue.updated_at
                          ? new Date(issue.updated_at).toLocaleDateString()
                          : 'N/A'}
                      </p>
                    </div>

                    {githubLink(issue.html_url)}
                  </div>
                );
              })}
            </div>
          )}
        </section>
      )}
    </div>
  );
};
