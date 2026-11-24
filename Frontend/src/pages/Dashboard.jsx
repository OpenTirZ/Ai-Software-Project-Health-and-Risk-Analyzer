import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  RotateCw,
  Clock,
  AlertCircle,
  CheckCircle2,
  Flame,
  Search,
} from 'lucide-react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { metricService } from '../services/metricService';
import { HealthScoreCard } from '../components/dashboard/HealthScoreCard';
import { BottlenecksList } from '../components/dashboard/BottlenecksList';
import { WorkloadChart } from '../components/dashboard/WorkloadChart';

/**
 * Custom Tooltip for Sprint Burndown Chart
 */
const CustomBurndownTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-slate-900/95 text-white p-3 rounded-xl shadow-xl text-xs border border-slate-700/80 backdrop-blur-md">
        <p className="font-bold text-indigo-300 mb-1">{label}</p>
        {payload.map((entry, idx) => (
          <p key={idx} className="flex items-center justify-between gap-4 text-slate-300">
            <span className="flex items-center gap-1.5">
              <span
                className="w-2 h-2 rounded-full inline-block"
                style={{ backgroundColor: entry.color }}
              />
              {entry.name}:
            </span>
            <span className="font-mono font-bold text-white">
              {entry.value !== null ? `${entry.value} pts` : 'In Progress'}
            </span>
          </p>
        ))}
      </div>
    );
  }
  return null;
};

/**
 * Sprint 2 Comprehensive React Dashboard Component
 * Clean, modern layout engineered to eliminate text collisions on all resolutions.
 */
