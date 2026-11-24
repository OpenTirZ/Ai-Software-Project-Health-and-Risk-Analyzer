import React, { useState, useEffect, useMemo } from 'react';

import type { PageView } from '../types';

import {
  metricsApi,
  dataSyncApi,
  type ProjectResponse,
  type HealthSummaryData,
  type MetricsBreakdownData,
} from '../services/api';

import {
  ArrowRight,
  RefreshCw,
  AlertTriangle,
  GitPullRequest,
  GitCommit,
  AlertCircle,
  CircleDot,
  Layers,
  CheckCircle2,
  ShieldAlert,
  Users,
  Timer,
  CalendarClock,
  Clock,
  ExternalLink,
} from 'lucide-react';

interface ProjectOverviewProps {
  project: ProjectResponse | null;
  onNavigate: (view: PageView) => void;
  onRefreshProject?: () => void;
}

interface FeedItem {
  key: string;
  kind: 'commit' | 'pr' | 'issue';
  title: string;
  actor: string;
  at: number;
  state?: string;
  ref?: string;
}

const TEAL = '#16A34A';
const BRAND = '#0B6B63';
const CRIMSON = '#CC1F2E';
const AMBER = '#B45309';
const MUTED = '#5F7C79';
const BORDER = '#9ED4C8';
const TRACK = '#CDEFE6';

const HEATMAP_WEEKS = 20;
const WEEKDAYS = [
  'Sunday',
  'Monday',
  'Tuesday',
  'Wednesday',
  'Thursday',
  'Friday',
  'Saturday',
];
const HEAT_LEVELS = [
  'rgba(205, 239, 230, 0.7)',
  'rgba(11, 107, 99, 0.28)',
  'rgba(11, 107, 99, 0.5)',
  'rgba(11, 107, 99, 0.75)',
  BRAND,
];

const getStatusColor = (status: string) => {
  switch (status) {
    case 'Good':
    case 'Low':
      return TEAL;
    case 'Caution':
    case 'Medium':
      return AMBER;
    case 'At Risk':
    case 'High':
      return CRIMSON;
    default:
      return MUTED;
  }
};

const getStatusBadge = (status: string) => {
  switch (status) {
    case 'Good':
    case 'Low':
      return 'border-[#86EFAC] bg-[#DCFCE7] text-[#15803D]';
    case 'Caution':
    case 'Medium':
      return 'border-amber-200 bg-amber-50 text-amber-800';
    case 'At Risk':
    case 'High':
      return 'border-[#F8A9A9] bg-[#FEE2E2] text-[#CC1F2E]';
    default:
      return 'border-slate-200 bg-slate-50 text-slate-600';
  }
};

const getSeverityLabel = (severity: string) => {
  const level = String(severity || '').toLowerCase();
  if (level === 'high' || level === 'critical') return 'High';
  if (level === 'medium' || level === 'moderate') return 'Medium';
  return 'Low';
};

const severityRank = (severity: string) => {
  const label = getSeverityLabel(severity);
  return label === 'High' ? 0 : label === 'Medium' ? 1 : 2;
};

const formatFlagType = (type: string) =>
  String(type || '')
    .replace(/[_-]+/g, ' ')
    .trim()
    .replace(/^\w/, (char) => char.toUpperCase());

