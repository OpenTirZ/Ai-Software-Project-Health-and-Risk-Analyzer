import React, { useState, useEffect } from 'react';
import type { PageView } from '../types';
import {
  metricsApi,
  type ProjectResponse,
  type MetricsBreakdownData,
} from '../services/api';
import { Info, X, ShieldCheck, AlertCircle, ArrowLeft, RefreshCw } from 'lucide-react';

interface HealthAnalysisProps {
  project: ProjectResponse | null;
  onNavigate: (view: PageView) => void;
}

export const HealthAnalysis: React.FC<HealthAnalysisProps> = ({ project, onNavigate }) => {
  const [metricsBreakdown, setMetricsBreakdown] = useState<MetricsBreakdownData | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [showCalculationModal, setShowCalculationModal] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const fetchBreakdown = async (projectId: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await metricsApi.getMetricsBreakdown(projectId);
      setMetricsBreakdown(data);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch metrics breakdown.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (project?.id) {
      fetchBreakdown(project.id);
    }
  }, [project?.id]);

  if (!project) {
    return (
      <div className="p-8 max-w-4xl mx-auto text-center space-y-4">
        <p className="text-slate-500">Please select an active project to view health analysis.</p>
        <button
          onClick={() => onNavigate('projects')}
          className="px-4 py-2 bg-indigo-600 text-white rounded-xl text-xs font-bold"
        >
          View Projects
        </button>
      </div>
    );
  }

  const score = metricsBreakdown?.health_score !== null && metricsBreakdown?.health_score !== undefined
    ? Math.round(metricsBreakdown.health_score)
    : null;

  const status = metricsBreakdown?.status || 'Insufficient Data';

  const getStatusColor = (st: string) => {
    switch (st) {
      case 'Good':
        return 'text-emerald-700 bg-emerald-50 border-emerald-200';
      case 'Caution':
        return 'text-amber-700 bg-amber-50 border-amber-200';
      case 'At Risk':
        return 'text-rose-700 bg-rose-50 border-rose-200';
      default:
        return 'text-slate-600 bg-slate-100 border-slate-200';
    }
  };

  const getGaugeStroke = (st: string) => {
    switch (st) {
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

  const indicators = [
    {
      id: 'bottlenecks',
      title: 'Review Bottlenecks (Pull Requests)',
      indicator: metricsBreakdown?.indicators?.bottlenecks,
      description: 'Aging open pull requests and queue review latencies exceeding SLA thresholds.',
      evidence: metricsBreakdown?.indicators?.bottlenecks?.details
        ? `${metricsBreakdown.indicators.bottlenecks.details.open_prs_count ?? 0} open PR(s), ${metricsBreakdown.indicators.bottlenecks.details.aging_prs_count ?? 0} aging (>48h)`
        : 'Telemetry not synced',
    },
    {
      id: 'workload',
      title: 'Workload & Concentration (Bus Factor)',
      indicator: metricsBreakdown?.indicators?.workload,
      description: 'Distribution of contributions across developers. High concentration flags bus-factor risk.',
      evidence: metricsBreakdown?.indicators?.workload?.details
        ? `${metricsBreakdown.indicators.workload.details.total_contributors ?? 0} active contributors, top contributor share: ${metricsBreakdown.indicators.workload.details.top_contributor_percentage ?? 0}%`
        : 'Telemetry not synced',
    },
    {
      id: 'issues',
      title: 'Issue Freshness & Inactivity',
      indicator: metricsBreakdown?.indicators?.stale_issues,
      description: 'Unresolved issues with no activity exceeding project threshold days.',
      evidence: metricsBreakdown?.indicators?.stale_issues?.details
        ? `${metricsBreakdown.indicators.stale_issues.details.stale_issues_count ?? 0} stale out of ${metricsBreakdown.indicators.stale_issues.details.open_issues_count ?? 0} open issues`
        : 'Telemetry not synced',
    },
    {
      id: 'schedule',
      title: 'Schedule & Milestone Velocity',
      indicator: metricsBreakdown?.indicators?.schedule_risk,
      description: 'Milestone target dates and sprint task completion velocities.',
      evidence: metricsBreakdown?.indicators?.schedule_risk?.details
        ? `${metricsBreakdown.indicators.schedule_risk.details.total_completed_items ?? 0}/${metricsBreakdown.indicators.schedule_risk.details.total_planned_items ?? 0} tasks completed`
        : 'Milestones not configured',
    },
  ];

  return (
    <div className="p-6 md:p-8 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <button
            onClick={() => onNavigate('overview')}
            className="inline-flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-800 font-medium mb-1 cursor-pointer"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Back to Project Overview</span>
          </button>
          <h1 className="text-2xl md:text-3xl font-bold text-slate-900 tracking-tight">
            Health Index Analysis
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Explainable weighted indicator assessment for <span className="font-semibold text-slate-700">{project.name}</span>.
          </p>
        </div>

        <button
          onClick={() => fetchBreakdown(project.id)}
          disabled={isLoading}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white border border-slate-200 text-xs font-semibold text-slate-700 rounded-lg shadow-sm hover:bg-slate-50 cursor-pointer"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Main Analysis Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Large Gauge Card (5 cols) */}
        <div className="lg:col-span-5 bg-white rounded-2xl p-8 border border-slate-200/90 shadow-sm flex flex-col items-center justify-between text-center min-h-[460px]">
          <div className="w-full text-left">
            <h2 className="text-xl font-bold text-slate-900">
              Overall Composite Score
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">Automated weighted calculation</p>
          </div>

          {/* Huge Circular Gauge */}
          <div className="relative my-auto w-56 h-56 flex items-center justify-center">
            <svg className="w-full h-full transform -rotate-90" viewBox="0 0 160 160">
              <circle
                cx="80"
                cy="80"
                r="66"
                stroke="#f1f5f9"
                strokeWidth="14"
                fill="transparent"
              />
              <circle
                cx="80"
                cy="80"
                r="66"
                stroke={getGaugeStroke(status)}
                strokeWidth="14"
                strokeDasharray={2 * Math.PI * 66}
                strokeDashoffset={
                  score !== null
                    ? (2 * Math.PI * 66) * (1 - score / 100)
                    : (2 * Math.PI * 66) * (1 - 0.05)
                }
                strokeLinecap="round"
                fill="transparent"
              />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-6xl font-extrabold text-slate-900 tracking-tight">
                {score !== null ? score : '--'}
              </span>
              <span className="text-sm font-bold uppercase tracking-widest mt-1">
                {status}
              </span>
            </div>
          </div>

          <div className="w-full pt-4 border-t border-slate-100 flex items-center justify-between">
            <button
              onClick={() => setShowCalculationModal(true)}
              className="text-xs font-semibold text-indigo-600 hover:text-indigo-800 transition-colors flex items-center gap-1.5 cursor-pointer"
            >
              <Info className="w-4 h-4" />
              <span>How is this score calculated?</span>
            </button>
            <span className="text-xs text-slate-400">
              Evaluated: {metricsBreakdown ? new Date(metricsBreakdown.evaluated_at).toLocaleTimeString() : 'N/A'}
            </span>
          </div>
        </div>

        {/* Right Indicators Breakdown (7 cols) */}
        <div className="lg:col-span-7 space-y-4">
          {indicators.map((item) => {
            const ind = item.indicator;
            const indScore = ind?.score !== null && ind?.score !== undefined ? Math.round(ind.score) : null;
            const indStatus = ind?.status || 'Insufficient Data';
            const weightPercent = metricsBreakdown?.weights_used?.[item.id]
              ? `${Math.round(metricsBreakdown.weights_used[item.id] * 100)}%`
              : '25%';

            return (
              <div
                key={item.id}
                className="bg-white rounded-2xl p-5 border border-slate-200/90 shadow-sm flex flex-col justify-between hover:border-slate-300 transition-all space-y-3"
              >
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="text-base font-bold text-slate-900">
                        {item.title}
                      </h3>
                      <span className={`px-2.5 py-0.5 rounded-full text-xs font-bold border ${getStatusColor(indStatus)}`}>
                        {indStatus}
                      </span>
                    </div>
                    <p className="text-xs text-slate-500 mt-1">
                      {item.description}
                    </p>
                  </div>

                  <div className="text-right shrink-0">
                    <span className="text-2xl font-extrabold text-slate-900">
                      {indScore !== null ? `${indScore}%` : '--'}
                    </span>
                    <span className="block text-[11px] font-medium text-slate-400">
                      Weight: {weightPercent}
                    </span>
                  </div>
                </div>

                <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-xs text-slate-600 font-mono">
                  <span>Evidence: {item.evidence}</span>
                  <span className="text-slate-400">Data Status: {ind?.data_status || 'unknown'}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Dynamic Calculation Modal */}
      {showCalculationModal && (
        <div className="fixed inset-0 bg-slate-950/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl p-6 md:p-8 max-w-xl w-full border border-slate-200 shadow-2xl relative space-y-4">
            <button
              onClick={() => setShowCalculationModal(false)}
              className="absolute top-5 right-5 text-slate-400 hover:text-slate-700 transition-colors cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>

            <h3 className="text-lg font-bold text-slate-900">
              Dynamic Weighted Health Formula
            </h3>

            <p className="text-xs text-slate-600 leading-relaxed">
              The Composite Health Score dynamically normalizes across all available telemetry inputs. If optional sources (such as sprints or PRs) have not been configured, the engine avoids false zero penalties by dynamically re-weighting active indicators so that total weight equals 100%.
            </p>

            <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 text-xs font-mono text-slate-800 space-y-1">
              <p className="font-bold">Active Weights Distribution:</p>
              {metricsBreakdown?.weights_used &&
                Object.entries(metricsBreakdown.weights_used).map(([key, w]) => (
                  <div key={key} className="flex justify-between">
                    <span className="capitalize">{key.replace('_', ' ')}:</span>
                    <span className="font-semibold">{Math.round(w * 100)}%</span>
                  </div>
                ))}
            </div>

            <div className="pt-2">
              <p className="text-xs font-bold text-slate-700 mb-1">Score Classifications:</p>
              <ul className="text-xs text-slate-600 space-y-1 list-disc list-inside">
                <li><span className="font-semibold text-emerald-600">Good:</span> Score &ge; 75</li>
                <li><span className="font-semibold text-amber-600">Caution:</span> 50 &le; Score &lt; 75</li>
                <li><span className="font-semibold text-rose-600">At Risk:</span> Score &lt; 50</li>
                <li><span className="font-semibold text-slate-600">Insufficient Data:</span> Telemetry missing</li>
              </ul>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