export const Dashboard = ({ projectId = 'proj_core_platform', selectedRepo = 'core-api-service', onNavigate: _onNavigate }) => {
  const [healthSummary, setHealthSummary] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [error, setError] = useState(null);
  const [syncSuccessMsg, setSyncSuccessMsg] = useState(null);

  // Stale Issues Filter State
  const [inactivityFilter, setInactivityFilter] = useState('ALL'); // 'ALL', '14', '30', 'CUSTOM'
  const [customInactivityDays, setCustomInactivityDays] = useState(14);
  const [issueSearchQuery, setIssueSearchQuery] = useState('');
  const [issueSeverityFilter, setIssueSeverityFilter] = useState('ALL');

  // Load health summary data from backend on mount or when projectId/selectedRepo changes
  const loadData = useCallback(async (showLoadingSpinner = true) => {
    if (showLoadingSpinner) setIsLoading(true);
    setError(null);
    try {
      const data = await metricService.getHealthSummary(projectId, selectedRepo);
      setHealthSummary(data);
      setError(null);
    } catch (err) {
      console.error('Failed to load health summary:', err);
      const errMsg = err?.message || 'Could not connect to health summary endpoint.';
      setError(errMsg);
    } finally {
      if (showLoadingSpinner) setIsLoading(false);
    }
  }, [projectId, selectedRepo]);

  useEffect(() => {
    loadData(true);
  }, [loadData]);

  // Handle Manual Refresh / Sync Button Click
  const handleManualSync = async () => {
    setIsSyncing(true);
    setSyncSuccessMsg(null);
    setError(null);

    try {
      const syncResult = await metricService.syncProjectData(projectId, selectedRepo);
      if (syncResult && syncResult.summary) {
        setHealthSummary(syncResult.summary);
      } else {
        await loadData(false);
      }
      setSyncSuccessMsg(syncResult?.message || 'Project metrics synchronized and recalculated successfully!');
      setTimeout(() => setSyncSuccessMsg(null), 4000);
    } catch (err) {
      console.error('Manual sync failed:', err);
      const errMsg = err?.message || 'Failed to complete manual sync.';
      setError(`Sync failed: ${errMsg}`);
    } finally {
      setIsSyncing(false);
    }
  };

  // Format "Last Synced At" timestamp display safely
  const formattedSyncTime = useMemo(() => {
    const rawTimestamp = healthSummary?.lastSyncedAt;
    if (!rawTimestamp) return 'Just now';
    try {
      const date = new Date(rawTimestamp);
      return date.toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      });
    } catch {
      return String(rawTimestamp);
    }
  }, [healthSummary?.lastSyncedAt]);

  // Filter Stale Issues based on Inactivity Days, Severity, and Search Query
  const filteredIssues = useMemo(() => {
    const issues = healthSummary?.staleIssues || [];

    return issues.filter((issue) => {
      // Inactivity threshold check
      if (inactivityFilter === '14' && issue.daysInactive < 14) return false;
      if (inactivityFilter === '30' && issue.daysInactive < 30) return false;
      if (inactivityFilter === 'CUSTOM' && issue.daysInactive < customInactivityDays) return false;

      // Severity check
      if (issueSeverityFilter !== 'ALL' && issue.severity.toUpperCase() !== issueSeverityFilter) {
        return false;
      }

      // Search text check
      if (issueSearchQuery.trim()) {
        const query = issueSearchQuery.toLowerCase();
        const matchesTitle = issue.title.toLowerCase().includes(query);
        const matchesId = issue.id.toLowerCase().includes(query);
        const matchesAuthor = issue.author.toLowerCase().includes(query);
        const matchesAssignee = issue.assignee.toLowerCase().includes(query);
        if (!matchesTitle && !matchesId && !matchesAuthor && !matchesAssignee) return false;
      }

      return true;
    });
  }, [healthSummary?.staleIssues, inactivityFilter, customInactivityDays, issueSeverityFilter, issueSearchQuery]);

  const overallHealth = healthSummary?.overallHealth;
  const bottlenecks = healthSummary?.bottlenecks;
  const workload = healthSummary?.workload;
  const sprint = healthSummary?.sprint;

  // Derive top contributor share dynamically from API (Hooks MUST run before any early returns)
  const topAuthorShare = useMemo(() => {
    const top = workload?.contributors?.[0];
    if (!top) return '—';
    return `${top.percentage}% (${top.name.split(' ')[0]})`;
  }, [workload?.contributors]);

  // Derive sprint daily burn rate dynamically from API
  const averageBurnRate = useMemo(() => {
    if (sprint?.completedStoryPoints && sprint?.totalSprintDays && sprint?.daysRemaining != null) {
      const daysElapsed = Math.max(1, sprint.totalSprintDays - sprint.daysRemaining);
      return (sprint.completedStoryPoints / daysElapsed).toFixed(1);
    }
    if (sprint?.velocity) {
      return (sprint.velocity / 7).toFixed(1);
    }
    return '0.0';
  }, [sprint]);

  // Derive predicted finish dynamically from API
  const predictedFinishText = useMemo(() => {
    if (sprint?.velocityStatus) {
      return sprint.velocityStatus.split(' (')[0];
    }
    if (sprint?.velocity && sprint?.velocityTarget) {
      return sprint.velocity >= sprint.velocityTarget ? 'Ahead of Schedule' : 'Behind Target';
    }
    return 'On Schedule';
  }, [sprint]);

  if (isLoading) {
    return (
      <div className="p-8 max-w-7xl mx-auto flex flex-col items-center justify-center min-h-[500px]">
        <RotateCw className="w-8 h-8 text-indigo-600 animate-spin mb-3" />
        <p className="text-sm font-semibold text-slate-700">Loading Project Health Analytics...</p>
        <p className="text-xs text-slate-400 mt-1">Connecting to /api/projects/{projectId}/health-summary</p>
      </div>
    );
  }

  // Proper API failure handling: Dedicated Error State when metrics cannot be loaded
  if (!healthSummary) {
    return (
      <div className="p-8 max-w-xl mx-auto flex flex-col items-center justify-center min-h-[500px] text-center">
        <div className="w-16 h-16 rounded-2xl bg-rose-50 border border-rose-200 flex items-center justify-center text-rose-600 mb-4 shadow-xs">
          <AlertCircle className="w-8 h-8" />
        </div>
        <h2 className="text-xl font-bold text-slate-900 mb-2">Unable to Load Project Health Metrics</h2>
        <p className="text-sm text-slate-600 max-w-md mb-2">
          {error || `No metrics available for project ID '${projectId}'.`}
        </p>
        <p className="text-xs text-slate-400 font-mono mb-6 bg-slate-50 py-1 px-3 rounded-lg border border-slate-200">
          Project ID: {projectId} • GET /api/projects/{projectId}/health-summary
        </p>
        <div className="flex items-center gap-3">
          <button
            onClick={() => loadData(true)}
            className="px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs shadow-md transition-all flex items-center gap-2 cursor-pointer"
          >
            <RotateCw className="w-3.5 h-3.5" />
            <span>Retry Connection</span>
          </button>
          {_onNavigate && (
            <button
              onClick={() => _onNavigate('projects')}
              className="px-4 py-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold text-xs transition-all cursor-pointer"
            >
              Back to All Repositories
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="p-4 sm:p-6 md:p-8 max-w-7xl mx-auto space-y-6">
      {/* Top Header & Sync Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-5 rounded-2xl border border-slate-200/90 shadow-xs min-w-0">
        <div className="min-w-0">
          <div className="flex items-center gap-2.5 flex-wrap">
            <h1 className="text-xl sm:text-2xl md:text-3xl font-black text-slate-900 tracking-tight truncate">
              Project Health & Risk Dashboard
            </h1>
            <span className="text-xs font-bold px-2.5 py-0.5 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200 shrink-0">
              Sprint 2
            </span>
          </div>
          <p className="text-xs md:text-sm text-slate-500 mt-1 flex items-center gap-2 flex-wrap">
            <span>Repository:</span>
            <strong className="text-slate-800 font-semibold truncate">{selectedRepo}</strong>
            <span className="text-slate-300">•</span>
            <span>Branch:</span>
            <strong className="text-slate-800 font-semibold truncate">{healthSummary?.branch || 'main'}</strong>
          </p>
        </div>

        {/* Sync Controls & Prominent Last Synced Display */}
        <div className="flex flex-wrap items-center gap-3 shrink-0 self-start sm:self-auto">
          {/* Prominent Last Synced At Badge */}
          <div className="flex items-center gap-2.5 px-3.5 py-2 rounded-xl bg-slate-50 border border-slate-200/90 shadow-2xs">
            <div className="w-7 h-7 rounded-lg bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 shrink-0">
              <Clock className={`w-3.5 h-3.5 ${isSyncing ? 'animate-spin' : ''}`} />
            </div>
            <div className="text-left min-w-0">
              <div className="flex items-center gap-1.5">
                <span className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">
                  Last Synced At
                </span>
                {healthSummary?.dataSource === 'github' && (
                  <span className="text-[9px] font-bold px-1.5 py-0.2 rounded-full bg-emerald-100 text-emerald-700">
                    GitHub Live
                  </span>
                )}
              </div>
              <p className="text-xs font-bold text-slate-800 font-mono leading-tight truncate">
                {formattedSyncTime}
              </p>
            </div>
          </div>

          {/* Manual Refresh / Sync Button */}
          <button
            onClick={handleManualSync}
            disabled={isSyncing}
            className="px-4 py-2.5 rounded-xl text-white font-semibold text-xs shadow-md shadow-indigo-500/20 transition-all flex items-center gap-2 cursor-pointer disabled:opacity-75 disabled:cursor-not-allowed shrink-0"
            style={{
              background: 'linear-gradient(135deg, #1b1795 0%, #2e3b63 50%, #18ebe4 100%)',
            }}
            title="Trigger manual health summary data refresh and recalculation"
          >
            <RotateCw className={`w-3.5 h-3.5 shrink-0 ${isSyncing ? 'animate-spin' : ''}`} />
            <span>{isSyncing ? 'Syncing...' : 'Sync Project Data'}</span>
          </button>
        </div>
      </div>

      {/* Sync Success / Error Notifications */}
      {syncSuccessMsg && (
        <div className="p-3.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-medium flex items-center gap-2 animate-fadeIn">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>{syncSuccessMsg}</span>
        </div>
      )}

      {error && (
        <div className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs font-medium flex items-center justify-between gap-2 animate-fadeIn">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
            <span>{error}</span>
          </div>
          <button
            onClick={() => setError(null)}
            className="text-rose-600 hover:text-rose-800 text-xs font-bold px-2 py-0.5 rounded cursor-pointer"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Section 1: Executive KPI Cards Grid (xl:grid-cols-6 ensures ample width on standard laptops) */}
      <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-3.5 min-w-0">
        {/* KPI 1: Overall Health */}
        <div className="bg-white rounded-xl p-4 border border-slate-200/90 shadow-xs flex flex-col justify-between min-w-0">
          <p className="text-[10px] font-extrabold uppercase text-slate-400 tracking-wider truncate">
            HEALTH SCORE
          </p>
          <div className="my-2 flex items-baseline justify-between gap-1">
            <span className="text-2xl sm:text-3xl font-black text-slate-900">{overallHealth?.score}</span>
            <span className="text-xs font-bold text-emerald-600 px-1.5 py-0.5 rounded bg-emerald-50 border border-emerald-200 truncate">
              {overallHealth?.status}
            </span>
          </div>
          <p className="text-[11px] font-medium text-emerald-600 truncate">
            {overallHealth?.trend}
          </p>
        </div>

        {/* KPI 2: Review Latency */}
        <div className="bg-white rounded-xl p-4 border border-slate-200/90 shadow-xs flex flex-col justify-between min-w-0">
          <p className="text-[10px] font-extrabold uppercase text-slate-400 tracking-wider truncate">
            REVIEW LATENCY
          </p>
          <div className="my-2 flex items-baseline gap-1.5">
            <span className="text-2xl sm:text-3xl font-black text-slate-900">{bottlenecks?.avgReviewLatencyHours}</span>
            <span className="text-xs font-medium text-slate-500">hours</span>
          </div>
          <p className="text-[11px] font-semibold text-amber-600 truncate">
            SLA Target: ≤ 24h
          </p>
        </div>

        {/* KPI 3: Pending PRs > 48h */}
        <div className="bg-white rounded-xl p-4 border border-slate-200/90 shadow-xs flex flex-col justify-between min-w-0">
          <p className="text-[10px] font-extrabold uppercase text-slate-400 tracking-wider truncate">
            PENDING PRS &gt; 48H
          </p>
          <div className="my-2 flex items-baseline gap-1.5">
            <span className="text-2xl sm:text-3xl font-black text-rose-600">{bottlenecks?.pendingPrsOver48hCount}</span>
            <span className="text-xs font-semibold text-slate-500">aging</span>
          </div>
          <p className="text-[11px] font-medium text-rose-600 truncate">
            Requires attention
          </p>
        </div>

        {/* KPI 4: Stale Issues */}
        <div className="bg-white rounded-xl p-4 border border-slate-200/90 shadow-xs flex flex-col justify-between min-w-0">
          <p className="text-[10px] font-extrabold uppercase text-slate-400 tracking-wider truncate">
            STALE ISSUES
          </p>
          <div className="my-2 flex items-baseline gap-1.5">
            <span className="text-2xl sm:text-3xl font-black text-slate-900">{healthSummary?.staleIssues?.length}</span>
            <span className="text-xs font-semibold text-slate-500">tickets</span>
          </div>
          <p className="text-[11px] font-medium text-slate-500 truncate">
            &gt; 7 days inactive
          </p>
        </div>

        {/* KPI 5: Sprint Velocity */}
        <div className="bg-white rounded-xl p-4 border border-slate-200/90 shadow-xs flex flex-col justify-between min-w-0">
          <p className="text-[10px] font-extrabold uppercase text-slate-400 tracking-wider truncate">
            SPRINT VELOCITY
          </p>
          <div className="my-2 flex items-baseline gap-1.5">
            <span className="text-2xl sm:text-3xl font-black text-slate-900">{sprint?.velocity}</span>
            <span className="text-xs font-medium text-slate-500">pts/wk</span>
          </div>
          <p className="text-[11px] font-medium text-emerald-600 truncate">
            Target: {sprint?.velocityTarget} pts
          </p>
        </div>

        {/* KPI 6: Bus Factor */}
        <div className="bg-white rounded-xl p-4 border border-slate-200/90 shadow-xs flex flex-col justify-between min-w-0">
          <p className="text-[10px] font-extrabold uppercase text-slate-400 tracking-wider truncate">
            BUS FACTOR
          </p>
          <div className="my-2 flex items-baseline justify-between gap-1">
            <span className="text-2xl sm:text-3xl font-black text-slate-900">{workload?.busFactorScore ?? '—'}</span>
            <span className="text-[11px] font-bold px-1.5 py-0.5 rounded bg-amber-50 text-amber-700 border border-amber-200 truncate">
              {workload?.busFactorRisk ?? 'Analysis'}
            </span>
          </div>
          <p className="text-[11px] font-medium text-slate-500 truncate" title={`Top author share: ${topAuthorShare}`}>
            Top author: {topAuthorShare}
          </p>
        </div>
      </div>

      {/* Section 2: Health Score Gauge & Delivery Bottleneck Radar */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-stretch min-w-0">
        <HealthScoreCard healthData={overallHealth} />
        <BottlenecksList bottleneckData={bottlenecks} />
      </div>

      {/* Section 3: Workload Distribution Bar Chart & Sprint Burndown / Velocity */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch min-w-0">
        {/* Left: Workload Bar Chart (7 cols) */}
        <div className="lg:col-span-7 min-w-0">
          <WorkloadChart workloadData={workload} />
        </div>

        {/* Right: Sprint Burndown & Velocity Indicator (5 cols) */}
        <div className="lg:col-span-5 bg-white rounded-2xl p-6 border border-slate-200/90 shadow-sm flex flex-col justify-between min-w-0">
          {/* Header */}
          <div className="flex flex-wrap items-center justify-between pb-4 border-b border-slate-100 gap-3">
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="w-10 h-10 rounded-xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 shadow-sm shrink-0">
                <Flame className="w-5 h-5" />
              </div>
              <div className="min-w-0">
                <h2 className="text-base sm:text-lg font-bold text-slate-900 tracking-tight truncate">
                  Sprint Burndown & Velocity
                </h2>
                <p className="text-xs text-slate-500 truncate">
                  {sprint?.sprintName || 'Current Sprint Progress'}
                </p>
              </div>
            </div>

            <span className="text-xs font-semibold px-2.5 py-1 rounded-lg bg-emerald-50 text-emerald-700 border border-emerald-200 shrink-0">
              {sprint?.daysRemaining} days left
            </span>
          </div>

          {/* Velocity Indicator Progress Bar */}
          <div className="my-4 p-4 rounded-xl bg-slate-50 border border-slate-100">
            <div className="flex flex-wrap items-center justify-between gap-1 text-xs mb-2">
              <span className="font-bold text-slate-700">Sprint Story Points</span>
              <span className="font-extrabold text-slate-900">
                {sprint?.completedStoryPoints} / {sprint?.totalStoryPoints} pts ({Math.round(
                  (sprint?.completedStoryPoints / sprint?.totalStoryPoints) * 100
                )}%)
              </span>
            </div>
            <div className="w-full bg-slate-200 h-2.5 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-emerald-500 transition-all duration-700"
                style={{
                  width: `${(sprint?.completedStoryPoints / sprint?.totalStoryPoints) * 100}%`,
                }}
              />
            </div>
            <div className="flex flex-wrap items-center justify-between gap-1 text-[11px] text-slate-500 mt-2">
              <span>Remaining: <strong>{sprint?.remainingStoryPoints} pts</strong></span>
              <span className="text-emerald-600 font-semibold">{sprint?.velocityStatus}</span>
            </div>
          </div>

          {/* Burndown Area Chart with clean X-Axis labels */}
          <div className="w-full h-56 min-w-0">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart
                data={sprint?.burndown || []}
                margin={{ top: 10, right: 15, left: -5, bottom: 20 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                <XAxis
                  dataKey="day"
                  tick={{ fill: '#64748b', fontSize: 10 }}
                  tickFormatter={(val) => val.replace(' (End)', '')}
                  height={30}
                />
                <YAxis
                  tick={{ fill: '#94a3b8', fontSize: 10 }}
                  width={30}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip content={<CustomBurndownTooltip />} />
                <Legend
                  verticalAlign="top"
                  align="right"
                  wrapperStyle={{ paddingBottom: 12, fontSize: 11 }}
                />
                <Area
                  type="monotone"
                  dataKey="ideal"
                  name="Ideal Burndown"
                  stroke="#94a3b8"
                  strokeDasharray="4 4"
                  fill="transparent"
                  strokeWidth={2}
                />
                <Area
                  type="monotone"
                  dataKey="actual"
                  name="Actual Story Points"
                  stroke="#6366f1"
                  fill="#818cf8"
                  fillOpacity={0.25}
                  strokeWidth={2.5}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          <div className="pt-3 border-t border-slate-100 text-[11px] text-slate-500 flex flex-wrap items-center justify-between gap-2 mt-2">
            <span>
              Average Burn: <strong>{averageBurnRate} pts / day</strong>
            </span>
            <span className="text-indigo-600 font-semibold">
              Predicted Finish: {predictedFinishText}
            </span>
          </div>
        </div>
      </div>

      {/* Section 4: Stale Issues Data Table with filterable inactivity days */}
      <div className="bg-white rounded-2xl p-6 border border-slate-200/90 shadow-sm space-y-4 min-w-0">
        {/* Table Top Header & Controls */}
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pb-4 border-b border-slate-100">
          <div className="min-w-0">
            <h2 className="text-base sm:text-lg font-bold text-slate-900 tracking-tight flex items-center gap-2 flex-wrap">
              <span>Stale Issues Inspector</span>
              <span className="text-xs px-2.5 py-0.5 rounded-full bg-slate-100 text-slate-600 border border-slate-200 font-semibold shrink-0">
                {filteredIssues.length} issues
              </span>
            </h2>
            <p className="text-xs text-slate-500 truncate">
              Filter and track dormant bug reports and unresolved task tickets
            </p>
          </div>

          {/* Filter Controls Bar */}
          <div className="flex flex-wrap items-center gap-2.5">
            {/* Search Input */}
            <div className="relative">
              <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                placeholder="Search issues or author..."
                value={issueSearchQuery}
                onChange={(e) => setIssueSearchQuery(e.target.value)}
                className="pl-8 pr-3 py-1.5 text-xs rounded-xl border border-slate-200 bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-100 w-44 sm:w-52"
              />
            </div>

            {/* Inactivity Day Filter Pills */}
            <div className="flex items-center rounded-xl bg-slate-100 p-1 border border-slate-200 text-xs font-semibold shrink-0">
              <button
                onClick={() => setInactivityFilter('ALL')}
                className={`px-2.5 py-1 rounded-lg transition-all ${
                  inactivityFilter === 'ALL'
                    ? 'bg-white text-slate-900 shadow-xs'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                All Stale (&gt;7d)
              </button>
              <button
                onClick={() => setInactivityFilter('14')}
                className={`px-2.5 py-1 rounded-lg transition-all ${
                  inactivityFilter === '14'
                    ? 'bg-white text-slate-900 shadow-xs'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                &gt; 14 Days
              </button>
              <button
                onClick={() => setInactivityFilter('30')}
                className={`px-2.5 py-1 rounded-lg transition-all ${
                  inactivityFilter === '30'
                    ? 'bg-white text-slate-900 shadow-xs'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                &gt; 30 Days
              </button>
              <button
                onClick={() => setInactivityFilter('CUSTOM')}
                className={`px-2.5 py-1 rounded-lg transition-all ${
                  inactivityFilter === 'CUSTOM'
                    ? 'bg-white text-slate-900 shadow-xs'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                Custom
              </button>
            </div>

            {/* Severity Dropdown Filter */}
            <select
              value={issueSeverityFilter}
              onChange={(e) => setIssueSeverityFilter(e.target.value)}
              className="px-2.5 py-1.5 text-xs rounded-xl border border-slate-200 bg-slate-50 text-slate-700 font-semibold focus:outline-none focus:ring-2 focus:ring-indigo-100 shrink-0"
            >
              <option value="ALL">All Severities</option>
              <option value="CRITICAL">Critical</option>
              <option value="HIGH">High</option>
              <option value="MEDIUM">Medium</option>
              <option value="LOW">Low</option>
            </select>
          </div>
        </div>

        {/* Custom Days Slider if CUSTOM selected */}
        {inactivityFilter === 'CUSTOM' && (
          <div className="p-3 bg-indigo-50/60 rounded-xl border border-indigo-100 flex flex-wrap items-center justify-between gap-4 text-xs">
            <span className="font-semibold text-indigo-900">
              Minimum Inactivity Days Threshold: <strong>{customInactivityDays} days</strong>
            </span>
            <input
              type="range"
              min="1"
              max="60"
              value={customInactivityDays}
              onChange={(e) => setCustomInactivityDays(Number(e.target.value))}
              className="w-48 accent-indigo-600"
            />
          </div>
        )}

        {/* Stale Issues Table with horizontal scroll container and no text overlap */}
        <div className="overflow-x-auto rounded-xl border border-slate-200/80">
          <table className="w-full text-left text-xs min-w-[780px]">
            <thead className="bg-slate-50/90 border-b border-slate-200 text-slate-500 uppercase tracking-wider font-bold">
              <tr>
                <th className="py-3 px-4 whitespace-nowrap">Issue ID</th>
                <th className="py-3 px-4 min-w-[260px]">Title & Context</th>
                <th className="py-3 px-4 whitespace-nowrap">Author / Assignee</th>
                <th className="py-3 px-4 whitespace-nowrap">Inactivity Days</th>
                <th className="py-3 px-4 whitespace-nowrap">Severity</th>
                <th className="py-3 px-4 whitespace-nowrap">Status</th>
                <th className="py-3 px-4 text-right whitespace-nowrap">Last Updated</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-700">
              {filteredIssues.map((issue) => {
                const isOver30 = issue.daysInactive >= 30;
                const isOver14 = issue.daysInactive >= 14;

                const getSeverityPill = (sev) => {
                  switch (sev.toLowerCase()) {
                    case 'critical':
                      return 'bg-rose-100 text-rose-800 border-rose-300';
                    case 'high':
                      return 'bg-orange-100 text-orange-800 border-orange-300';
                    case 'medium':
                      return 'bg-amber-100 text-amber-800 border-amber-300';
                    default:
                      return 'bg-blue-100 text-blue-800 border-blue-300';
                  }
                };

                return (
                  <tr key={issue.id} className="hover:bg-slate-50/70 transition-colors">
                    <td className="py-3.5 px-4 font-mono font-bold text-indigo-600 whitespace-nowrap">
                      {issue.id}
                    </td>
                    <td className="py-3.5 px-4 max-w-sm">
                      <p className="font-semibold text-slate-900 break-words leading-snug">{issue.title}</p>
                      <div className="flex items-center gap-1.5 mt-1.5 flex-wrap">
                        {issue.labels?.map((label, lIdx) => (
                          <span
                            key={lIdx}
                            className="text-[10px] font-medium px-1.5 py-0.2 rounded bg-slate-100 text-slate-600"
                          >
                            #{label}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="py-3.5 px-4 whitespace-nowrap">
                      <p className="font-semibold text-slate-800">{issue.author}</p>
                      <p className="text-[10px] text-slate-400 mt-0.5">
                        Assignee: <span className="text-slate-600 font-medium">{issue.assignee}</span>
                      </p>
                    </td>
                    <td className="py-3.5 px-4 whitespace-nowrap">
                      <span
                        className={`inline-flex items-center gap-1 font-bold px-2.5 py-1 rounded-full text-[11px] border ${
                          isOver30
                            ? 'bg-rose-50 text-rose-700 border-rose-200'
                            : isOver14
                            ? 'bg-amber-50 text-amber-700 border-amber-200'
                            : 'bg-yellow-50 text-yellow-700 border-yellow-200'
                        }`}
                      >
                        <Clock className="w-3 h-3" />
                        {issue.daysInactive} days inactive
                      </span>
                    </td>
                    <td className="py-3.5 px-4 whitespace-nowrap">
                      <span
                        className={`text-[10px] font-bold px-2 py-0.5 rounded-md border ${getSeverityPill(
                          issue.severity
                        )}`}
                      >
                        {issue.severity}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 whitespace-nowrap">
                      <span className="font-medium text-slate-600">{issue.status}</span>
                    </td>
                    <td className="py-3.5 px-4 text-right font-mono text-[11px] text-slate-500 whitespace-nowrap">
                      {issue.lastUpdated}
                    </td>
                  </tr>
                );
              })}

              {filteredIssues.length === 0 && (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-slate-400">
                    No stale issues found matching current criteria.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