const dayKey = (date: Date) =>
  `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;

const toTime = (value: unknown) => {
  if (!value) return NaN;
  return new Date(value as string).getTime();
};

const formatRelative = (time: number) => {
  const minutes = Math.max(0, Math.floor((Date.now() - time) / 60000));
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(time).toLocaleDateString();
};

const actorName = (value: any) =>
  value?.login || value?.name || (typeof value === 'string' ? value : '') || 'contributor';

const initialsOf = (name: string) =>
  name
    .replace(/[^a-zA-Z0-9 ]+/g, ' ')
    .trim()
    .split(/\s+/)
    .map((part) => part[0])
    .slice(0, 2)
    .join('')
    .toUpperCase() || 'U';

const Panel: React.FC<{
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
  className?: string;
  children: React.ReactNode;
}> = ({ title, subtitle, action, className = '', children }) => (
  <section
    className={`flex flex-col rounded-2xl border bg-white p-5 sm:p-6 ${className}`}
    style={{ borderColor: BORDER }}
  >
    <header className="flex items-start justify-between gap-3">
      <div className="min-w-0">
        <h2 className="font-display text-lg font-semibold leading-tight text-slate-900">
          {title}
        </h2>
        {subtitle && (
          <p className="mt-1 text-xs text-slate-500">{subtitle}</p>
        )}
      </div>
      {action}
    </header>
    <div className="mt-5 flex min-h-0 flex-1 flex-col">{children}</div>
  </section>
);

const PanelLink: React.FC<{ label: string; onClick: () => void }> = ({
  label,
  onClick,
}) => (
  <button
    type="button"
    onClick={onClick}
    className="inline-flex shrink-0 items-center gap-1 rounded-md px-2 py-1 text-xs font-semibold text-[#0B6B63] hover:bg-[#CDEFE6]"
  >
    {label}
    <ArrowRight className="h-3.5 w-3.5" />
  </button>
);

const EmptyNote: React.FC<{
  icon: React.ElementType;
  title: string;
  text: string;
}> = ({ icon: Icon, title, text }) => (
  <div className="flex flex-1 flex-col items-center justify-center gap-2 rounded-xl bg-[#EAF8F3] px-4 py-8 text-center">
    <Icon className="h-6 w-6 text-[#0B6B63]" />
    <p className="text-sm font-semibold text-slate-800">{title}</p>
    <p className="max-w-[260px] text-xs text-slate-500">{text}</p>
  </div>
);

const ShieldEmblem: React.FC<{
  score: number | null;
  status: string;
  color: string;
  ready: boolean;
}> = ({ score, status, color, ready }) => {
  const safe = score !== null ? Math.min(100, Math.max(0, score)) : 0;
  const offset = ready ? ((100 - safe) / 100) * 128 : 128;

  return (
    <div
      className="relative mx-auto h-[200px] w-[172px] shrink-0 sm:h-[230px] sm:w-[198px]"
      role="img"
      aria-label={`Project health score: ${score ?? 'No data'}, status ${status}`}
    >
      <svg viewBox="0 0 120 140" className="h-full w-full">
        <defs>
          <clipPath id="kavach-shield-clip">
            <path d="M60 6 L110 24 V66 C110 100 88 122 60 134 C32 122 10 100 10 66 V24 Z" />
          </clipPath>
        </defs>

        <path
          d="M60 6 L110 24 V66 C110 100 88 122 60 134 C32 122 10 100 10 66 V24 Z"
          fill="rgba(255,255,255,0.08)"
        />

        <g clipPath="url(#kavach-shield-clip)">
          <rect
            x="0"
            y="6"
            width="120"
            height="128"
            fill={color}
            opacity="0.92"
            style={{
              transform: `translateY(${offset}px)`,
              transition: 'transform 1.4s cubic-bezier(0.22, 1, 0.36, 1)',
            }}
            className="motion-reduce:!transition-none"
          />
        </g>

        <path
          d="M60 6 L110 24 V66 C110 100 88 122 60 134 C32 122 10 100 10 66 V24 Z"
          fill="none"
          stroke="rgba(255,255,255,0.85)"
          strokeWidth="2"
          strokeLinejoin="round"
        />
        <path
          d="M60 16 L101 30 V66 C101 94 83 113 60 124 C37 113 19 94 19 66 V30 Z"
          fill="none"
          stroke="rgba(255,255,255,0.28)"
          strokeWidth="1"
          strokeLinejoin="round"
        />
      </svg>

      <div className="absolute inset-0 flex flex-col items-center justify-center pb-3 text-center text-white">
        <span className="font-display text-5xl font-extrabold tabular-nums leading-none sm:text-6xl">
          {score !== null ? score : '--'}
        </span>
        <span className="mt-2 text-xs font-semibold tracking-wide text-white/90">
          {status}
        </span>
      </div>
    </div>
  );
};

const Plate: React.FC<{
  icon: React.ElementType;
  label: string;
  score: number | null | undefined;
  status: string | undefined;
  detail: string;
}> = ({ icon: Icon, label, score, status, detail }) => {
  const hasScore = score !== null && score !== undefined;
  const safe = hasScore ? Math.min(100, Math.max(0, score)) : 0;
  const color = status ? getStatusColor(status) : MUTED;

  return (
    <div
      className="flex flex-col rounded-2xl border bg-white p-4 sm:p-5"
      style={{ borderColor: BORDER }}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2.5">
          <span
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg"
            style={{ backgroundColor: `${color}1A`, color }}
          >
            <Icon className="h-4 w-4" />
          </span>
          <span className="truncate text-sm font-semibold text-slate-800">
            {label}
          </span>
        </div>

        {status && (
          <span
            className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-semibold ${getStatusBadge(status)}`}
          >
            {status}
          </span>
        )}
      </div>

      <div className="mt-4 flex items-baseline gap-1">
        <span className="font-display text-4xl font-extrabold tabular-nums leading-none text-slate-900">
          {hasScore ? Math.round(score) : '--'}
        </span>
        {hasScore && (
          <span className="text-sm font-medium text-slate-500">/ 100</span>
        )}
      </div>

      <div
        className="mt-4 h-1.5 w-full overflow-hidden rounded-full"
        style={{ backgroundColor: TRACK }}
        role="progressbar"
        aria-label={label}
        aria-valuenow={hasScore ? Math.round(safe) : undefined}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div
          className="h-full rounded-full"
          style={{ width: `${safe}%`, backgroundColor: color }}
        />
      </div>

      <p className="mt-3 text-xs leading-relaxed text-slate-500">{detail}</p>
    </div>
  );
};

