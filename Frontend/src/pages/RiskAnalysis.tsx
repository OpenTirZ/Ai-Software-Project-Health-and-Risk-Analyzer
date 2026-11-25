import React, { useState, useEffect } from 'react';
import type { PageView } from '../types';
import {
  metricsApi,
  type ProjectResponse,
  type HealthSummaryData,
} from '../services/api';
import {
  AlertTriangle,
  Info,
  ChevronRight,
  ShieldCheck,
  RefreshCw,
  ArrowLeft,
} from 'lucide-react';

interface RiskAnalysisProps {
  project: ProjectResponse | null;
  onNavigate: (view: PageView) => void;
}

type RiskFilter = 'All' | 'High' | 'Medium' | 'Low';

export const RiskAnalysis: React.FC<RiskAnalysisProps> = ({
  project,
  onNavigate,
}) => {
  const [healthSummary, setHealthSummary] =
    useState<HealthSummaryData | null>(null);
  const [filter, setFilter] = useState<RiskFilter>('All');
  const [selectedRiskId, setSelectedRiskId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const fetchRisks = async (projectId: string) => {
    setIsLoading(true);
    setError(null);

    try {
      const data = await metricsApi.getHealthSummary(projectId);
      setHealthSummary(data);

      if (data.active_flags && data.active_flags.length > 0) {
        setSelectedRiskId(data.active_flags[0].id);
      } else {
        setSelectedRiskId(null);
      }
    } catch (err: unknown) {
      setError(
        err instanceof Error
          ? err.message
          : 'Failed to fetch project risk analysis.',
      );
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (project?.id) {
      fetchRisks(project.id);
    }
  }, [project?.id]);

  if (!project) {
    return (
      <div className="mx-auto max-w-4xl p-8 text-center">
        <div className="rounded-xl border border-[#9ED4C8] bg-white p-8">
          <p className="text-sm text-[#3F5F5C]">
            Please select an active project to view risk analysis.
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

  const allFlags = healthSummary?.active_flags || [];

  const filteredFlags = allFlags.filter((flag) => {
    if (filter === 'All') return true;
    return flag.severity.toLowerCase() === filter.toLowerCase();
  });

  const highCount = allFlags.filter(
    (flag) => flag.severity.toLowerCase() === 'high',
  ).length;

  const mediumCount = allFlags.filter(
    (flag) => flag.severity.toLowerCase() === 'medium',
  ).length;

  const lowCount = allFlags.filter(
    (flag) => flag.severity.toLowerCase() === 'low',
  ).length;

  const selectedRisk =
    allFlags.find((flag) => flag.id === selectedRiskId) || allFlags[0] || null;

  const severityStyles = (severity: string) => {
    switch (severity.toLowerCase()) {
      case 'high':
        return 'border-[#CC1F2E]/20 bg-[#CC1F2E]/5 text-[#CC1F2E]';
      case 'medium':
        return 'border-[#B45309]/25 bg-[#B45309]/5 text-[#B45309]';
      default:
        return 'border-[#9ED4C8] bg-[#CDEFE6] text-[#0B6B63]';
    }
  };

  const statCards = [
    {
      label: 'High',
      count: highCount,
      color: 'text-[#CC1F2E]',
      border: 'border-l-[#CC1F2E]',
    },
    {
      label: 'Medium',
      count: mediumCount,
      color: 'text-[#B45309]',
      border: 'border-l-[#B45309]',
    },
    {
      label: 'Low',
      count: lowCount,
      color: 'text-[#15803D]',
      border: 'border-l-[#16A34A]',
    },
  ];

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
            Risk &amp; Vulnerability Analysis
          </h1>

          <p className="mt-1 text-sm text-[#3F5F5C]">
            <span className="font-semibold tabular-nums text-[#0E2A2A]">
              {allFlags.length}
            </span>{' '}
            active risk signals detected for{' '}
            <span className="font-semibold text-[#0E2A2A]">
              {project.name}
            </span>
            .
          </p>
        </div>

        <button
          onClick={() => fetchRisks(project.id)}
          disabled={isLoading}
          className="w-full sm:w-auto inline-flex shrink-0 items-center justify-center gap-2 rounded-lg border border-[#9ED4C8] bg-white px-4 py-2.5 text-sm font-semibold text-[#3F5F5C] hover:bg-[#EAF8F3] disabled:cursor-not-allowed disabled:opacity-60"
        >
          <RefreshCw className="h-4 w-4" />
          {isLoading ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>

      {error && (
        <div
          role="alert"
          className="flex flex-col justify-between gap-3 rounded-xl border border-[#CC1F2E]/20 bg-[#CC1F2E]/5 p-4 sm:flex-row sm:items-center"
        >
          <div className="flex items-start gap-3">
            <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-[#CC1F2E]" />
            <div>
              <p className="text-sm font-semibold text-[#CC1F2E]">
                Failed to load risk analysis
              </p>
              <p className="mt-1 text-sm text-[#CC1F2E]">{error}</p>
            </div>
          </div>

          <button
            onClick={() => fetchRisks(project.id)}
            className="shrink-0 self-start rounded-lg bg-[#CC1F2E] px-3 py-2 text-sm font-semibold text-white hover:bg-[#CC1F2E] sm:self-center"
          >
            Retry
          </button>
        </div>
      )}

      <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-center">
        <div
          className="flex flex-wrap items-center gap-1 rounded-lg border border-[#9ED4C8] bg-white p-1"
          aria-label="Filter risks by severity"
        >
          {(['All', 'High', 'Medium', 'Low'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setFilter(tab)}
              aria-pressed={filter === tab}
              className={`rounded-md px-4 py-2 text-sm font-semibold ${
                filter === tab
                  ? 'bg-[#0B6B63] text-white'
                  : 'text-[#3F5F5C] hover:bg-[#CDEFE6] hover:text-[#0B6B63]'
              }`}
            >
              {tab}
            </button>
          ))}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {statCards.map((stat) => (
            <div
              key={stat.label}
              className={`min-w-0 rounded-lg border border-[#9ED4C8] border-l-4 ${stat.border} bg-white px-4 py-3`}
            >
              <p className="text-xs font-semibold uppercase tracking-wide text-[#5F7C79]">
                {stat.label}
              </p>
              <p
                className={`mt-1 text-2xl font-bold tabular-nums ${stat.color}`}
              >
                {stat.count}
              </p>
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 items-start gap-5 lg:grid-cols-12">

        <section className="space-y-3 lg:col-span-8">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold text-[#0E2A2A]">
              Detected Risk Signals
            </h2>
            <span className="text-xs font-medium text-[#5F7C79] tabular-nums">
              {filteredFlags.length} shown
            </span>
          </div>

          {isLoading && !healthSummary ? (
            <div className="rounded-xl border border-[#9ED4C8] bg-white p-10 text-center">
              <p className="text-sm text-[#5F7C79]">
                Loading risk analysis...
              </p>
            </div>
          ) : filteredFlags.length === 0 ? (
            <div className="rounded-xl border border-[#9ED4C8] bg-white px-6 py-12 text-center">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-[#CDEFE6] text-[#0B6B63]">
                <ShieldCheck className="h-6 w-6" />
              </div>

              <h3 className="mt-4 text-base font-semibold text-[#0E2A2A]">
                {allFlags.length === 0
                  ? 'Zero Active Risk Flags'
                  : `No ${filter} Severity Risks`}
              </h3>

              <p className="mx-auto mt-2 max-w-sm text-sm leading-6 text-[#5F7C79]">
                {allFlags.length === 0
                  ? 'All telemetry indicators are operating within normal project boundaries.'
                  : `No items matched the active filter "${filter}".`}
              </p>
            </div>
          ) : (
            filteredFlags.map((risk) => {
              const isSelected = selectedRisk?.id === risk.id;
              const severity = risk.severity.toUpperCase();

              return (
                <div
                  key={risk.id}
                  role="button"
                  tabIndex={0}
                  aria-pressed={isSelected}
                  onClick={() => setSelectedRiskId(risk.id)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault();
                      setSelectedRiskId(risk.id);
                    }
                  }}
                  className={`cursor-pointer rounded-xl border bg-white p-5 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0B6B63] ${
                    isSelected
                      ? 'border-[#0B6B63]'
                      : 'border-[#9ED4C8] hover:border-[#0B6B63]'
                  }`}
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span
                      className={`inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-bold ${severityStyles(
                        risk.severity,
                      )}`}
                    >
                      <AlertTriangle className="h-3.5 w-3.5" />
                      {severity}
                    </span>

                    <span className="text-xs font-medium capitalize text-[#5F7C79]">
                      {risk.type.replace(/_/g, ' ')}
                    </span>
                  </div>

                  <h3 className="mt-3 text-base font-semibold leading-6 text-[#0E2A2A]">
                    {risk.message}
                  </h3>

                  {risk.evidence && (
                    <div className="mt-4 border-t border-[#9ED4C8] pt-3">
                      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-[#3F5F5C]">
                        Supporting Evidence
                      </p>

                      <div className="flex flex-wrap gap-2">
                        {Object.entries(risk.evidence).map(([key, value]) => (
                          <span
                            key={key}
                            className="max-w-full break-words rounded-md border border-[#9ED4C8] bg-[#EAF8F3] px-2.5 py-1.5 text-xs text-[#3F5F5C]"
                          >
                            <span className="font-semibold text-[#0E2A2A]">
                              {key}:
                            </span>{' '}
                            <span className="font-mono">
                              {typeof value === 'object'
                                ? JSON.stringify(value)
                                : String(value)}
                            </span>
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              );
            })
          )}
        </section>

        <aside className="rounded-xl border border-[#9ED4C8] bg-white p-5 lg:sticky lg:top-6 lg:col-span-4">
          <div className="flex items-center gap-2 border-b border-[#9ED4C8] pb-4">
            <Info className="h-5 w-5 text-[#0B6B63]" />
            <h2 className="text-base font-semibold text-[#0E2A2A]">
              Explainable Risk Details
            </h2>
          </div>

          {selectedRisk ? (
            <div className="space-y-5 pt-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-[#5F7C79]">
                  Active Flag
                </p>
                <p className="mt-1 text-sm font-semibold leading-6 text-[#0E2A2A]">
                  {selectedRisk.message}
                </p>
                <span
                  className={`mt-2 inline-flex rounded-md border px-2 py-1 text-xs font-bold ${severityStyles(
                    selectedRisk.severity,
                  )}`}
                >
                  {selectedRisk.severity.toUpperCase()} SEVERITY
                </span>
              </div>

              <div className="rounded-lg border border-[#9ED4C8] bg-[#EAF8F3] p-4">
                <p className="mb-2 text-sm font-semibold text-[#0E2A2A]">
                  Risk Description &amp; Evidence
                </p>
                <p className="text-sm leading-6 text-[#3F5F5C]">
                  This flag was triggered because repository activity exceeded
                  the project SLA threshold. Review the evidence parameters and
                  inspect individual items in Activity.
                </p>
              </div>

              <div>
                <p className="mb-3 text-sm font-semibold text-[#0E2A2A]">
                  Recommended Next Steps
                </p>
                <ul className="list-disc space-y-2 pl-5 text-sm leading-5 text-[#3F5F5C]">
                  <li>
                    Review aging PR queues or reassign pending code reviews.
                  </li>
                  <li>
                    Verify if stale issues can be resolved, closed, or
                    reprioritized.
                  </li>
                  <li>
                    Review project threshold settings if this behavior is
                    expected.
                  </li>
                </ul>
              </div>

              <button
                onClick={() => onNavigate('activity')}
                className="flex w-full items-center justify-center gap-2 rounded-lg bg-[#0B6B63] px-4 py-3 text-sm font-semibold text-white hover:bg-[#084F49] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0B6B63]"
              >
                Inspect in Activity Logs
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          ) : (
            <p className="py-8 text-center text-sm text-[#5F7C79]">
              Select a risk flag to inspect its evidence.
            </p>
          )}
        </aside>
      </div>
    </div>
  );
};
