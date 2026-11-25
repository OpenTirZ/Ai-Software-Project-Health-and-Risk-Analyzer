import React, { useState, useEffect, useCallback } from 'react';
import { RefreshCw, Clock, ArrowLeft } from 'lucide-react';

import type { PageView } from '../types';
import type { ProjectResponse } from '../services/api';
import { dataSyncApi } from '../services/api';
import {
  metricService,
  type HealthGaugeData,
  type BottleneckItem,
  type WorkloadEntry,
  type StaleIssueRow,
  type SprintVelocity,
} from '../services/metricService';

import {
  HealthScoreCard,
  BottlenecksList,
  WorkloadChart,
  StaleIssuesTable,
  SprintVelocityCard,
} from '../components/dashboard';

// ---------------------------------------------------------------------------
// Dashboard Page — Comprehensive Project Health Dashboard
// ---------------------------------------------------------------------------

interface DashboardProps {
  project: ProjectResponse | null;
  onNavigate: (view: PageView) => void;
}

export const Dashboard: React.FC<DashboardProps> = ({ project, onNavigate }) => {
  // ---------------------------------------------------------------------------
  // State
  // ---------------------------------------------------------------------------
  const [healthData, setHealthData] = useState<HealthGaugeData | null>(null);
  const [bottlenecks, setBottlenecks] = useState<BottleneckItem[]>([]);
  const [workload, setWorkload] = useState<WorkloadEntry[]>([]);
  const [staleIssues, setStaleIssues] = useState<StaleIssueRow[]>([]);
  const [sprints, setSprints] = useState<SprintVelocity[]>([]);

  const [loadingHealth, setLoadingHealth] = useState(false);
  const [loadingBottlenecks, setLoadingBottlenecks] = useState(false);
  const [loadingWorkload, setLoadingWorkload] = useState(false);
  const [loadingStale, setLoadingStale] = useState(false);
  const [loadingSprints, setLoadingSprints] = useState(false);

  const [errorHealth, setErrorHealth] = useState<string | null>(null);
  const [errorBottlenecks, setErrorBottlenecks] = useState<string | null>(null);
  const [errorWorkload, setErrorWorkload] = useState<string | null>(null);
  const [errorStale, setErrorStale] = useState<string | null>(null);
  const [errorSprints, setErrorSprints] = useState<string | null>(null);

  const [lastSyncedAt, setLastSyncedAt] = useState<string | null>(null);
  const [isSyncing, setIsSyncing] = useState(false);

  // ---------------------------------------------------------------------------
  // Data fetching
  // ---------------------------------------------------------------------------
  const fetchAll = useCallback(
    async (projectId: string) => {
      // Health gauge
      setLoadingHealth(true);
      setErrorHealth(null);
      metricService
        .fetchHealthGauge(projectId)
        .then((d) => {
          setHealthData(d);
          setLastSyncedAt(d.lastSyncedAt);
        })
        .catch((e) => setErrorHealth(e.message))
        .finally(() => setLoadingHealth(false));

      // Bottlenecks
      setLoadingBottlenecks(true);
      setErrorBottlenecks(null);
      metricService
        .fetchBottlenecks(projectId)
        .then(setBottlenecks)
        .catch((e) => setErrorBottlenecks(e.message))
        .finally(() => setLoadingBottlenecks(false));

      // Workload
      setLoadingWorkload(true);
      setErrorWorkload(null);
      metricService
        .fetchWorkload(projectId)
        .then(setWorkload)
        .catch((e) => setErrorWorkload(e.message))
        .finally(() => setLoadingWorkload(false));

      // Stale issues
      setLoadingStale(true);
      setErrorStale(null);
      metricService
        .fetchStaleIssues(projectId)
        .then(setStaleIssues)
        .catch((e) => setErrorStale(e.message))
        .finally(() => setLoadingStale(false));

      // Sprint velocity
      setLoadingSprints(true);
      setErrorSprints(null);
      metricService
        .fetchSprintVelocity(projectId)
        .then(setSprints)
        .catch((e) => setErrorSprints(e.message))
        .finally(() => setLoadingSprints(false));
    },
    []
  );

  useEffect(() => {
    if (project?.id) {
      fetchAll(project.id);
    }
  }, [project?.id, fetchAll]);

  // ---------------------------------------------------------------------------
  // Manual refresh / sync
  // ---------------------------------------------------------------------------
  const handleRefresh = async () => {
    if (!project?.id || isSyncing) return;
    setIsSyncing(true);
    try {
      await Promise.allSettled([
        dataSyncApi.syncCommits(project.id, project.default_branch || 'main'),
        dataSyncApi.syncPRs(project.id),
        dataSyncApi.syncIssues(project.id),
        dataSyncApi.syncContributors(project.id),
        dataSyncApi.syncMilestones(project.id),
      ]);
      setLastSyncedAt(new Date().toISOString());
      await fetchAll(project.id);
    } catch (err) {
      console.warn('Sync error:', err);
    } finally {
      setIsSyncing(false);
    }
  };

  // ---------------------------------------------------------------------------
  // No project selected
  // ---------------------------------------------------------------------------
  if (!project) {
    return (
      <div className="mx-auto max-w-4xl p-6 sm:p-8">
        <div className="space-y-4 rounded-lg border bg-white p-8 text-center" style={{ borderColor: '#9ED4C8' }}>
          <h2 className="text-lg font-semibold text-slate-900">No Project Selected</h2>
          <p className="text-sm text-slate-500">Select a project to view its health dashboard.</p>
          <button
            type="button"
            onClick={() => onNavigate('projects')}
            className="mt-2 rounded-lg bg-[#0B6B63] px-4 py-2 text-sm font-medium text-white hover:bg-[#084F49] transition-colors"
          >
            Browse Projects
          </button>
        </div>
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------
  return (
    <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8 space-y-6">
      {/* ─── Top bar ─── */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => onNavigate('overview')}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700 transition-colors"
            aria-label="Back to overview"
          >
            <ArrowLeft className="h-5 w-5" />
          </button>
          <div>
            <h1 className="text-xl font-bold text-slate-900 font-display">
              {project.name} — Dashboard
            </h1>
            <p className="text-xs text-slate-500 mt-0.5">
              Comprehensive health, bottleneck, workload, and sprint analysis
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {/* Last synced */}
          {lastSyncedAt && (
            <span className="inline-flex items-center gap-1 text-[11px] text-slate-400">
              <Clock className="h-3.5 w-3.5" />
              Last synced:{' '}
              {new Date(lastSyncedAt).toLocaleString('en-US', {
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
              })}
            </span>
          )}

          {/* Manual refresh */}
          <button
            type="button"
            onClick={handleRefresh}
            disabled={isSyncing}
            className={`w-full sm:w-auto inline-flex items-center justify-center gap-2 rounded-lg border px-3 py-2 text-xs font-medium transition-colors ${
              isSyncing
                ? 'border-slate-200 bg-slate-50 text-slate-400 cursor-not-allowed'
                : 'border-[#9ED4C8] bg-white text-[#0B6B63] hover:bg-[#EAF8F3]'
            }`}
          >
            <RefreshCw className={`h-4 w-4 ${isSyncing ? 'animate-spin' : ''}`} />
            {isSyncing ? 'Syncing…' : 'Sync & Refresh'}
          </button>
        </div>
      </div>

      {/* ─── Grid layout ─── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left column — Health Score + Sprint Velocity */}
        <div className="space-y-6">
          <HealthScoreCard data={healthData} isLoading={loadingHealth} error={errorHealth} />
          <SprintVelocityCard data={sprints} isLoading={loadingSprints} error={errorSprints} />
        </div>

        {/* Centre column — Bottlenecks + Workload */}
        <div className="space-y-6">
          <BottlenecksList items={bottlenecks} isLoading={loadingBottlenecks} error={errorBottlenecks} />
          <WorkloadChart data={workload} isLoading={loadingWorkload} error={errorWorkload} />
        </div>

        {/* Right column (spans full width on lg) — Stale issues table */}
        <div className="lg:col-span-1">
          <StaleIssuesTable data={staleIssues} isLoading={loadingStale} error={errorStale} />
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