export const ProjectOverview: React.FC<ProjectOverviewProps> = ({
  project,
  onNavigate,
  onRefreshProject,
}) => {
  const [healthSummary, setHealthSummary] =
    useState<HealthSummaryData | null>(null);
  const [metricsBreakdown, setMetricsBreakdown] =
    useState<MetricsBreakdownData | null>(null);
  const [commits, setCommits] = useState<any[]>([]);
  const [prs, setPrs] = useState<any[]>([]);
  const [issues, setIssues] = useState<any[]>([]);
  const [contributors, setContributors] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncFeedback, setSyncFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [shieldReady, setShieldReady] = useState(false);

  const asList = (value: unknown): any[] => (Array.isArray(value) ? value : []);

  const fetchMetrics = async (projectId: string) => {
    setIsLoading(true);
    setError(null);

    try {
      const [summary, breakdown, commitList, prList, issueList, people] =
        await Promise.all([
          metricsApi.getHealthSummary(projectId).catch(() => null),
          metricsApi.getMetricsBreakdown(projectId).catch(() => null),
          dataSyncApi.getCommits(projectId, 500).catch(() => []),
          dataSyncApi.getPRs(projectId, 'all').catch(() => []),
          dataSyncApi.getIssues(projectId, 'all').catch(() => []),
          dataSyncApi.getContributors(projectId).catch(() => []),
        ]);

      setHealthSummary(summary);
      setMetricsBreakdown(breakdown);
      setCommits(asList(commitList));
      setPrs(asList(prList));
      setIssues(asList(issueList));
      setContributors(asList(people));
    } catch (err: unknown) {
      setError(
        err instanceof Error
          ? err.message
          : 'Failed to fetch project metrics.'
      );
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (project?.id) {
      fetchMetrics(project.id);
    } else {
      setHealthSummary(null);
      setMetricsBreakdown(null);
      setCommits([]);
      setPrs([]);
      setIssues([]);
      setContributors([]);
    }
  }, [project?.id]);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => setShieldReady(true));
    return () => window.cancelAnimationFrame(frame);
  }, []);

  const handleSyncAll = async () => {
    if (!project?.id) return;

    setIsSyncing(true);
    setSyncFeedback(
      'Synchronizing commits, PRs, issues and contributors from GitHub...'
    );

    try {
      const results = await Promise.allSettled([
        dataSyncApi.syncCommits(
          project.id,
          project.default_branch || 'main'
        ),
        dataSyncApi.syncPRs(project.id),
        dataSyncApi.syncIssues(project.id),
        dataSyncApi.syncContributors(project.id),
        dataSyncApi.syncMilestones(project.id),
      ]);

      const serviceNames = ['Commits', 'PRs', 'Issues', 'Contributors', 'Milestones'];
      const failedServices = results
        .map((res, idx) => (res.status === 'rejected' ? serviceNames[idx] : null))
        .filter((name): name is string => name !== null);

      if (failedServices.length === 0) {
        setSyncFeedback('Synchronization complete! Refreshing metrics...');
      } else if (failedServices.length === serviceNames.length) {
        setSyncFeedback('Synchronization failed across all telemetry services.');
      } else {
        setSyncFeedback(
          `Sync completed with warnings: ${failedServices.join(', ')} failed to sync.`
        );
      }
      await fetchMetrics(project.id);

      if (onRefreshProject) {
        onRefreshProject();
      }

      setTimeout(() => setSyncFeedback(null), 3500);
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : 'Partial sync completed.';

      setSyncFeedback(`Sync note: ${message}`);
      setTimeout(() => setSyncFeedback(null), 4000);
    } finally {
      setIsSyncing(false);
    }
  };

  const heatmap = useMemo(() => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    const start = new Date(today);
    start.setDate(today.getDate() - today.getDay() - (HEATMAP_WEEKS - 1) * 7);

    const cells: { date: Date; key: string; count: number }[] = [];
    for (
      const cursor = new Date(start);
      cursor <= today;
      cursor.setDate(cursor.getDate() + 1)
    ) {
      const date = new Date(cursor);
      cells.push({ date, key: dayKey(date), count: 0 });
    }

    const lookup = new Map(cells.map((cell) => [cell.key, cell]));

    commits.forEach((commit) => {
      const time = toTime(commit?.timestamp || commit?.date || commit?.authored_date || commit?.created_at);
      if (Number.isNaN(time)) return;
      const bucket = lookup.get(dayKey(new Date(time)));
      if (bucket) bucket.count += 1;
    });

    const total = cells.reduce((sum, cell) => sum + cell.count, 0);
    const peak = cells.reduce((max, cell) => Math.max(max, cell.count), 0);
    const activeDays = cells.filter((cell) => cell.count > 0).length;

    const byWeekday = Array.from({ length: 7 }, () => 0);
    cells.forEach((cell) => {
      byWeekday[cell.date.getDay()] += cell.count;
    });
    const busiestIndex = byWeekday.indexOf(Math.max(...byWeekday));

    return {
      cells,
      total,
      peak,
      activeDays,
      busiest: total > 0 ? WEEKDAYS[busiestIndex] : null,
    };
  }, [commits]);

  const feed = useMemo(() => {
    const items: FeedItem[] = [];

    commits.forEach((commit, index) => {
      const at = toTime(commit?.timestamp || commit?.date || commit?.authored_date || commit?.created_at);
      if (Number.isNaN(at)) return;
      items.push({
        key: `c-${commit?.sha || index}`,
        kind: 'commit',
        title: String(commit?.message || 'Commit with no message').split('\n')[0],
        actor: actorName(commit?.author) || commit?.author_name || 'contributor',
        at,
        ref: commit?.sha ? String(commit.sha).slice(0, 7) : undefined,
      });
    });

    prs.forEach((pr, index) => {
      const at = toTime(pr?.merged_at || pr?.updated_at || pr?.created_at);
      if (Number.isNaN(at)) return;
      items.push({
        key: `p-${pr?.number || pr?.pr_number || index}`,
        kind: 'pr',
        title: String(pr?.title || 'Untitled pull request'),
        actor: actorName(pr?.author),
        at,
        state: String(pr?.state || 'open').toLowerCase(),
        ref: `#${pr?.number || pr?.pr_number || ''}`,
      });
    });

    issues.forEach((issue, index) => {
      const at = toTime(issue?.updated_at || issue?.created_at);
      if (Number.isNaN(at)) return;
      items.push({
        key: `i-${issue?.number || issue?.issue_number || index}`,
        kind: 'issue',
        title: String(issue?.title || 'Untitled issue'),
        actor: actorName(issue?.author),
        at,
        state: String(issue?.state || 'open').toLowerCase(),
        ref: `#${issue?.number || issue?.issue_number || ''}`,
      });
    });

    return items.sort((a, b) => b.at - a.at).slice(0, 8);
  }, [commits, prs, issues]);

  const topContributors = useMemo(() => {
    const rows = contributors.map((person) => ({
      name: person?.github_username || person?.login || person?.name || person?.username || 'contributor',
      url: person?.html_url as string | undefined,
      count: Number(person?.contributions || person?.commits || 1),
    }));
    const total = rows.reduce((sum, row) => sum + row.count, 0);
    return rows
      .sort((a, b) => b.count - a.count)
      .slice(0, 5)
      .map((row) => ({ ...row, share: total > 0 ? (row.count / total) * 100 : 0 }));
  }, [contributors]);

  if (!project) {
    return (
      <div className="mx-auto max-w-4xl p-5 sm:p-8">
        <div
          className="space-y-4 rounded-2xl border bg-white p-8 text-center"
          style={{ borderColor: BORDER }}
        >
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-lg bg-[#CDEFE6] text-[#0B6B63]">
            <Layers className="h-6 w-6" />
          </div>

          <h2 className="text-xl font-semibold text-slate-900">
            No Project Selected
          </h2>

          <p className="mx-auto max-w-md text-sm text-slate-500">
            You don't have an active project selected or no projects have
            been created yet.
          </p>

          <button
            type="button"
            onClick={() => onNavigate('create-project')}
            className="inline-flex items-center gap-2 rounded-md bg-[#0B6B63] px-5 py-2.5 text-sm font-semibold text-white hover:bg-[#084F49]"
          >
            Create First Project
            <ArrowRight className="h-4 w-4" />
          </button>
        </div>
      </div>
    );
  }

  if (!project.repo_url) {
    return (
      <div className="mx-auto max-w-4xl p-5 sm:p-8">
        <div
          className="space-y-4 rounded-2xl border bg-white p-8 text-center"
          style={{ borderColor: BORDER }}
        >
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-lg bg-amber-50 text-amber-700">
            <GitPullRequest className="h-6 w-6" />
          </div>

          <h2 className="text-xl font-semibold text-slate-900">
            Connect a GitHub Repository
          </h2>

          <p className="mx-auto max-w-md text-sm text-slate-500">
            Project <strong className="text-slate-800">{project.name}</strong>{' '}
            is not connected to a GitHub repository. Connect a repository
            to ingest commits, pull requests, and health metrics.
          </p>

          <button
            type="button"
            onClick={() => onNavigate('connect-repo')}
            className="inline-flex items-center gap-2 rounded-md bg-[#0B6B63] px-5 py-2.5 text-sm font-semibold text-white hover:bg-[#084F49]"
          >
            Connect GitHub Repository
            <ArrowRight className="h-4 w-4" />
          </button>
        </div>
      </div>
    );
  }

  const bottlenecks = metricsBreakdown?.indicators?.bottlenecks;
  const workload = metricsBreakdown?.indicators?.workload;
  const staleIssues = metricsBreakdown?.indicators?.stale_issues;
  const scheduleRisk = metricsBreakdown?.indicators?.schedule_risk;

  const healthScore =
    healthSummary?.health_score !== null &&
    healthSummary?.health_score !== undefined
      ? Math.floor(healthSummary.health_score)
      : null;

  const healthStatus = healthSummary?.status || 'Insufficient Data';

  const openPRsCount = bottlenecks?.details?.open_prs_count ?? 0;
  const agingPRsCount = bottlenecks?.details?.aging_prs_count ?? 0;
  const staleIssuesCount = staleIssues?.details?.stale_issues_count ?? 0;
  const openIssuesCount = staleIssues?.details?.open_issues_count ?? 0;
  const totalContributorsCount = workload?.details?.total_contributors ?? 0;
  const topContributorShare = workload?.details?.top_contributor_percentage;
  const overdueCount = scheduleRisk?.details?.overdue_count ?? 0;
  const totalPlanned = scheduleRisk?.details?.total_planned_items ?? 0;
  const totalCompleted = scheduleRisk?.details?.total_completed_items ?? 0;

  const isInsufficient =
    healthStatus === 'Insufficient Data' || healthScore === null;

  const scoreColor = getStatusColor(healthStatus);

  const activeFlags = [...(healthSummary?.active_flags || [])].sort(
    (a, b) => severityRank(a.severity) - severityRank(b.severity)
  );
  const flagTotals = {
    high: healthSummary?.flags_count?.high ?? 0,
    medium: healthSummary?.flags_count?.medium ?? 0,
    low: healthSummary?.flags_count?.low ?? 0,
  };
  const flagSum = flagTotals.high + flagTotals.medium + flagTotals.low;

  const freshness = healthSummary?.data_freshness || 'unknown';
  const lastSynced = healthSummary?.last_synced_at
    ? new Date(healthSummary.last_synced_at).toLocaleString()
    : null;

  const feedIcon = {
    commit: GitCommit,
    pr: GitPullRequest,
    issue: CircleDot,
  } as const;

  const feedKindLabel = {
    commit: 'committed',
    pr: 'pull request',
    issue: 'issue',
  } as const;

  const stateBadge = (state: string) =>
    state === 'merged' || state === 'closed'
      ? state === 'merged'
        ? 'border-[#86EFAC] bg-[#DCFCE7] text-[#15803D]'
        : 'border-slate-200 bg-slate-50 text-slate-600'
      : 'border-[#9ED4C8] bg-[#EAF8F3] text-[#0B6B63]';

  return (
    <div className="mx-auto max-w-[1500px] p-4 sm:p-6 lg:p-8">

      {(isLoading || error || syncFeedback || (isInsufficient && !isLoading)) && (
        <div className="mb-4 space-y-3">
          {isLoading && (
            <div className="flex items-center gap-2 rounded-xl border border-[#9ED4C8] bg-white px-4 py-3 text-sm text-slate-600">
              <RefreshCw className="h-4 w-4 animate-spin text-[#0B6B63]" />
              Loading project metrics...
            </div>
          )}

          {error && (
            <div className="flex flex-col justify-between gap-3 rounded-xl border border-[#F8A9A9] bg-white p-4 sm:flex-row sm:items-center">
              <div className="flex items-start gap-3">
                <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-[#CC1F2E]" />
                <div>
                  <p className="text-sm font-semibold text-[#CC1F2E]">
                    Failed to load project telemetry
                  </p>
                  <p className="mt-1 text-sm text-slate-600">{error}</p>
                </div>
              </div>

              <button
                type="button"
                onClick={() => project.id && fetchMetrics(project.id)}
                className="shrink-0 rounded-md bg-[#CC1F2E] px-3 py-2 text-xs font-semibold text-white hover:bg-[#CC1F2E]"
              >
                Retry
              </button>
            </div>
          )}

          {syncFeedback && (
            <div className="flex items-start gap-2 rounded-xl border border-[#9ED4C8] bg-white px-4 py-3 text-sm text-slate-700">
              <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-[#0B6B63]" />
              <span>{syncFeedback}</span>
            </div>
          )}

          {isInsufficient && !isLoading && (
            <div className="flex flex-col justify-between gap-4 rounded-xl border border-amber-200 bg-white p-4 sm:flex-row sm:items-center">
              <div className="flex items-start gap-3">
                <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" />

                <div>
                  <p className="text-sm font-semibold text-amber-800">
                    Insufficient Telemetry Data
                  </p>

                  <p className="mt-1 text-sm text-slate-600">
                    GitHub telemetry has not been synchronized yet for this
                    project. Synchronize the repository to ingest commits,
                    pull requests, and issues.
                  </p>
                </div>
              </div>

              <button
                type="button"
                onClick={handleSyncAll}
                disabled={isSyncing}
                className="w-full shrink-0 rounded-md bg-amber-700 px-4 py-2 text-xs font-semibold text-white hover:bg-amber-800 disabled:opacity-60 sm:w-auto"
              >
                {isSyncing ? 'Syncing...' : 'Sync Telemetry Now'}
              </button>
            </div>
          )}
        </div>
      )}

      <section className="hero-vibrant relative overflow-hidden rounded-3xl px-5 pb-20 pt-7 text-white sm:px-8 sm:pb-24 sm:pt-9 lg:px-12">
        <div className="relative z-10 grid items-center gap-8 lg:grid-cols-[minmax(0,1fr)_auto] lg:gap-14">
          <div className="min-w-0 text-center lg:text-left">
            <div className="flex flex-wrap items-center justify-center gap-2 lg:justify-start">
              <span className="rounded-full border border-white/25 bg-white/10 px-3 py-1 font-mono text-xs font-medium text-white/90">
                {project.default_branch || 'main'}
              </span>

              <a
                href={project.repo_url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 break-all rounded-full border border-white/25 bg-white/10 px-3 py-1 text-xs font-medium text-white/90 hover:bg-white/20"
              >
                {project.repo_url.replace(/^https:\/\/github\.com\//, '')}
                <ExternalLink className="h-3 w-3 shrink-0" />
              </a>
            </div>

            <h1 className="font-display mt-4 break-words text-3xl font-extrabold leading-[1.05] tracking-tight text-white sm:text-5xl">
              {project.name}
            </h1>

            <p className="mx-auto mt-4 max-w-xl text-sm leading-relaxed text-white/80 sm:text-base lg:mx-0">
              {healthSummary?.summary_statement?.match(/^.*?\.(?=\s|$)/)?.[0] ||
                healthSummary?.summary_statement ||
                'Synchronize repository to evaluate live health statement.'}
            </p>

            <div className="mt-5 flex flex-wrap items-center justify-center gap-x-5 gap-y-2 text-xs text-white/75 lg:justify-start">
              <span className="inline-flex items-center gap-1.5">
                <Clock className="h-3.5 w-3.5" />
                {lastSynced ? `Synced ${lastSynced}` : 'Not synced yet'}
              </span>

              <span className="inline-flex items-center gap-1.5">
                <span
                  className="h-2 w-2 rounded-full"
                  style={{
                    backgroundColor:
                      freshness === 'fresh'
                        ? TEAL
                        : freshness === 'stale'
                          ? AMBER
                          : MUTED,
                  }}
                />
                {freshness === 'fresh'
                  ? 'Fresh data'
                  : freshness === 'stale'
                    ? 'Stale data'
                    : 'Freshness unknown'}
              </span>
            </div>

            <div className="mt-6 flex flex-wrap items-center justify-center gap-3 lg:justify-start">
              <button
                type="button"
                onClick={handleSyncAll}
                disabled={isSyncing}
                className="inline-flex items-center gap-2 rounded-lg bg-white px-4 py-2.5 text-sm font-semibold text-[#0B6B63] hover:bg-[#CDEFE6] disabled:cursor-not-allowed disabled:opacity-60"
              >
                <RefreshCw className={`h-4 w-4 ${isSyncing ? 'animate-spin' : ''}`} />
                {isSyncing ? 'Synchronizing...' : 'Sync Live Telemetry'}
              </button>

              <button
                type="button"
                onClick={() => onNavigate('health-analysis')}
                className="inline-flex items-center gap-2 rounded-lg border border-white/35 px-4 py-2.5 text-sm font-semibold text-white hover:bg-white/10"
              >
                Health breakdown
                <ArrowRight className="h-4 w-4" />
              </button>
            </div>
          </div>

          <div className="flex flex-col items-center gap-4">
            <ShieldEmblem
              score={healthScore}
              status={healthStatus}
              color={scoreColor}
              ready={shieldReady}
            />

            <div className="flex flex-wrap justify-center gap-2 text-[11px] font-semibold">
              <span className="rounded-full bg-white/15 px-2.5 py-1">
                {flagTotals.high} high
              </span>
              <span className="rounded-full bg-white/15 px-2.5 py-1">
                {flagTotals.medium} medium
              </span>
              <span className="rounded-full bg-white/15 px-2.5 py-1">
                {flagTotals.low} low
              </span>
            </div>
          </div>
        </div>
      </section>

      <section className="relative z-10 -mt-12 grid grid-cols-1 gap-4 px-2 sm:-mt-14 sm:grid-cols-2 lg:grid-cols-4 sm:px-4 lg:px-8">
        <Plate
          icon={GitPullRequest}
          label="Review flow"
          score={bottlenecks?.score}
          status={bottlenecks?.status}
          detail={`${openPRsCount} open pull request${openPRsCount === 1 ? '' : 's'}, ${agingPRsCount} waiting over 48h`}
        />

        <Plate
          icon={Users}
          label="Workload"
          score={workload?.score}
          status={workload?.status}
          detail={`${totalContributorsCount} active contributor${totalContributorsCount === 1 ? '' : 's'}${
            topContributorShare !== undefined && topContributorShare !== null
              ? `, top share ${topContributorShare}%`
              : ''
          }`}
        />

        <Plate
          icon={Timer}
          label="Issue freshness"
          score={staleIssues?.score}
          status={staleIssues?.status}
          detail={`${staleIssuesCount} stale of ${openIssuesCount} open issue${openIssuesCount === 1 ? '' : 's'}`}
        />

        <Plate
          icon={CalendarClock}
          label="Schedule velocity"
          score={scheduleRisk?.score}
          status={scheduleRisk?.status}
          detail={
            totalPlanned > 0
              ? `${totalCompleted} of ${totalPlanned} items done, ${overdueCount} overdue`
              : overdueCount > 0
                ? `${overdueCount} overdue milestone${overdueCount === 1 ? '' : 's'}`
                : 'No active milestone slippage'
          }
        />
      </section>

      <div className="mt-5 grid grid-cols-1 gap-4 sm:gap-5 xl:grid-cols-12">

        <Panel
          title="Commit rhythm"
          subtitle={`Daily commits across the last ${HEATMAP_WEEKS} weeks`}
          className="xl:col-span-8"
          action={<PanelLink label="Activity" onClick={() => onNavigate('activity')} />}
        >
          {heatmap.total === 0 ? (
            <EmptyNote
              icon={GitCommit}
              title="No commits in this period"
              text="Synchronize telemetry to load recent commit history."
            />
          ) : (
            <>
              <dl className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="rounded-xl bg-[#EAF8F3] px-4 py-3">
                  <dt className="text-xs text-slate-500">Commits</dt>
                  <dd className="font-display text-2xl font-bold tabular-nums text-slate-900">
                    {heatmap.total}
                  </dd>
                </div>
                <div className="rounded-xl bg-[#EAF8F3] px-4 py-3">
                  <dt className="text-xs text-slate-500">Active days</dt>
                  <dd className="font-display text-2xl font-bold tabular-nums text-slate-900">
                    {heatmap.activeDays}
                  </dd>
                </div>
                <div className="rounded-xl bg-[#EAF8F3] px-4 py-3">
                  <dt className="text-xs text-slate-500">Busiest day</dt>
                  <dd className="font-display truncate text-2xl font-bold text-slate-900">
                    {heatmap.busiest}
                  </dd>
                </div>
              </dl>

              <div className="mt-5 w-full overflow-x-auto pb-2">
                <div
                  className="grid min-w-[500px] grid-flow-col grid-rows-7 gap-[3px] sm:gap-1"
                  style={{ gridAutoColumns: 'minmax(0, 1fr)' }}
                  role="img"
                  aria-label={`${heatmap.total} commits over the last ${HEATMAP_WEEKS} weeks`}
                >
                  {heatmap.cells.map((cell) => {
                    const level =
                      cell.count === 0
                        ? 0
                        : Math.max(1, Math.ceil((cell.count / heatmap.peak) * 4));

                    return (
                      <div
                        key={cell.key}
                        title={`${cell.date.toLocaleDateString(undefined, {
                          month: 'short',
                          day: 'numeric',
                        })}: ${cell.count} commit${cell.count === 1 ? '' : 's'}`}
                        className="h-3.5 rounded-[3px] sm:h-5"
                        style={{ backgroundColor: HEAT_LEVELS[level] }}
                      />
                    );
                  })}
                </div>
              </div>

              <div className="mt-3 flex items-center justify-between text-[11px] text-slate-500">
                <span>
                  {heatmap.cells[0].date.toLocaleDateString(undefined, {
                    month: 'short',
                    day: 'numeric',
                  })}
                </span>

                <span className="inline-flex items-center gap-1.5">
                  Fewer
                  {HEAT_LEVELS.map((color, index) => (
                    <span
                      key={index}
                      className="h-2.5 w-2.5 rounded-[2px]"
                      style={{ backgroundColor: color }}
                    />
                  ))}
                  More
                </span>

                <span>Today</span>
              </div>
            </>
          )}
        </Panel>

        <Panel
          title="Risk radar"
          subtitle="Active automated risk triggers"
          className="xl:col-span-4"
          action={
            <PanelLink label="Investigate" onClick={() => onNavigate('risk-analysis')} />
          }
        >
          {flagSum > 0 && (
            <div
              className="mb-4 flex h-2 w-full overflow-hidden rounded-full"
              style={{ backgroundColor: TRACK }}
              role="img"
              aria-label={`${flagTotals.high} high, ${flagTotals.medium} medium, ${flagTotals.low} low risk flags`}
            >
              <div style={{ width: `${(flagTotals.high / flagSum) * 100}%`, backgroundColor: CRIMSON }} />
              <div style={{ width: `${(flagTotals.medium / flagSum) * 100}%`, backgroundColor: AMBER }} />
              <div style={{ width: `${(flagTotals.low / flagSum) * 100}%`, backgroundColor: BRAND }} />
            </div>
          )}

          {activeFlags.length === 0 ? (
            <EmptyNote
              icon={ShieldAlert}
              title="No active risk flags"
              text="Nothing needs attention right now."
            />
          ) : (
            <ul className="space-y-2.5">
              {activeFlags.slice(0, 5).map((flag, index) => {
                const label = getSeverityLabel(flag.severity);
                const color = getStatusColor(label);

                return (
                  <li
                    key={flag.id || `${flag.type}-${index}`}
                    className="rounded-lg bg-[#EAF8F3]/70 py-2.5 pl-3.5 pr-3"
                    style={{ borderLeft: `3px solid ${color}` }}
                  >
                    <p className="break-words text-[13px] font-medium leading-snug text-slate-800">
                      {flag.message}
                    </p>
                    <p className="mt-1 flex items-center gap-2 text-[11px] text-slate-500">
                      <span className="font-semibold" style={{ color }}>
                        {label}
                      </span>
                      <span>{formatFlagType(flag.type)}</span>
                    </p>
                  </li>
                );
              })}
            </ul>
          )}

          {activeFlags.length > 5 && (
            <button
              type="button"
              onClick={() => onNavigate('risk-analysis')}
              className="mt-3 self-start text-xs font-semibold text-[#0B6B63] hover:underline"
            >
              Show all {activeFlags.length} risks
            </button>
          )}
        </Panel>

        <Panel
          title="Recent activity"
          subtitle="Latest commits, pull requests and issues"
          className="xl:col-span-8"
          action={<PanelLink label="All activity" onClick={() => onNavigate('activity')} />}
        >
          {feed.length === 0 ? (
            <EmptyNote
              icon={Layers}
              title="No activity yet"
              text="Synchronize telemetry to see what your team has been working on."
            />
          ) : (
            <ol className="relative space-y-0.5">
              <span
                className="absolute bottom-4 left-[17px] top-4 w-px"
                style={{ backgroundColor: TRACK }}
                aria-hidden="true"
              />

              {feed.map((item) => {
                const Icon = feedIcon[item.kind];

                return (
                  <li key={item.key} className="relative flex gap-3 py-2">
                    <span
                      className="relative z-10 flex h-9 w-9 shrink-0 items-center justify-center rounded-full border bg-white text-[#0B6B63]"
                      style={{ borderColor: BORDER }}
                    >
                      <Icon className="h-4 w-4" />
                    </span>

                    <div className="min-w-0 flex-1">
                      <p className="break-words text-sm font-medium leading-snug text-slate-900">
                        {item.title}
                      </p>
                      <p className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-slate-500">
                        <span className="font-medium text-slate-600">
                          {item.actor}
                        </span>
                        <span>{feedKindLabel[item.kind]}</span>
                        {item.ref && (
                          <span className="font-mono text-[11px]">{item.ref}</span>
                        )}
                        {item.state && (
                          <span
                            className={`rounded-full border px-2 py-px text-[10px] font-semibold capitalize ${stateBadge(item.state)}`}
                          >
                            {item.state}
                          </span>
                        )}
                      </p>
                    </div>

                    <span className="shrink-0 pt-0.5 text-xs text-slate-500">
                      {formatRelative(item.at)}
                    </span>
                  </li>
                );
              })}
            </ol>
          )}
        </Panel>

        <Panel
          title="Who is building"
          subtitle="Share of recorded contributions"
          className="xl:col-span-4"
          action={<PanelLink label="Team" onClick={() => onNavigate('contributors')} />}
        >
          {topContributors.length === 0 ? (
            <EmptyNote
              icon={Users}
              title="No contributors yet"
              text="Synchronize contributors to see who is driving the work."
            />
          ) : (
            <ul className="space-y-4">
              {topContributors.map((person) => (
                <li key={person.name}>
                  <div className="flex items-center gap-3">
                    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#CDEFE6] text-xs font-bold text-[#0B6B63]">
                      {initialsOf(person.name)}
                    </span>

                    <div className="min-w-0 flex-1">
                      <div className="flex items-baseline justify-between gap-2">
                        <span className="truncate text-sm font-semibold text-slate-800">
                          {person.name}
                        </span>
                        <span className="shrink-0 text-xs font-semibold tabular-nums text-slate-600">
                          {Math.round(person.share)}%
                        </span>
                      </div>

                      <div
                        className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full"
                        style={{ backgroundColor: TRACK }}
                      >
                        <div
                          className="h-full rounded-full"
                          style={{
                            width: `${person.share}%`,
                            backgroundColor: person.share >= 60 ? CRIMSON : BRAND,
                          }}
                        />
                      </div>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>
    </div>
  );
};
