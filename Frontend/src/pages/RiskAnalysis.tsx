import React, { useState, useEffect } from 'react';
import type { PageView } from '../types';
import {
  metricsApi,
  type ProjectResponse,
  type HealthSummaryData,
} from '../services/api';
import { AlertTriangle, Info, ChevronRight, ShieldCheck, RefreshCw, ArrowLeft } from 'lucide-react';

interface RiskAnalysisProps {
  project: ProjectResponse | null;
  onNavigate: (view: PageView) => void;
}

export const RiskAnalysis: React.FC<RiskAnalysisProps> = ({ project, onNavigate }) => {
  const [healthSummary, setHealthSummary] = useState<HealthSummaryData | null>(null);
  const [filter, setFilter] = useState<'All' | 'High' | 'Medium' | 'Low'>('All');
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
      }
    } catch (err: any) {
      setError(err.message || 'Failed to fetch project risk analysis.');
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
      <div className="p-8 max-w-4xl mx-auto text-center space-y-4">
        <p className="text-slate-500">Please select an active project to view risk analysis.</p>
        <button
          onClick={() => onNavigate('projects')}
          className="px-4 py-2 bg-indigo-600 text-white rounded-xl text-xs font-bold"
        >
          View Projects
        </button>
      </div>
    );
  }

  const allFlags = healthSummary?.active_flags || [];

  const filteredFlags = allFlags.filter((f) => {
    if (filter === 'All') return true;
    return f.severity.toLowerCase() === filter.toLowerCase();
  });

  const highCount = allFlags.filter((f) => f.severity.toLowerCase() === 'high').length;
  const mediumCount = allFlags.filter((f) => f.severity.toLowerCase() === 'medium').length;
  const lowCount = allFlags.filter((f) => f.severity.toLowerCase() === 'low').length;

  const selectedRisk = allFlags.find((f) => f.id === selectedRiskId) || allFlags[0] || null;

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
            Risk & Vulnerability Analysis
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            {allFlags.length} active risk signals detected for <span className="font-semibold text-slate-700">{project.name}</span>.
          </p>
        </div>

        <button
          onClick={() => fetchRisks(project.id)}
          disabled={isLoading}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white border border-slate-200 text-xs font-semibold text-slate-700 rounded-lg shadow-sm hover:bg-slate-50 cursor-pointer"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Error Alert Banner */}
      {error && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-sm flex items-center justify-between gap-3 animate-fadeIn">
          <div className="flex items-center gap-2.5">
            <AlertTriangle className="w-5 h-5 text-rose-500 shrink-0" />
            <div>
              <p className="font-semibold text-xs text-rose-900">Failed to load risk analysis</p>
              <p className="text-xs text-rose-700">{error}</p>
            </div>
          </div>
          <button
            onClick={() => fetchRisks(project.id)}
            className="px-3 py-1.5 bg-rose-600 hover:bg-rose-700 text-white font-semibold text-xs rounded-lg transition-colors cursor-pointer shrink-0"
          >
            Retry
          </button>
        </div>
      )}

      {/* Filter Tabs & Stat Boxes */}
      <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4">
        {/* Filter Pills */}
        <div className="inline-flex items-center gap-2 p-1.5 bg-slate-100 rounded-xl">
          {(['All', 'High', 'Medium', 'Low'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setFilter(tab)}
              className={`px-4 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                filter === tab
                  ? 'bg-white text-blue-600 shadow-sm'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              {tab}
            </button>
          ))}
        </div>

        {/* 3 Stat Boxes */}
        <div className="flex items-center gap-3">
          <div className="bg-white rounded-xl px-5 py-3 border border-slate-200/90 shadow-sm text-center min-w-[100px]">
            <p className="text-[11px] font-extrabold uppercase text-rose-600 tracking-wider">HIGH</p>
            <p className="text-2xl font-bold text-slate-900 mt-0.5">{highCount}</p>
          </div>
          <div className="bg-white rounded-xl px-5 py-3 border border-slate-200/90 shadow-sm text-center min-w-[100px]">
            <p className="text-[11px] font-extrabold uppercase text-amber-500 tracking-wider">MEDIUM</p>
            <p className="text-2xl font-bold text-slate-900 mt-0.5">{mediumCount}</p>
          </div>
          <div className="bg-white rounded-xl px-5 py-3 border border-slate-200/90 shadow-sm text-center min-w-[100px]">
            <p className="text-[11px] font-extrabold uppercase text-blue-600 tracking-wider">LOW</p>
            <p className="text-2xl font-bold text-slate-900 mt-0.5">{lowCount}</p>
          </div>
        </div>
      </div>

      {/* Risks List & Explainability Section */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Risks List (8 cols) */}
        <div className="lg:col-span-8 space-y-4">
          {filteredFlags.length === 0 ? (
            <div className="bg-white rounded-2xl p-10 border border-slate-200/90 shadow-sm text-center space-y-3">
              <div className="w-12 h-12 bg-emerald-50 text-emerald-600 rounded-full flex items-center justify-center mx-auto">
                <ShieldCheck className="w-6 h-6" />
              </div>
              <h3 className="text-base font-bold text-slate-900">
                {allFlags.length === 0
                  ? 'Zero Active Risk Flags'
                  : `No ${filter} Severity Risks`}
              </h3>
              <p className="text-xs text-slate-500 max-w-sm mx-auto">
                {allFlags.length === 0
                  ? 'All telemetry indicators are operating within normal project boundaries.'
                  : `No items matched the active filter "${filter}".`}
              </p>
            </div>
          ) : (
            filteredFlags.map((risk) => {
              const isSelected = selectedRisk?.id === risk.id;
              const sev = risk.severity.toUpperCase();
              const badgeColor =
                sev === 'HIGH'
                  ? 'text-rose-600 bg-rose-50 border-rose-200'
                  : sev === 'MEDIUM'
                  ? 'text-amber-600 bg-amber-50 border-amber-200'
                  : 'text-blue-600 bg-blue-50 border-blue-200';

              return (
                <div
                  key={risk.id}
                  onClick={() => setSelectedRiskId(risk.id)}
                  className={`bg-white rounded-2xl p-6 border transition-all cursor-pointer ${
                    isSelected
                      ? 'border-indigo-500 ring-2 ring-indigo-50 shadow-md'
                      : 'border-slate-200/90 hover:border-slate-300 shadow-sm'
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold border ${badgeColor}`}>
                      <AlertTriangle className="w-3 h-3" />
                      <span>{sev}</span>
                    </span>
                    <span className="text-xs text-slate-400 font-mono capitalize">
                      {risk.type.replace('_', ' ')}
                    </span>
                  </div>

                  <h3 className="text-base font-bold text-slate-900 mt-2">
                    {risk.message}
                  </h3>

                  {/* Evidence items */}
                  {risk.evidence && (
                    <div className="mt-3 pt-3 border-t border-slate-100">
                      <p className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                        Supporting Evidence:
                      </p>
                      <div className="flex flex-wrap gap-2 text-xs font-mono text-slate-700">
                        {Object.entries(risk.evidence).map(([key, val]) => (
                          <span
                            key={key}
                            className="px-2.5 py-1 rounded bg-slate-100 border border-slate-200 text-[11px]"
                          >
                            {key}: {typeof val === 'object' ? JSON.stringify(val) : String(val)}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>

        {/* Explainable AI Risk Inspector Card (4 cols) */}
        <div className="lg:col-span-4 bg-white rounded-2xl p-6 border border-slate-200/90 shadow-sm sticky top-6 space-y-4">
          <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
            <Info className="w-5 h-5 text-indigo-600" />
            <h3 className="text-base font-bold text-slate-900">
              Explainable Risk Details
            </h3>
          </div>

          {selectedRisk ? (
            <>
              <div>
                <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">
                  Active Flag
                </p>
                <p className="text-sm font-bold text-slate-900 mt-0.5">
                  {selectedRisk.message}
                </p>
              </div>

              <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200/80 text-xs text-slate-600 leading-relaxed">
                <p className="font-semibold text-slate-800 mb-1">Risk Description & Evidence:</p>
                <p>
                  This flag was triggered because repository activity exceeded the project SLA threshold.
                  Review the evidence parameters and inspect individual items in Activity.
                </p>
              </div>

              <div className="space-y-2 pt-2">
                <p className="text-xs font-bold text-slate-700">Recommended Next Steps:</p>
                <ul className="text-xs text-slate-600 space-y-1.5 list-disc list-inside">
                  <li>Review aging PR queues or reassign pending code reviews</li>
                  <li>Verify if stale issues can be resolved, closed, or reprioritized</li>
                  <li>Review project threshold settings if this behavior is expected</li>
                </ul>
              </div>

              <button
                onClick={() => onNavigate('activity')}
                className="w-full mt-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold transition-colors flex items-center justify-center gap-1.5 cursor-pointer shadow-md shadow-indigo-600/20"
              >
                <span>Inspect in Activity Logs</span>
                <ChevronRight className="w-4 h-4" />
              </button>
            </>
          ) : (
            <p className="text-xs text-slate-400">Select a risk flag to inspect its evidence.</p>
          )}
        </div>
      </div>
    </div>
  );
};
