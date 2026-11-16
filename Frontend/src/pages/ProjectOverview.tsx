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
  TrendingUp,
  RefreshCw,
  AlertTriangle,
  GitPullRequest,
  AlertCircle,
  Users,
  CheckCircle2,
  Clock,
  Layers,
  Sparkles,
} from 'lucide-react';

interface ProjectOverviewProps {
  project: ProjectResponse | null;
  onNavigate: (view: PageView) => void;
  onRefreshProject?: () => void;
}

export const ProjectOverview: React.FC<ProjectOverviewProps> = ({
  project,
  onNavigate,
  onRefreshProject,
}) => {
  const [healthSummary, setHealthSummary] = useState<HealthSummaryData | null>(null);
  const [metricsBreakdown, setMetricsBreakdown] = useState<MetricsBreakdownData | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isSyncing, setIsSyncing] = useState<boolean>(false);
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
    } catch (err: any) {
      setError(err.message || 'Failed to fetch project metrics.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (project?.id) {
      fetchMetrics(project.id);
    }
  }, [project?.id]);

  const handleSyncAll = async () => {
    if (!project?.id) return;
    setIsSyncing(true);
    setSyncFeedback('Synchronizing commits, PRs, issues and contributors from GitHub...');
    try {
      await Promise.allSettled([
        dataSyncApi.syncCommits(project.id, project.default_branch || 'main'),
        dataSyncApi.syncPRs(project.id),
        dataSyncApi.syncIssues(project.id),
        dataSyncApi.syncContributors(project.id),
        dataSyncApi.syncMilestones(project.id),
      ]);
      setSyncFeedback('Synchronization complete! Refreshing metrics...');
      await fetchMetrics(project.id);
      if (onRefreshProject) onRefreshProject();
      setTimeout(() => setSyncFeedback(null), 3500);
    } catch (err: any) {
      setSyncFeedback(`Sync note: ${err.message || 'Partial sync completed.'}`);
      setTimeout(() => setSyncFeedback(null), 4000);
    } finally {
      setIsSyncing(false);
    }
  };

  // If no project is selected or user has zero projects
  if (!project) {
    return (
      <div className="p-8 max-w-4xl mx-auto space-y-6">
        <div className="bg-white rounded-2xl p-8 border border-slate-200/90 shadow-sm text-center space-y-4">
          <div className="w-14 h-14 bg-indigo-50 text-indigo-600 rounded-2xl flex items-center justify-center mx-auto shadow-inner">
            <Layers className="w-7 h-7" />
          </div>
          <h2 className="text-xl font-bold text-slate-900">No Project Selected</h2>
          <p className="text-sm text-slate-500 max-w-md mx-auto">
            You don't have an active project selected or no projects have been created yet.
          </p>
          <button
            onClick={() => onNavigate('create-project')}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-indigo-600 text-white text-xs font-bold hover:bg-indigo-700 transition-colors cursor-pointer shadow-md shadow-indigo-600/20"
          >
            <span>+ Create First Project</span>
          </button>
        </div>
      </div>
    );
  }

  // If project has no repository connected yet
  if (!project.repo_url) {
    return (
      <div className="p-8 max-w-4xl mx-auto space-y-6">
        <div className="bg-white rounded-2xl p-8 border border-slate-200/90 shadow-sm text-center space-y-4">
          <div className="w-14 h-14 bg-amber-50 text-amber-600 rounded-2xl flex items-center justify-center mx-auto shadow-inner">
            <GitPullRequest className="w-7 h-7" />
          </div>
          <h2 className="text-xl font-bold text-slate-900">Connect a GitHub Repository</h2>
          <p className="text-sm text-slate-500 max-w-md mx-auto">
            Project <span className="font-semibold text-slate-800">"{project.name}"</span> is not connected to a GitHub repository. Connect a repository to ingest commits, pull requests, and real-time health metrics.
          </p>
          <button
            onClick={() => onNavigate('connect-repo')}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-indigo-600 text-white text-xs font-bold hover:bg-indigo-700 transition-colors cursor-pointer shadow-md shadow-indigo-600/20"
          >
            <span>Connect GitHub Repository</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    );
  }

  const bottlenecks = metricsBreakdown?.indicators?.bottlenecks;
  const workload = metricsBreakdown?.indicators?.workload;
  const staleIssues = metricsBreakdown?.indicators?.stale_issues;
  const scheduleRisk = metricsBreakdown?.indicators?.schedule_risk;

  const healthScore = healthSummary?.health_score !== null && healthSummary?.health_score !== undefined
    ? Math.round(healthSummary.health_score)
    : null;

  const healthStatus = healthSummary?.status || 'Insufficient Data';

  const getScoreColor = (status: string) => {
    switch (status) {
      case 'Good':
        return 'text-emerald-600';
      case 'Caution':
        return 'text-amber-600';
      case 'At Risk':
        return 'text-rose-600';
      default:
        return 'text-slate-500';
    }
  };

  const getScoreBg = (status: string) => {
    switch (status) {
      case 'Good':
        return '#10b981';
      case 'Caution':
        return '#f59e0b';
      case 'At Risk':
        return '#f43f5e';
      default:
        return '#94a3b8';
    }
  };

  const openPRsCount = bottlenecks?.details?.open_prs_count ?? 0;
  const agingPRsCount = bottlenecks?.details?.aging_prs_count ?? 0;
  const staleIssuesCount = staleIssues?.details?.stale_issues_count ?? 0;
  const totalContributorsCount = workload?.details?.total_contributors ?? 0;
  const potentialBottlenecks = (healthSummary?.flags_count?.high ?? 0) + (healthSummary?.flags_count?.medium ?? 0);

  const isInsufficient = healthStatus === 'Insufficient Data' || healthScore === null;

  return (
    <div className="p-6 md:p-8 max-w-7xl mx-auto space-y-6">
      {/* Header & Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl md:text-3xl font-bold text-slate-900 tracking-tight">
              {project.name}
            </h1>
            <span className="text-xs font-mono font-medium px-2.5 py-1 bg-slate-100 border border-slate-200 text-slate-700 rounded-lg">
              {project.default_branch || 'main'}
            </span>
          </div>
          <p className="text-sm text-slate-500 mt-1">
            Real-time health, delivery risks, and telemetry for{' '}
            <a
              href={project.repo_url}
              target="_blank"
              rel="noreferrer"
              className="font-medium text-indigo-600 hover:underline"
            >
              {project.repo_url.replace(/^https:\/\/github\.com\//, '')}
            </a>
          </p>
        </div>

        {/* Sync Controls */}
        <div className="flex items-center gap-2">
          <button
            onClick={handleSyncAll}
            disabled={isSyncing}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold text-white shadow-md shadow-indigo-600/20 bg-indigo-600 hover:bg-indigo-700 transition-all cursor-pointer disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isSyncing ? 'animate-spin' : ''}`} />
            <span>{isSyncing ? 'Synchronizing...' : 'Sync Live Telemetry'}</span>
          </button>
        </div>
      </div>

      {/* Sync / Status Feedback Banner */}
      {syncFeedback && (
        <div className="p-3.5 bg-indigo-50/80 border border-indigo-200 rounded-xl text-xs text-indigo-900 flex items-center justify-between animate-fadeIn">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-indigo-600 shrink-0" />
            <span>{syncFeedback}</span>
          </div>
        </div>
      )}

      {/* Insufficient Data Onboarding Banner */}
      {isInsufficient && !isLoading && (
        <div className="p-4 bg-amber-50/80 border border-amber-200/90 rounded-2xl flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs text-amber-900">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
            <div>
              <p className="font-bold text-sm text-amber-950">Insufficient Telemetry Data</p>
              <p className="text-amber-800 mt-0.5">
                GitHub telemetry has not been synchronized yet for this project. Trigger a synchronization to ingest commits, pull requests, and issues.
              </p>
            </div>
          </div>
          <button
            onClick={handleSyncAll}
            disabled={isSyncing}
            className="px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white font-bold rounded-xl transition-colors cursor-pointer shrink-0 disabled:opacity-50"
          >
            {isSyncing ? 'Syncing...' : 'Sync Telemetry Now'}
          </button>
        </div>
      )}

      {/* Top 6 KPI Cards Grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3.5">
        {/* 1. PROJECT HEALTH */}
        <div className="bg-white rounded-xl p-4 border border-slate-200/90 shadow-sm flex flex-col justify-between">
          <p className="text-[11px] font-extrabold uppercase text-[#01315e] tracking-tight">
            PROJECT HEALTH
          </p>
          <div className="my-2 flex items-baseline gap-2">
            <span className="text-3xl font-bold text-slate-900">
              {healthScore !== null ? healthScore : '--'}
            </span>
            <span className={`text-xs font-bold ${getScoreColor(healthStatus)}`}>
              {healthStatus}
            </span>
          </div>
          <p className="text-[11px] font-medium text-slate-500 flex items-center gap-1">
            <Clock className="w-3 h-3 text-slate-400" />
            <span>{healthSummary?.data_freshness === 'fresh' ? 'Fresh (< 24h)' : 'Freshness: ' + (healthSummary?.data_freshness || 'unknown')}</span>
          </p>
        </div>

        {/* 2. SCHEDULE RISK */}
        <div className="bg-white rounded-xl p-4 border border-slate-200/90 shadow-sm flex flex-col justify-between">
          <p className="text-[11px] font-extrabold uppercase text-[#01315e] tracking-tight">
            SCHEDULE RISK
          </p>
          <div className="my-2">
            <span className="text-3xl font-bold text-slate-900">
              {scheduleRisk?.status || 'N/A'}
            </span>
          </div>
          <p className="text-[11px] text-slate-500">
            {scheduleRisk?.details?.overdue_count ? `${scheduleRisk.details.overdue_count} overdue milestone(s)` : 'No active milestone slippage'}
          </p>
        </div>

        {/* 3. OPEN PULL REQUESTS */}
        <div className="bg-white rounded-xl p-4 border border-slate-200/90 shadow-sm flex flex-col justify-between">
          <p className="text-[11px] font-extrabold uppercase text-[#01315e] tracking-tight">
            OPEN PULL REQUESTS
          </p>
          <div className="my-2">
            <span className="text-3xl font-bold text-slate-900">{openPRsCount}</span>
          </div>
          <p className={`text-[11px] font-semibold ${agingPRsCount > 0 ? 'text-amber-600' : 'text-emerald-600'}`}>
            {agingPRsCount > 0 ? `${agingPRsCount} aging (>48h)` : 'Review queue healthy'}
          </p>
        </div>

        {/* 4. STALE ISSUES */}
        <div className="bg-white rounded-xl p-4 border border-slate-200/90 shadow-sm flex flex-col justify-between">
          <p className="text-[11px] font-extrabold uppercase text-[#01315e] tracking-tight">
            STALE ISSUES
          </p>
          <div className="my-2">
            <span className="text-3xl font-bold text-slate-900">{staleIssuesCount}</span>
          </div>
          <p className={`text-[11px] font-semibold ${staleIssuesCount > 0 ? 'text-amber-600' : 'text-emerald-600'}`}>
            {staleIssuesCount > 0 ? 'Exceeds inactivity limit' : 'All issues active'}
          </p>
        </div>

        {/* 5. BOTTLENECKS */}
        <div className="bg-white rounded-xl p-4 border border-slate-200/90 shadow-sm flex flex-col justify-between">
          <p className="text-[11px] font-extrabold uppercase text-[#01315e] tracking-tight">
            BOTTLENECKS
          </p>
          <div className="my-2">
            <span className="text-3xl font-bold text-slate-900">{potentialBottlenecks}</span>
          </div>
          <p className="text-[11px] text-slate-500">
            {potentialBottlenecks > 0 ? 'Actionable flags detected' : 'Zero blockers'}
          </p>
        </div>

        {/* 6. CONTRIBUTORS */}
        <div className="bg-white rounded-xl p-4 border border-slate-200/90 shadow-sm flex flex-col justify-between">
          <p className="text-[11px] font-extrabold uppercase text-[#01315e] tracking-tight">
            CONTRIBUTORS
          </p>
          <div className="my-2">
            <span className="text-3xl font-bold text-slate-900">{totalContributorsCount}</span>
          </div>
          <p className="text-[11px] text-slate-500">
            Active contributors
          </p>
        </div>
      </div>

      {/* Middle Grid: Project Health Breakdown + Risk Overview + Delivery Progress */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Card 1: Project Health & Indicators (6 cols) */}
        <div className="lg:col-span-6 bg-white rounded-2xl p-6 border border-slate-200/90 shadow-sm flex flex-col justify-between">
          <div className="flex items-center justify-between border-b border-slate-100 pb-4">
            <div>
              <h2 className="text-lg font-bold text-slate-900">
                Composite Health Index
              </h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Deterministic weighted score based on GitHub telemetry
              </p>
            </div>
            <button
              onClick={() => onNavigate('health-analysis')}
              className="text-xs font-semibold text-blue-600 hover:text-blue-800 transition-colors flex items-center gap-1 cursor-pointer"
            >
              <span>View Breakdown</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 items-center my-auto py-4">
            {/* Health Score Gauge */}
            <div className="flex flex-col items-center justify-center p-4">
              <div className="relative w-36 h-36 flex items-center justify-center">
                <svg className="w-full h-full transform -rotate-90" viewBox="0 0 120 120">
                  <circle
                    cx="60"
                    cy="60"
                    r="48"
                    stroke="#e2e8f0"
                    strokeWidth="10"
                    fill="transparent"
                  />
                  <circle
                    cx="60"
                    cy="60"
                    r="48"
                    stroke={getScoreBg(healthStatus)}
                    strokeWidth="10"
                    strokeDasharray={2 * Math.PI * 48}
                    strokeDashoffset={
                      healthScore !== null
                        ? (2 * Math.PI * 48) * (1 - healthScore / 100)
                        : (2 * Math.PI * 48) * (1 - 0.05)
                    }
                    strokeLinecap="round"
                    fill="transparent"
                  />
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
                  <span className="text-4xl font-extrabold text-slate-900 leading-none">
                    {healthScore !== null ? healthScore : '--'}
                  </span>
                  <span className={`text-[11px] font-bold mt-1 uppercase tracking-wider ${getScoreColor(healthStatus)}`}>
                    {healthStatus}
                  </span>
                </div>
              </div>
            </div>

            {/* Health Indicators Bars */}
            <div className="space-y-3.5">
              <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
                Normalized Indicators
              </h3>

              {/* Bottlenecks */}
              <div>
                <div className="flex justify-between text-xs font-medium mb-1">
                  <span className="text-slate-600">Review Bottlenecks</span>
                  <span className="text-slate-900 font-semibold">
                    {bottlenecks?.score !== null && bottlenecks?.score !== undefined ? `${Math.round(bottlenecks.score)}%` : 'No Data'}
                  </span>
                </div>
                <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
                  <div
                    className="bg-emerald-500 h-full rounded-full transition-all duration-500"
                    style={{ width: `${bottlenecks?.score || 0}%` }}
                  />
                </div>
              </div>

              {/* Workload */}
              <div>
                <div className="flex justify-between text-xs font-medium mb-1">
                  <span className="text-slate-600">Workload Balance</span>
                  <span className="text-slate-900 font-semibold">
                    {workload?.score !== null && workload?.score !== undefined ? `${Math.round(workload.score)}%` : 'No Data'}
                  </span>
                </div>
                <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
                  <div
                    className="bg-indigo-500 h-full rounded-full transition-all duration-500"
                    style={{ width: `${workload?.score || 0}%` }}
                  />
                </div>
              </div>

              {/* Issues */}
              <div>
                <div className="flex justify-between text-xs font-medium mb-1">
                  <span className="text-slate-600">Issue Freshness</span>
                  <span className="text-slate-900 font-semibold">
                    {staleIssues?.score !== null && staleIssues?.score !== undefined ? `${Math.round(staleIssues.score)}%` : 'No Data'}
                  </span>
                </div>
                <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
                  <div
                    className="bg-emerald-500 h-full rounded-full transition-all duration-500"
                    style={{ width: `${staleIssues?.score || 0}%` }}
                  />
                </div>
              </div>

              {/* Schedule */}
              <div>
                <div className="flex justify-between text-xs font-medium mb-1">
                  <span className="text-slate-600">Schedule Velocity</span>
                  <span className="text-slate-900 font-semibold">
                    {scheduleRisk?.score !== null && scheduleRisk?.score !== undefined ? `${Math.round(scheduleRisk.score)}%` : 'No Data'}
                  </span>
                </div>
                <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
                  <div
                    className="bg-amber-500 h-full rounded-full transition-all duration-500"
                    style={{ width: `${scheduleRisk?.score || 0}%` }}
                  />
                </div>
              </div>
            </div>
          </div>

          <div className="pt-3 border-t border-slate-100 text-xs text-slate-500 italic">
            {healthSummary?.summary_statement || 'Synchronize repository to evaluate live health statement.'}
          </div>
        </div>

        {/* Card 2: Risk Overview (3 cols) */}
        <div className="lg:col-span-3 bg-white rounded-2xl p-6 border border-slate-200/90 shadow-sm flex flex-col justify-between">
          <div className="border-b border-slate-100 pb-4">
            <h2 className="text-lg font-bold text-slate-900">
              Risk Signals
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">Active automated risk triggers</p>
          </div>

          <div className="space-y-4 my-auto py-3">
            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-700 font-medium">Aging PR Bottlenecks</span>
              <span className={`font-bold px-2 py-0.5 rounded text-xs ${agingPRsCount > 0 ? 'text-rose-600 bg-rose-50' : 'text-emerald-600 bg-emerald-50'}`}>
                {agingPRsCount}
              </span>
            </div>

            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-700 font-medium">Stale Issues (&gt;14d)</span>
              <span className={`font-bold px-2 py-0.5 rounded text-xs ${staleIssuesCount > 0 ? 'text-amber-600 bg-amber-50' : 'text-emerald-600 bg-emerald-50'}`}>
                {staleIssuesCount}
              </span>
            </div>

            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-700 font-medium">Workload Concentration</span>
              <span className="text-indigo-600 font-bold bg-indigo-50 px-2 py-0.5 rounded text-xs">
                {workload?.status || 'Good'}
              </span>
            </div>

            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-700 font-medium">Milestone Slippage</span>
              <span className="text-slate-600 font-bold bg-slate-100 px-2 py-0.5 rounded text-xs">
                {scheduleRisk?.status || 'Low'}
              </span>
            </div>
          </div>

          <button
            onClick={() => onNavigate('risk-analysis')}
            className="w-full py-2.5 text-xs font-semibold text-center text-indigo-600 hover:text-indigo-800 bg-indigo-50/70 hover:bg-indigo-50 rounded-lg transition-colors cursor-pointer"
          >
            Investigate All Risks ({healthSummary?.active_flags?.length ?? 0}) →
          </button>
        </div>

        {/* Card 3: Milestone / Velocity Progress (3 cols) */}
        <div className="lg:col-span-3 bg-white rounded-2xl p-6 border border-slate-200/90 shadow-sm flex flex-col justify-between">
          <div className="border-b border-slate-100 pb-4">
            <h2 className="text-lg font-bold text-slate-900">
              Delivery Progress
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">Milestone and sprint execution</p>
          </div>

          <div className="space-y-4 my-auto py-3">
            <div>
              <div className="flex justify-between text-xs font-medium mb-1.5">
                <span className="text-slate-600">Completion Velocity</span>
                <span className="text-slate-900 font-bold">
                  {scheduleRisk?.score !== null && scheduleRisk?.score !== undefined ? `${Math.round(scheduleRisk.score)}%` : '--'}
                </span>
              </div>
              <div className="w-full bg-slate-100 h-2.5 rounded-full overflow-hidden">
                <div
                  className="bg-indigo-600 h-full rounded-full transition-all duration-500"
                  style={{ width: `${scheduleRisk?.score || 0}%` }}
                />
              </div>
            </div>

            <div className="p-3 bg-slate-50 border border-slate-200/80 rounded-xl space-y-1 text-xs text-slate-600">
              <div className="flex justify-between">
                <span>Total Items Tracked:</span>
                <span className="font-semibold text-slate-900">{scheduleRisk?.details?.total_planned_items ?? 0}</span>
              </div>
              <div className="flex justify-between">
                <span>Completed Items:</span>
                <span className="font-semibold text-slate-900">{scheduleRisk?.details?.total_completed_items ?? 0}</span>
              </div>
              <div className="flex justify-between">
                <span>Overdue Target Dates:</span>
                <span className={`font-semibold ${scheduleRisk?.details?.overdue_count ? 'text-rose-600' : 'text-emerald-600'}`}>
                  {scheduleRisk?.details?.overdue_count ?? 0}
                </span>
              </div>
            </div>
          </div>

          <button
            onClick={() => onNavigate('activity')}
            className="w-full py-2.5 text-xs font-semibold text-center text-slate-700 hover:text-slate-900 bg-slate-100 hover:bg-slate-200/80 rounded-lg transition-colors cursor-pointer"
          >
            View Activity Telemetry →
          </button>
        </div>
      </div>
    </div>
  );
};
