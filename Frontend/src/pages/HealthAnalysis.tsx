import React, { useState, useEffect } from 'react';
import type { PageView } from '../types';
import {
  metricsApi,
  type ProjectResponse,
  type MetricsBreakdownData,
} from '../services/api';
import {
  Info,
  X,
  ShieldCheck,
  AlertCircle,
  ArrowLeft,
  RefreshCw,
} from 'lucide-react';

interface HealthAnalysisProps {
  project: ProjectResponse | null;
  onNavigate: (view: PageView) => void;
}

const TEAL = '#16A34A';
const CRIMSON = '#CC1F2E';
const BORDER = '#9ED4C8';

export const HealthAnalysis: React.FC<HealthAnalysisProps> = ({
  project,
  onNavigate,
}) => {
  const [metricsBreakdown, setMetricsBreakdown] =
    useState<MetricsBreakdownData | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [showCalculationModal, setShowCalculationModal] =
    useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const fetchBreakdown = async (projectId: string) => {
    setIsLoading(true);
    setError(null);

    try {
      const data = await metricsApi.getMetricsBreakdown(projectId);
      setMetricsBreakdown(data);
    } catch (err: unknown) {
      setError(
        err instanceof Error
          ? err.message
          : 'Failed to fetch metrics breakdown.'
      );
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (project?.id) {
      fetchBreakdown(project.id);
    } else {
      setMetricsBreakdown(null);
    }
  }, [project?.id]);

  if (!project) {
    return (
      <div className="mx-auto max-w-4xl p-6 sm:p-8">
        <div
          className="space-y-4 rounded-lg border bg-white p-8 text-center"
          style={{ borderColor: BORDER }}
        >
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-lg bg-[#CDEFE6] text-[#0B6B63]">
            <ShieldCheck className="h-6 w-6" />
          </div>

          <h2 className="text-lg font-semibold text-slate-900">
            No Project Selected
          </h2>

          <p className="text-sm text-slate-500">
            Please select an active project to view health analysis.
          </p>

          <button
            type="button"
            onClick={() => onNavigate('projects')}
            className="rounded-md bg-[#0B6B63] px-4 py-2.5 text-xs font-semibold text-white hover:bg-[#084F49]"
          >
            View Projects
          </button>
        </div>
      </div>
    );
  }

  const score =
    metricsBreakdown?.health_score !== null &&
    metricsBreakdown?.health_score !== undefined
      ? Math.round(metricsBreakdown.health_score)
      : null;

  const status = metricsBreakdown?.status || 'Insufficient Data';

  const getStatusColor = (st: string) => {
    switch (st) {
      case 'Good':
        return 'text-[#15803D] bg-[#DCFCE7] border-[#86EFAC]';
      case 'Caution':
        return 'text-amber-800 bg-amber-50 border-amber-200';
      case 'At Risk':
        return 'text-[#CC1F2E] bg-[#FEE2E2] border-[#F8A9A9]';
      default:
        return 'text-slate-600 bg-slate-50 border-slate-200';
    }
  };

  const getGaugeStroke = (st: string) => {
    switch (st) {
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

  const indicators = [
    {
      id: 'bottlenecks',
      title: 'Review Bottlenecks (Pull Requests)',
      indicator: metricsBreakdown?.indicators?.bottlenecks,
      description:
        'Aging open pull requests and queue review latencies exceeding SLA thresholds.',
      evidence: metricsBreakdown?.indicators?.bottlenecks?.details
        ? `${metricsBreakdown.indicators.bottlenecks.details.open_prs_count ?? 0} open PR(s), ${metricsBreakdown.indicators.bottlenecks.details.aging_prs_count ?? 0} aging (>48h)`
        : 'Telemetry not synced',
    },
    {
      id: 'workload',
      title: 'Workload & Concentration (Bus Factor)',
      indicator: metricsBreakdown?.indicators?.workload,
      description:
        'Distribution of contributions across developers. High concentration flags bus-factor risk.',
      evidence: metricsBreakdown?.indicators?.workload?.details
        ? `${metricsBreakdown.indicators.workload.details.total_contributors ?? 0} active contributors, top contributor share: ${metricsBreakdown.indicators.workload.details.top_contributor_percentage ?? 0}%`
        : 'Telemetry not synced',
    },
    {
      id: 'stale_issues',
      title: 'Issue Freshness & Inactivity',
      indicator: metricsBreakdown?.indicators?.stale_issues,
      description:
        'Unresolved issues with no activity exceeding project threshold days.',
      evidence: metricsBreakdown?.indicators?.stale_issues?.details
        ? `${metricsBreakdown.indicators.stale_issues.details.stale_issues_count ?? 0} stale out of ${metricsBreakdown.indicators.stale_issues.details.open_issues_count ?? 0} open issues`
        : 'Telemetry not synced',
    },
    {
      id: 'schedule_risk',
      title: 'Schedule & Milestone Velocity',
      indicator: metricsBreakdown?.indicators?.schedule_risk,
      description:
        'Milestone target dates and sprint task completion velocities.',
      evidence: metricsBreakdown?.indicators?.schedule_risk?.details
        ? `${metricsBreakdown.indicators.schedule_risk.details.total_completed_items ?? 0}/${metricsBreakdown.indicators.schedule_risk.details.total_planned_items ?? 0} tasks completed`
        : 'Milestones not configured',
    },
  ];

  const circumference = 2 * Math.PI * 66;
  const safeScore =
    score !== null ? Math.min(100, Math.max(0, score)) : 0;

  return (
    <div className="mx-auto max-w-[1500px] space-y-5 p-4 sm:p-6 lg:p-8">

      <section className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <button
            type="button"
            onClick={() => onNavigate('overview')}
            className="mb-2 inline-flex items-center gap-1.5 text-xs font-medium text-slate-500 hover:text-[#0B6B63]"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to Project Overview
          </button>

          <h1 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
            Health Index Analysis
          </h1>

          <p className="mt-1 text-sm text-slate-500">
            Explainable weighted indicator assessment for{' '}
            <span className="font-semibold text-slate-800">
              {project.name}
            </span>.
          </p>
        </div>

        <button
          type="button"
          onClick={() => fetchBreakdown(project.id)}
          disabled={isLoading}
          className="inline-flex items-center justify-center gap-2 self-start rounded-md border border-[#9ED4C8] bg-white px-4 py-2.5 text-xs font-semibold text-slate-700 hover:border-[#0B6B63] hover:text-[#0B6B63] disabled:cursor-not-allowed disabled:opacity-60 sm:self-auto"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          {isLoading ? 'Refreshing...' : 'Refresh'}
        </button>
      </section>

      {isLoading && (
        <div className="rounded-md border border-[#9ED4C8] bg-white px-4 py-3 text-sm text-slate-600">
          Loading health metrics...
        </div>
      )}

      {error && (
        <div className="flex flex-col justify-between gap-3 rounded-md border border-[#F8A9A9] bg-white p-4 sm:flex-row sm:items-center">
          <div className="flex items-start gap-3">
            <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-[#CC1F2E]" />

            <div>
              <p className="text-sm font-semibold text-[#CC1F2E]">
                Failed to load health metrics
              </p>
              <p className="mt-1 text-sm text-slate-600">{error}</p>
            </div>
          </div>

          <button
            type="button"
            onClick={() => fetchBreakdown(project.id)}
            className="shrink-0 rounded-md bg-[#CC1F2E] px-4 py-2 text-xs font-semibold text-white hover:bg-[#CC1F2E]"
          >
            Retry
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 items-start gap-5 lg:grid-cols-12">

        <section
          className="flex flex-col justify-between gap-6 rounded-lg border bg-white p-5 sm:p-7 lg:col-span-5"
          style={{ borderColor: BORDER }}
        >
          <div>
            <h2 className="text-lg font-semibold text-slate-900">
              Overall Composite Score
            </h2>
            <p className="mt-1 text-xs text-slate-500">
              Automated weighted calculation
            </p>
          </div>

          <div className="flex flex-col items-center justify-center py-4">
            <div className="relative h-52 w-52 max-w-full sm:h-56 sm:w-56">
              <svg
                className="h-full w-full -rotate-90"
                viewBox="0 0 160 160"
                role="img"
                aria-label={`Health score: ${score ?? 'No data'}`}
              >
                <circle
                  cx="80"
                  cy="80"
                  r="66"
                  stroke="#EAF8F3"
                  strokeWidth="14"
                  fill="none"
                />

                <circle
                  cx="80"
                  cy="80"
                  r="66"
                  stroke={getGaugeStroke(status)}
                  strokeWidth="14"
                  strokeDasharray={circumference}
                  strokeDashoffset={
                    circumference * (1 - (score !== null ? safeScore / 100 : 0))
                  }
                  strokeLinecap="round"
                  fill="none"
                />
              </svg>

              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-5xl font-bold tabular-nums tracking-tight text-slate-900 sm:text-6xl">
                  {score !== null ? score : '--'}
                </span>

                <span
                  className={`mt-2 rounded-md border px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider ${getStatusColor(status)}`}
                >
                  {status}
                </span>
              </div>
            </div>

            <p className="mt-3 text-xs text-slate-500">
              Overall project health score
            </p>
          </div>

          <div
            className="flex flex-col justify-between gap-3 border-t pt-4 sm:flex-row sm:items-center"
            style={{ borderColor: BORDER }}
          >
            <button
              type="button"
              onClick={() => setShowCalculationModal(true)}
              className="inline-flex items-center gap-2 text-xs font-semibold text-[#0B6B63] hover:underline"
            >
              <Info className="h-4 w-4" />
              How is this score calculated?
            </button>

            <span className="text-xs text-slate-400">
              Evaluated:{' '}
              {metricsBreakdown
                ? new Date(metricsBreakdown.evaluated_at).toLocaleTimeString()
                : 'N/A'}
            </span>
          </div>
        </section>

        <section className="space-y-4 lg:col-span-7">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-700">
              Health Indicators
            </h2>

            <span className="text-xs text-slate-500">
              Four assessment areas
            </span>
          </div>

          {indicators.map((item) => {
            const ind = item.indicator;

            const indScore =
              ind?.score !== null && ind?.score !== undefined
                ? Math.round(ind.score)
                : null;

            const indStatus = ind?.status || 'Insufficient Data';

            const weightPercent = metricsBreakdown?.weights_used?.[item.id]
              ? `${Math.round(metricsBreakdown.weights_used[item.id] * 100)}%`
              : '25%';

            const indicatorColor =
              indStatus === 'Good'
                ? TEAL
                : indStatus === 'Caution'
                  ? '#B45309'
                  : indStatus === 'At Risk'
                    ? CRIMSON
                    : '#5F7C79';

            return (
              <article
                key={item.id}
                className="rounded-lg border bg-white p-4 sm:p-5"
                style={{ borderColor: BORDER }}
              >
                <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="text-sm font-semibold text-slate-900">
                        {item.title}
                      </h3>

                      <span
                        className={`rounded-md border px-2 py-1 text-[10px] font-semibold ${getStatusColor(indStatus)}`}
                      >
                        {indStatus}
                      </span>
                    </div>

                    <p className="mt-2 text-xs leading-relaxed text-slate-500">
                      {item.description}
                    </p>
                  </div>

                  <div className="shrink-0 sm:text-right">
                    <p className="text-2xl font-bold tabular-nums text-slate-900">
                      {indScore !== null ? `${indScore}%` : '--'}
                    </p>

                    <p className="mt-0.5 text-[11px] text-slate-500">
                      Weight: {weightPercent}
                    </p>
                  </div>
                </div>

                <div className="mt-4">
                  <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                    <div
                      className="h-full rounded-full"
                      style={{
                        width: `${indScore !== null ? Math.min(100, Math.max(0, indScore)) : 0}%`,
                        backgroundColor: indicatorColor,
                      }}
                    />
                  </div>
                </div>

                <div
                  className="mt-4 grid grid-cols-1 gap-3 border-t pt-3 sm:grid-cols-2"
                  style={{ borderColor: BORDER }}
                >
                  <div className="min-w-0">
                    <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                      Supporting Evidence
                    </p>

                    <p className="mt-1 break-words font-mono text-xs leading-relaxed text-slate-700">
                      {item.evidence}
                    </p>
                  </div>

                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                      Data Status
                    </p>

                    <p className="mt-1 text-xs font-medium text-slate-700">
                      {ind?.data_status || 'Unknown'}
                    </p>
                  </div>
                </div>
              </article>
            );
          })}
        </section>
      </div>

      {showCalculationModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-[#032826]/70 p-4"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) {
              setShowCalculationModal(false);
            }
          }}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="calculation-modal-title"
            className="relative max-h-[85vh] w-full max-w-xl space-y-5 overflow-y-auto rounded-lg border bg-white p-5 sm:p-7"
            style={{ borderColor: BORDER }}
          >
            <button
              type="button"
              onClick={() => setShowCalculationModal(false)}
              aria-label="Close calculation details"
              className="absolute right-4 top-4 rounded-md p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
            >
              <X className="h-5 w-5" />
            </button>

            <div className="pr-8">
              <h3
                id="calculation-modal-title"
                className="text-lg font-semibold text-slate-900"
              >
                Dynamic Weighted Health Formula
              </h3>

              <p className="mt-2 text-xs leading-relaxed text-slate-600">
                The Composite Health Score dynamically normalizes across
                all available telemetry inputs. If optional sources (such
                as sprints or PRs) have not been configured, the engine
                avoids false zero penalties by dynamically re-weighting
                active indicators so that total weight equals 100%.
              </p>
            </div>

            <div
              className="space-y-3 rounded-md border bg-[#EAF8F3] p-4"
              style={{ borderColor: BORDER }}
            >
              <p className="text-xs font-semibold text-slate-800">
                Active Weights Distribution
              </p>

              {metricsBreakdown?.weights_used &&
              Object.entries(metricsBreakdown.weights_used).length > 0 ? (
                Object.entries(metricsBreakdown.weights_used).map(
                  ([key, weight]) => (
                    <div
                      key={key}
                      className="flex items-center justify-between gap-3 text-xs"
                    >
                      <span className="capitalize text-slate-600">
                        {key.replace('_', ' ')}
                      </span>

                      <span className="font-semibold tabular-nums text-slate-900">
                        {Math.round(weight * 100)}%
                      </span>
                    </div>
                  )
                )
              ) : (
                <p className="text-xs text-slate-500">
                  Weight distribution is not available.
                </p>
              )}
            </div>

            <div>
              <p className="mb-3 text-xs font-semibold text-slate-800">
                Score Classifications
              </p>

              <div className="space-y-2">
                <div className="flex items-center justify-between gap-3 text-xs">
                  <span className="font-semibold text-[#0B6B63]">
                    Good
                  </span>
                  <span className="text-slate-600">Score ≥ 75</span>
                </div>

                <div className="flex items-center justify-between gap-3 text-xs">
                  <span className="font-semibold text-amber-700">
                    Caution
                  </span>
                  <span className="text-slate-600">
                    50 ≤ Score &lt; 75
                  </span>
                </div>

                <div className="flex items-center justify-between gap-3 text-xs">
                  <span className="font-semibold text-[#CC1F2E]">
                    At Risk
                  </span>
                  <span className="text-slate-600">Score &lt; 50</span>
                </div>

                <div className="flex items-center justify-between gap-3 text-xs">
                  <span className="font-semibold text-slate-600">
                    Insufficient Data
                  </span>
                  <span className="text-slate-600">Telemetry missing</span>
                </div>
              </div>
            </div>

            <div className="flex justify-end border-t pt-4" style={{ borderColor: BORDER }}>
              <button
                type="button"
                onClick={() => setShowCalculationModal(false)}
                className="rounded-md bg-[#0B6B63] px-4 py-2 text-xs font-semibold text-white hover:bg-[#084F49]"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
