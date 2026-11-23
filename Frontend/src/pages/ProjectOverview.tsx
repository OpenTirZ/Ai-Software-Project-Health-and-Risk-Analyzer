import React, { useState, useEffect } from 'react';

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
  AlertCircle,
  Layers,
  CheckCircle2,
  Activity,
  ShieldAlert,
  Users,
} from 'lucide-react';

interface ProjectOverviewProps {
  project: ProjectResponse | null;
  onNavigate: (view: PageView) => void;
  onRefreshProject?: () => void;
}

const TEAL = '#16A34A';
const CRIMSON = '#CC1F2E';
const BORDER = '#9ED4C8';

export const ProjectOverview: React.FC<ProjectOverviewProps> = ({
  project,
  onNavigate,
  onRefreshProject,
}) => {
  const [healthSummary, setHealthSummary] =
    useState<HealthSummaryData | null>(null);
  const [metricsBreakdown, setMetricsBreakdown] =
    useState<MetricsBreakdownData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncFeedback, setSyncFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchMetrics = async (projectId: string) => {
    setIsLoading(true);
    setError(null);

    try {
      const [summary, breakdown] = await Promise.all([
        metricsApi.getHealthSummary(projectId).catch(() => null),
        metricsApi.getMetricsBreakdown(projectId).catch(() => null),
      ]);

      setHealthSummary(summary);
      setMetricsBreakdown(breakdown);
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
    }
  }, [project?.id]);

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

  const cardClass = 'rounded-lg border bg-white p-4 sm:p-5';

  const secondaryText = 'text-sm text-slate-500';

  const getScoreColor = (status: string) => {
    switch (status) {
      case 'Good':
        return 'text-[#15803D]';
      case 'Caution':
        return 'text-amber-700';
      case 'At Risk':
        return 'text-[#CC1F2E]';
      default:
        return 'text-slate-500';
    }
  };

  const getScoreBg = (status: string) => {
    switch (status) {
      case 'Good':
        return TEAL;
      case 'Caution':
        return '#B45309';
      case 'At Risk':
        return CRIMSON;
      default:
        return '#5F7C79';
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

  const MetricBar: React.FC<{
    label: string;
    score: number | null | undefined;
    color: string;
  }> = ({ label, score, color }) => {
    const hasScore = score !== null && score !== undefined;
    const safeScore = hasScore
      ? Math.min(100, Math.max(0, score))
      : 0;

    return (
      <div className="space-y-1.5">
        <div className="flex items-center justify-between gap-3 text-xs">
          <span className="font-medium text-slate-600">{label}</span>
          <span className="font-semibold tabular-nums text-slate-900">
            {hasScore ? `${Math.round(score)}%` : 'No Data'}
          </span>
        </div>

        <div
          className="h-2 w-full overflow-hidden rounded-full bg-slate-100"
          role="progressbar"
          aria-label={label}
          aria-valuenow={hasScore ? Math.round(safeScore) : undefined}
          aria-valuemin={0}
          aria-valuemax={100}
        >
          <div
            className="h-full rounded-full"
            style={{
              width: `${safeScore}%`,
              backgroundColor: color,
            }}
          />
        </div>
      </div>
    );
  };

  const MetricCard: React.FC<{
    label: string;
    value: React.ReactNode;
    description: string;
    valueColor?: string;
  }> = ({ label, value, description, valueColor = '#0E2A2A' }) => (
    <div className={cardClass} style={{ borderColor: BORDER }}>
      <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
        {label}
      </p>

      <div
        className="my-3 text-2xl font-bold tabular-nums"
        style={{ color: valueColor }}
      >
        {value}
      </div>

      <p className="text-xs leading-relaxed text-slate-500">
        {description}
      </p>
    </div>
  );

  if (!project) {
    return (
      <div className="mx-auto max-w-4xl p-5 sm:p-8">
        <div
          className="space-y-4 rounded-lg border bg-white p-8 text-center"
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
          className="space-y-4 rounded-lg border bg-white p-8 text-center"
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
      ? Math.round(healthSummary.health_score)
      : null;

  const healthStatus = healthSummary?.status || 'Insufficient Data';

  const openPRsCount = bottlenecks?.details?.open_prs_count ?? 0;
  const agingPRsCount = bottlenecks?.details?.aging_prs_count ?? 0;
  const staleIssuesCount = staleIssues?.details?.stale_issues_count ?? 0;
  const totalContributorsCount =
    workload?.details?.total_contributors ?? 0;

  const potentialBottlenecks =
    (healthSummary?.flags_count?.high ?? 0) +
    (healthSummary?.flags_count?.medium ?? 0);

  const isInsufficient =
    healthStatus === 'Insufficient Data' || healthScore === null;

  const overdueCount = scheduleRisk?.details?.overdue_count ?? 0;
  const totalPlanned = scheduleRisk?.details?.total_planned_items ?? 0;
  const totalCompleted =
    scheduleRisk?.details?.total_completed_items ?? 0;

  const scoreColor = getScoreBg(healthStatus);
  const circumference = 2 * Math.PI * 48;
  const safeHealthScore =
    healthScore !== null
      ? Math.min(100, Math.max(0, healthScore))
      : 0;

  return (
    <div className="mx-auto max-w-[1500px] space-y-5 p-4 sm:p-6 lg:p-8">

      <section className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
              {project.name}
            </h1>

            <span className="rounded-md border border-[#9ED4C8] bg-white px-2.5 py-1 font-mono text-xs font-medium text-slate-600">
              {project.default_branch || 'main'}
            </span>
          </div>

          <p className="mt-1 break-words text-sm text-slate-500">
            Repository:{' '}
            <a
              href={project.repo_url}
              target="_blank"
              rel="noreferrer"
              className="font-medium text-[#0B6B63] underline-offset-2 hover:underline"
            >
              {project.repo_url.replace(/^https:\/\/github\.com\//, '')}
            </a>
          </p>
        </div>

        <button
          type="button"
          onClick={handleSyncAll}
          disabled={isSyncing}
          className="inline-flex shrink-0 items-center justify-center gap-2 rounded-md bg-[#0B6B63] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#084F49] disabled:cursor-not-allowed disabled:opacity-60"
        >
          <RefreshCw className="h-4 w-4" />
          {isSyncing ? 'Synchronizing...' : 'Sync Live Telemetry'}
        </button>
      </section>

      {isLoading && (
        <div className="flex items-center gap-2 rounded-md border border-[#9ED4C8] bg-white px-4 py-3 text-sm text-slate-600">
          <RefreshCw className="h-4 w-4 text-[#0B6B63]" />
          Loading project metrics...
        </div>
      )}

      {error && (
        <div className="flex flex-col justify-between gap-3 rounded-md border border-[#F8A9A9] bg-white p-4 sm:flex-row sm:items-center">
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
        <div
          className="flex items-start gap-2 rounded-md border px-4 py-3 text-sm text-slate-700"
          style={{
            borderColor: BORDER,
            backgroundColor: '#FFFFFF',
          }}
        >
          <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-[#0B6B63]" />
          <span>{syncFeedback}</span>
        </div>
      )}

      {isInsufficient && !isLoading && (
        <div className="flex flex-col justify-between gap-4 rounded-md border border-amber-200 bg-white p-4 sm:flex-row sm:items-center">
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
            className="shrink-0 rounded-md bg-amber-700 px-4 py-2 text-xs font-semibold text-white hover:bg-amber-800 disabled:opacity-60"
          >
            {isSyncing ? 'Syncing...' : 'Sync Telemetry Now'}
          </button>
        </div>
      )}

      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-700">
            Project Metrics
          </h2>
          <span className="text-xs text-slate-500">
            Repository overview
          </span>
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-6">
          <MetricCard
            label="Project Health"
            value={healthScore !== null ? healthScore : '--'}
            description={
              healthSummary?.data_freshness === 'fresh'
                ? 'Fresh data (< 24h)'
                : `Freshness: ${healthSummary?.data_freshness || 'Unknown'}`
            }
            valueColor={scoreColor}
          />

          <MetricCard
            label="Schedule Risk"
            value={scheduleRisk?.status || 'N/A'}
            description={
              overdueCount > 0
                ? `${overdueCount} overdue milestone(s)`
                : 'No active milestone slippage'
            }
            valueColor={
              scheduleRisk?.status === 'High' ||
              scheduleRisk?.status === 'At Risk'
                ? CRIMSON
                : '#0E2A2A'
            }
          />

          <MetricCard
            label="Open Pull Requests"
            value={openPRsCount}
            description={
              agingPRsCount > 0
                ? `${agingPRsCount} aging (>48h)`
                : 'Review queue healthy'
            }
            valueColor={agingPRsCount > 0 ? '#B45309' : TEAL}
          />

          <MetricCard
            label="Stale Issues"
            value={staleIssuesCount}
            description={
              staleIssuesCount > 0
                ? 'Exceeds inactivity limit'
                : 'All issues active'
            }
            valueColor={staleIssuesCount > 0 ? CRIMSON : TEAL}
          />

          <MetricCard
            label="Bottlenecks"
            value={potentialBottlenecks}
            description={
              potentialBottlenecks > 0
                ? 'Actionable flags detected'
                : 'Zero blockers'
            }
            valueColor={potentialBottlenecks > 0 ? CRIMSON : TEAL}
          />

          <MetricCard
            label="Contributors"
            value={totalContributorsCount}
            description="Active contributors"
          />
        </div>
      </section>

      <section className="grid grid-cols-1 gap-4 xl:grid-cols-12">

        <div
          className="flex flex-col gap-5 rounded-lg border bg-white p-5 xl:col-span-6"
          style={{ borderColor: BORDER }}
        >
          <div
            className="flex flex-col justify-between gap-3 border-b pb-4 sm:flex-row sm:items-center"
            style={{ borderColor: BORDER }}
          >
            <div>
              <h2 className="text-lg font-semibold text-slate-900">
                Composite Health Index
              </h2>
              <p className={secondaryText}>
                Deterministic weighted score based on GitHub telemetry
              </p>
            </div>

            <button
              type="button"
              onClick={() => onNavigate('health-analysis')}
              className="inline-flex shrink-0 items-center gap-1 text-xs font-semibold text-[#0B6B63] hover:underline"
            >
              View Breakdown
              <ArrowRight className="h-3.5 w-3.5" />
            </button>
          </div>

          <div className="grid grid-cols-1 items-center gap-6 sm:grid-cols-2">

            <div className="flex flex-col items-center justify-center py-2">
              <div className="relative h-36 w-36">
                <svg
                  className="h-full w-full -rotate-90"
                  viewBox="0 0 120 120"
                  role="img"
                  aria-label={`Project health score: ${healthScore ?? 'No data'}`}
                >
                  <circle
                    cx="60"
                    cy="60"
                    r="48"
                    stroke="#CDEFE6"
                    strokeWidth="10"
                    fill="none"
                  />

                  <circle
                    cx="60"
                    cy="60"
                    r="48"
                    stroke={scoreColor}
                    strokeWidth="10"
                    strokeDasharray={circumference}
                    strokeDashoffset={
                      circumference * (1 - safeHealthScore / 100)
                    }
                    strokeLinecap="round"
                    fill="none"
                  />
                </svg>

                <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
                  <span className="text-4xl font-bold tabular-nums text-slate-900">
                    {healthScore !== null ? healthScore : '--'}
                  </span>

                  <span
                    className={`mt-1 text-[10px] font-semibold uppercase tracking-wider ${getScoreColor(healthStatus)}`}
                  >
                    {healthStatus}
                  </span>
                </div>
              </div>

              <p className="mt-3 text-xs text-slate-500">
                Overall project health
              </p>
            </div>

            <div className="space-y-5">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-700">
                Normalized Indicators
              </h3>

              <MetricBar
                label="Review Bottlenecks"
                score={bottlenecks?.score}
                color={TEAL}
              />

              <MetricBar
                label="Workload Balance"
                score={workload?.score}
                color="#084F49"
              />

              <MetricBar
                label="Issue Freshness"
                score={staleIssues?.score}
                color={TEAL}
              />

              <MetricBar
                label="Schedule Velocity"
                score={scheduleRisk?.score}
                color="#B45309"
              />
            </div>
          </div>

          <div
            className="border-t pt-4 text-sm leading-relaxed text-slate-600"
            style={{ borderColor: BORDER }}
          >
            {healthSummary?.summary_statement ||
              'Synchronize repository to evaluate live health statement.'}
          </div>
        </div>

        <div
          className="flex flex-col rounded-lg border bg-white p-5 xl:col-span-3"
          style={{ borderColor: BORDER }}
        >
          <div className="border-b pb-4" style={{ borderColor: BORDER }}>
            <div className="flex items-center gap-2">
              <ShieldAlert className="h-4 w-4 text-[#CC1F2E]" />
              <h2 className="text-lg font-semibold text-slate-900">
                Risk Signals
              </h2>
            </div>

            <p className="mt-1 text-xs text-slate-500">
              Active automated risk triggers
            </p>
          </div>

          <div className="my-4 flex-1 space-y-4">
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm text-slate-700">
                Aging PR Bottlenecks
              </span>
              <span
                className={`rounded border px-2 py-1 text-xs font-semibold ${
                  agingPRsCount > 0
                    ? 'border-[#F8A9A9] bg-[#FEE2E2] text-[#CC1F2E]'
                    : 'border-[#86EFAC] bg-[#DCFCE7] text-[#15803D]'
                }`}
              >
                {agingPRsCount}
              </span>
            </div>

            <div className="flex items-center justify-between gap-2">
              <span className="text-sm text-slate-700">
                Stale Issues (&gt;14d)
              </span>
              <span
                className={`rounded border px-2 py-1 text-xs font-semibold ${
                  staleIssuesCount > 0
                    ? 'border-amber-200 bg-amber-50 text-amber-800'
                    : 'border-[#86EFAC] bg-[#DCFCE7] text-[#15803D]'
                }`}
              >
                {staleIssuesCount}
              </span>
            </div>

            <div className="flex items-center justify-between gap-2">
              <span className="text-sm text-slate-700">
                Workload Concentration
              </span>
              <span
                className={`rounded border px-2 py-1 text-xs font-semibold ${getStatusBadge(workload?.status || 'Good')}`}
              >
                {workload?.status || 'Good'}
              </span>
            </div>

            <div className="flex items-center justify-between gap-2">
              <span className="text-sm text-slate-700">
                Milestone Slippage
              </span>
              <span
                className={`rounded border px-2 py-1 text-xs font-semibold ${getStatusBadge(scheduleRisk?.status || 'Low')}`}
              >
                {scheduleRisk?.status || 'Low'}
              </span>
            </div>
          </div>

          <button
            type="button"
            onClick={() => onNavigate('risk-analysis')}
            className="flex w-full items-center justify-center gap-2 rounded-md border border-[#0B6B63] px-3 py-2.5 text-xs font-semibold text-[#0B6B63] hover:bg-[#CDEFE6]"
          >
            Investigate All Risks
            ({healthSummary?.active_flags?.length ?? 0})
            <ArrowRight className="h-3.5 w-3.5" />
          </button>
        </div>

        <div
          className="flex flex-col rounded-lg border bg-white p-5 xl:col-span-3"
          style={{ borderColor: BORDER }}
        >
          <div className="border-b pb-4" style={{ borderColor: BORDER }}>
            <div className="flex items-center gap-2">
              <Activity className="h-4 w-4 text-[#0B6B63]" />
              <h2 className="text-lg font-semibold text-slate-900">
                Delivery Progress
              </h2>
            </div>

            <p className="mt-1 text-xs text-slate-500">
              Milestone and sprint execution
            </p>
          </div>

          <div className="my-4 flex-1 space-y-5">
            <MetricBar
              label="Completion Velocity"
              score={scheduleRisk?.score}
              color={TEAL}
            />

            <div
              className="space-y-3 rounded-md border bg-[#EAF8F3] p-3"
              style={{ borderColor: BORDER }}
            >
              <div className="flex items-center justify-between gap-2 text-xs">
                <span className="text-slate-600">Total Items Tracked</span>
                <span className="font-semibold tabular-nums text-slate-900">
                  {totalPlanned}
                </span>
              </div>

              <div className="flex items-center justify-between gap-2 text-xs">
                <span className="text-slate-600">Completed Items</span>
                <span className="font-semibold tabular-nums text-slate-900">
                  {totalCompleted}
                </span>
              </div>

              <div className="flex items-center justify-between gap-2 text-xs">
                <span className="text-slate-600">Overdue Target Dates</span>
                <span
                  className={`font-semibold tabular-nums ${
                    overdueCount > 0 ? 'text-[#CC1F2E]' : 'text-[#0B6B63]'
                  }`}
                >
                  {overdueCount}
                </span>
              </div>
            </div>

            <div className="flex items-center gap-2 text-xs text-slate-500">
              <Users className="h-4 w-4 text-[#0B6B63]" />
              {totalContributorsCount} active contributors
            </div>
          </div>

          <button
            type="button"
            onClick={() => onNavigate('activity')}
            className="flex w-full items-center justify-center gap-2 rounded-md border border-[#9ED4C8] px-3 py-2.5 text-xs font-semibold text-slate-700 hover:bg-[#CDEFE6]"
          >
            View Activity Telemetry
            <ArrowRight className="h-3.5 w-3.5" />
          </button>
        </div>
      </section>
    </div>
  );
};
