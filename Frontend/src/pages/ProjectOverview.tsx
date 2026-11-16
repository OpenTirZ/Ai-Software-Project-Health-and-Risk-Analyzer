import React from 'react';
import type { PageView } from '../types';
import { 
  ArrowRight,
  TrendingUp,
  Sparkles
} from 'lucide-react';

interface ProjectOverviewProps {
  selectedRepo: string;
  onNavigate: (view: PageView) => void;
}

export const ProjectOverview: React.FC<ProjectOverviewProps> = ({
  selectedRepo,
  onNavigate,
}) => {
  return (
    <div className="p-6 md:p-8 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl md:text-3xl font-bold text-slate-900 tracking-tight">
          Project Overview
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          Current project health and risk overview for <span className="font-semibold text-slate-700">{selectedRepo}</span>.
        </p>
      </div>

      {/* Top 6 KPI Cards Grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3.5">
        {/* 1. PROJECT HEALTH */}
        <div className="bg-white rounded-xl p-4 border border-slate-200/90 shadow-sm flex flex-col justify-between">
          <p className="text-[11px] font-extrabold uppercase text-[#01315e] tracking-tight">
            PROJECT HEALTH
          </p>
          <div className="my-2 flex items-baseline gap-2">
            <span className="text-3xl font-bold text-slate-900">82</span>
            <span className="text-xs font-bold text-emerald-600">Good</span>
          </div>
          <p className="text-[11px] font-medium text-emerald-600 flex items-center gap-1">
            <TrendingUp className="w-3 h-3" />
            <span>↑ 4.2% from last week</span>
          </p>
        </div>

        {/* 2. SCHEDULE RISK */}
        <div className="bg-white rounded-xl p-4 border border-slate-200/90 shadow-sm flex flex-col justify-between">
          <p className="text-[11px] font-extrabold uppercase text-[#01315e] tracking-tight">
            SCHEDULE RISK
          </p>
          <div className="my-2">
            <span className="text-3xl font-bold text-slate-900">Low</span>
          </div>
          <p className="text-[11px] text-slate-500">
            No critical warning
          </p>
        </div>

        {/* 3. OPEN PULL REQUESTS */}
        <div className="bg-white rounded-xl p-4 border border-slate-200/90 shadow-sm flex flex-col justify-between">
          <p className="text-[11px] font-extrabold uppercase text-[#01315e] tracking-tight">
            OPEN PULL REQUESTS
          </p>
          <div className="my-2">
            <span className="text-3xl font-bold text-slate-900">12</span>
          </div>
          <p className="text-[11px] font-semibold text-amber-600">
            3 aging
          </p>
        </div>

        {/* 4. STALE ISSUES */}
        <div className="bg-white rounded-xl p-4 border border-slate-200/90 shadow-sm flex flex-col justify-between">
          <p className="text-[11px] font-extrabold uppercase text-[#01315e] tracking-tight">
            STALE ISSUES
          </p>
          <div className="my-2">
            <span className="text-3xl font-bold text-slate-900">4</span>
          </div>
          <p className="text-[11px] font-semibold text-amber-600">
            Need attention
          </p>
        </div>

        {/* 5. BOTTLENECKS */}
        <div className="bg-white rounded-xl p-4 border border-slate-200/90 shadow-sm flex flex-col justify-between">
          <p className="text-[11px] font-extrabold uppercase text-[#01315e] tracking-tight">
            BOTTLENECKS
          </p>
          <div className="my-2">
            <span className="text-3xl font-bold text-slate-900">3</span>
          </div>
          <p className="text-[11px] text-slate-500">
            Potential
          </p>
        </div>

        {/* 6. CONTRIBUTORS */}
        <div className="bg-white rounded-xl p-4 border border-slate-200/90 shadow-sm flex flex-col justify-between">
          <p className="text-[11px] font-extrabold uppercase text-[#01315e] tracking-tight">
            CONTRIBUTORS
          </p>
          <div className="my-2">
            <span className="text-3xl font-bold text-slate-900">12</span>
          </div>
          <p className="text-[11px] text-slate-500">
            Active
          </p>
        </div>
      </div>

      {/* Middle Grid: Project Health Breakdown + Risk Overview + Sprint 14 */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Card 1: Project Health & Indicators (6 cols) */}
        <div className="lg:col-span-6 bg-white rounded-2xl p-6 border border-slate-200/90 shadow-sm flex flex-col justify-between">
          <div className="flex items-center justify-between border-b border-slate-100 pb-4">
            <h2 className="text-lg font-bold text-slate-900">
              Project Health
            </h2>
            <button
              onClick={() => onNavigate('health-analysis')}
              className="text-xs font-semibold text-blue-600 hover:text-blue-800 transition-colors flex items-center gap-1 cursor-pointer"
            >
              <span>View Details</span>
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
                    stroke="#10b981"
                    strokeWidth="10"
                    strokeDasharray={2 * Math.PI * 48}
                    strokeDashoffset={(2 * Math.PI * 48) * (1 - 0.82)}
                    strokeLinecap="round"
                    fill="transparent"
                  />
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
                  <span className="text-4xl font-extrabold text-slate-900 leading-none">82</span>
                  <span className="text-xs font-bold text-emerald-600 mt-1 uppercase tracking-wider">GOOD</span>
                </div>
              </div>
            </div>

            {/* Health Indicators Bars */}
            <div className="space-y-3.5">
              <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
                Health Indicators
              </h3>
              <div>
                <div className="flex justify-between text-xs font-medium mb-1">
                  <span className="text-slate-600">Bottlenecks</span>
                  <span className="text-slate-900 font-semibold">82%</span>
                </div>
                <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
                  <div className="bg-emerald-500 h-full rounded-full" style={{ width: '82%' }}></div>
                </div>
              </div>

              <div>
                <div className="flex justify-between text-xs font-medium mb-1">
                  <span className="text-slate-600">Workload</span>
                  <span className="text-slate-900 font-semibold">76%</span>
                </div>
                <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
                  <div className="bg-indigo-500 h-full rounded-full" style={{ width: '76%' }}></div>
                </div>
              </div>

              <div>
                <div className="flex justify-between text-xs font-medium mb-1">
                  <span className="text-slate-600">Issues</span>
                  <span className="text-slate-900 font-semibold">88%</span>
                </div>
                <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
                  <div className="bg-emerald-500 h-full rounded-full" style={{ width: '88%' }}></div>
                </div>
              </div>

              <div>
                <div className="flex justify-between text-xs font-medium mb-1">
                  <span className="text-slate-600">Schedule</span>
                  <span className="text-slate-900 font-semibold">70%</span>
                </div>
                <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
                  <div className="bg-amber-500 h-full rounded-full" style={{ width: '70%' }}></div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Card 2: Risk Overview (3 cols) */}
        <div className="lg:col-span-3 bg-white rounded-2xl p-6 border border-slate-200/90 shadow-sm flex flex-col justify-between">
          <div className="border-b border-slate-100 pb-4">
            <h2 className="text-lg font-bold text-slate-900">
              Risk Overview
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">Summary of risk metrics</p>
          </div>

          <div className="space-y-4 my-auto py-3">
            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-700 font-medium">Potential PR Bottleneck</span>
              <span className="text-rose-600 font-bold bg-rose-50 px-2 py-0.5 rounded text-xs">3</span>
            </div>

            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-700 font-medium">Stale Issues</span>
              <span className="text-amber-600 font-bold bg-amber-50 px-2 py-0.5 rounded text-xs">4</span>
            </div>

            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-700 font-medium">Workload Balance</span>
              <span className="text-emerald-600 font-bold bg-emerald-50 px-2 py-0.5 rounded text-xs">Good</span>
            </div>

            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-700 font-medium">Repository Activity</span>
              <span className="text-emerald-600 font-bold bg-emerald-50 px-2 py-0.5 rounded text-xs">Good</span>
            </div>
          </div>

          <button
            onClick={() => onNavigate('risk-analysis')}
            className="w-full py-2 text-xs font-semibold text-center text-indigo-600 hover:text-indigo-800 bg-indigo-50/60 hover:bg-indigo-50 rounded-lg transition-colors cursor-pointer"
          >
            Investigate All Risks →
          </button>
        </div>

        {/* Card 3: Sprint 14 (3 cols) */}
        <div className="lg:col-span-3 bg-white rounded-2xl p-6 border border-slate-200/90 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold text-slate-900">
                Sprint 14
              </h2>
              <span className="text-xs px-2 py-0.5 rounded bg-blue-50 text-blue-700 font-medium border border-blue-200">Active</span>
            </div>
            <p className="text-xs text-slate-500 mt-1">Nov 1 – Nov 14</p>
          </div>

          <div className="my-6 space-y-3">
            <div className="flex justify-between items-baseline">
              <span className="text-sm font-bold text-slate-800">21 / 30 completed</span>
              <span className="text-xs font-bold text-indigo-600">70% complete</span>
            </div>

            <div className="w-full bg-slate-100 h-2.5 rounded-full overflow-hidden">
              <div 
                className="bg-indigo-600 h-full rounded-full transition-all duration-500" 
                style={{ width: '70%' }}
              />
            </div>

            <p className="text-xs text-slate-500 pt-1">
              Remaining tasks: <span className="font-semibold text-slate-800">9</span>
            </p>
          </div>

          <div className="text-xs text-slate-400 bg-slate-50 p-2.5 rounded-lg border border-slate-100 text-center">
            On track to complete by Nov 14
          </div>
        </div>
      </div>

      {/* Bottom Section: AI Recommendations */}
      <div className="bg-white rounded-2xl p-6 border border-slate-200/90 shadow-sm space-y-4">
        <div className="flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-indigo-600" />
          <h2 className="text-lg font-bold text-slate-900">
            AI Recommendations
          </h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Recommendation 1 */}
          <div 
            onClick={() => onNavigate('risk-analysis')}
            className="p-4 rounded-xl border border-amber-200/90 bg-amber-50/40 hover:bg-amber-50/80 transition-colors cursor-pointer flex items-start gap-3.5 group"
          >
            <div className="p-2 rounded-lg bg-amber-100 text-amber-700 shrink-0 mt-0.5">
              ⚠
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="text-sm font-bold text-amber-900 flex items-center justify-between">
                <span>Review aging pull requests</span>
                <span className="text-xs font-semibold text-amber-700 group-hover:translate-x-1 transition-transform">Audit →</span>
              </h3>
              <p className="text-xs text-slate-600 mt-1">
                3 PRs have exceeded the configured aging threshold (48 hours). Merge velocity is currently impacted.
              </p>
            </div>
          </div>

          {/* Recommendation 2 */}
          <div 
            onClick={() => onNavigate('activity')}
            className="p-4 rounded-xl border border-blue-200/90 bg-blue-50/40 hover:bg-blue-50/80 transition-colors cursor-pointer flex items-start gap-3.5 group"
          >
            <div className="p-2 rounded-lg bg-blue-100 text-blue-700 shrink-0 mt-0.5">
              ℹ
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="text-sm font-bold text-blue-900 flex items-center justify-between">
                <span>Investigate stale issues</span>
                <span className="text-xs font-semibold text-blue-700 group-hover:translate-x-1 transition-transform">View →</span>
              </h3>
              <p className="text-xs text-slate-600 mt-1">
                4 issues have had no recent developer activity. Prioritize triage before the end of Sprint 14.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
