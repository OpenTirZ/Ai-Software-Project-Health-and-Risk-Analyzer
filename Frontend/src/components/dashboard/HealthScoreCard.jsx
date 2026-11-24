import React, { useState } from 'react';
import { 
  HeartPulse, 
  TrendingUp, 
  Info, 
  CheckCircle2, 
  AlertTriangle, 
  AlertCircle,
  ShieldCheck
} from 'lucide-react';

/**
 * HealthScoreCard Component
 * Displays the Overall Health Score Gauge (Red / Yellow / Green)
 * with a spacious, clean contributing factor breakdown that prevents any text overlapping.
 */
export const HealthScoreCard = ({ healthData }) => {
  const [showFormulaModal, setShowFormulaModal] = useState(false);

  const score = healthData?.score ?? 84;
  const status = healthData?.status ?? (score >= 80 ? 'Healthy' : score >= 60 ? 'Caution' : 'At Risk');
  const trend = healthData?.trend ?? '+4.2% from last sprint';
  const factors = healthData?.factors ?? [
    { name: 'PR Review Latency', score: 76, weight: 30, status: 'Caution', description: 'Average review turnaround time' },
    { name: 'Workload Balance', score: 72, weight: 25, status: 'Caution', description: 'Commit & PR distribution among team' },
    { name: 'Issue Hygiene', score: 94, weight: 25, status: 'Healthy', description: 'Active vs. stale issue resolution' },
    { name: 'Sprint Velocity', score: 92, weight: 20, status: 'Healthy', description: 'Story points burned against target' },
  ];

  // Dynamic color palette based on score threshold
  const getColorScheme = (val) => {
    if (val >= 80) {
      return {
        text: 'text-emerald-600',
        bg: 'bg-emerald-50',
        border: 'border-emerald-200',
        ring: '#10b981',
        badge: 'bg-emerald-100 text-emerald-800 border-emerald-300',
        icon: CheckCircle2,
      };
    }
    if (val >= 60) {
      return {
        text: 'text-amber-600',
        bg: 'bg-amber-50',
        border: 'border-amber-200',
        ring: '#f59e0b',
        badge: 'bg-amber-100 text-amber-800 border-amber-300',
        icon: AlertTriangle,
      };
    }
    return {
      text: 'text-rose-600',
      bg: 'bg-rose-50',
      border: 'border-rose-200',
      ring: '#ef4444',
      badge: 'bg-rose-100 text-rose-800 border-rose-300',
      icon: AlertCircle,
    };
  };

  const scheme = getColorScheme(score);
  const StatusIcon = scheme.icon;

  // SVG Gauge calculations with comfortable proportions to prevent inner text overlap
  const radius = 76;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference * (1 - Math.min(Math.max(score, 0), 100) / 100);

  return (
    <div className="bg-white rounded-2xl p-6 border border-slate-200/90 shadow-sm flex flex-col justify-between min-w-0">
      {/* Top Header */}
      <div className="flex items-center justify-between pb-4 border-b border-slate-100 gap-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="w-10 h-10 rounded-xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 shadow-sm shrink-0">
            <HeartPulse className="w-5 h-5" />
          </div>
          <div className="min-w-0">
            <h2 className="text-base sm:text-lg font-bold text-slate-900 tracking-tight flex items-center gap-2 flex-wrap">
              <span>Overall Health Score</span>
              <span className={`text-[11px] px-2.5 py-0.5 rounded-full font-bold border shrink-0 ${scheme.badge}`}>
                {status.toUpperCase()}
              </span>
            </h2>
            <p className="text-xs text-slate-500 truncate">Automated weighted factor calculation</p>
          </div>
        </div>

        <button
          onClick={() => setShowFormulaModal(true)}
          className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors shrink-0"
          title="View calculation formula"
        >
          <Info className="w-4 h-4" />
        </button>
      </div>

      {/* Main Gauge & Contributing Factors Section */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-6 my-6 items-center">
        {/* Left Circular Gauge (5 cols) */}
        <div className="md:col-span-5 flex flex-col items-center justify-center">
          <div className="relative w-48 h-48 sm:w-52 sm:h-52 flex items-center justify-center">
            <svg className="w-full h-full transform -rotate-90" viewBox="0 0 190 190">
              {/* Background Track */}
              <circle
                cx="95"
                cy="95"
                r={radius}
                stroke="#f1f5f9"
                strokeWidth="14"
                fill="transparent"
              />
              {/* Animated Value Ring */}
              <circle
                cx="95"
                cy="95"
                r={radius}
                stroke={scheme.ring}
                strokeWidth="14"
                strokeDasharray={circumference}
                strokeDashoffset={strokeDashoffset}
                strokeLinecap="round"
                fill="transparent"
                style={{ transition: 'stroke-dashoffset 1s ease-in-out' }}
              />
            </svg>

            {/* Inner Gauge Text with generous spacing */}
            <div className="absolute inset-0 flex flex-col items-center justify-center text-center p-4">
              <span className="text-4xl sm:text-5xl font-black text-slate-900 tracking-tight leading-none">
                {score}
              </span>
              <span className="text-[11px] font-bold text-slate-400 mt-1 uppercase tracking-wider">
                out of 100
              </span>
              <div className={`mt-1.5 px-2.5 py-0.5 rounded-full flex items-center gap-1 text-[11px] font-bold border ${scheme.badge}`}>
                <StatusIcon className="w-3 h-3 shrink-0" />
                <span>{status}</span>
              </div>
            </div>
          </div>

          <div className="mt-2 text-center">
            <p className="text-xs font-medium text-emerald-600 flex items-center justify-center gap-1">
              <TrendingUp className="w-3.5 h-3.5" />
              <span>{trend}</span>
            </p>
          </div>
        </div>

        {/* Right Contributing Factor Breakdown (7 cols) */}
        <div className="md:col-span-7 space-y-3 min-w-0">
          <div className="flex items-center justify-between text-xs font-bold uppercase tracking-wider text-slate-400 pb-1">
            <span>Factor Breakdown</span>
            <span>Score / SLA</span>
          </div>

          {factors.map((factor, index) => {
            const factorScheme = getColorScheme(factor.score);
            return (
              <div
                key={index}
                className="p-3 rounded-xl bg-slate-50/80 border border-slate-100 hover:border-slate-200 transition-all min-w-0"
              >
                {/* Responsive Header Row with wrap prevention */}
                <div className="flex flex-wrap items-center justify-between gap-x-2 gap-y-1 text-xs mb-1.5">
                  <div className="flex items-center gap-1.5 min-w-0">
                    <span className="font-bold text-slate-800 truncate">{factor.name}</span>
                    <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-white border border-slate-200 text-slate-500 shrink-0">
                      {factor.weight}% wt
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0 ml-auto">
                    <span className="font-extrabold text-slate-900">{factor.score}</span>
                    <span className="text-slate-400 text-[11px]">/ 100</span>
                    <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded border ${factorScheme.badge}`}>
                      {factor.status}
                    </span>
                  </div>
                </div>

                {/* Factor Progress Bar */}
                <div className="w-full bg-slate-200/70 h-2 rounded-full overflow-hidden my-1">
                  <div
                    className={`h-full rounded-full transition-all duration-700 ${
                      factor.score >= 80 ? 'bg-emerald-500' : factor.score >= 60 ? 'bg-amber-500' : 'bg-rose-500'
                    }`}
                    style={{ width: `${Math.min(factor.score, 100)}%` }}
                  />
                </div>

                <p className="text-[11px] text-slate-500 mt-1 leading-snug break-words">
                  {factor.description}
                </p>
              </div>
            );
          })}
        </div>
      </div>

      {/* Bottom Summary Banner */}
      <div className="pt-3 border-t border-slate-100 flex items-start gap-2.5 text-xs text-slate-600 bg-slate-50/60 p-3 rounded-xl mt-2">
        <ShieldCheck className="w-4 h-4 text-indigo-600 shrink-0 mt-0.5" />
        <p className="leading-relaxed break-words">
          <span className="font-semibold text-slate-800">Recommendation:</span>{' '}
          {healthData?.breakdownSummary ||
            'Workload is slightly concentrated on the top 2 engineers. Consider spreading complex pull requests to improve review latency and protect against bus factor vulnerabilities.'}
        </p>
      </div>

      {/* Formula Modal */}
      {showFormulaModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200 animate-in fade-in zoom-in-95 duration-150">
            <h3 className="text-lg font-bold text-slate-900 mb-2 flex items-center gap-2">
              <HeartPulse className="w-5 h-5 text-indigo-600" />
              Health Score Algorithm
            </h3>
            <p className="text-xs text-slate-600 mb-4 leading-relaxed">
              The Overall Health Score is calculated via a normalized composite index weighted across four primary software engineering velocity and stability dimensions:
            </p>
            <div className="space-y-2 text-xs text-slate-700 bg-slate-50 p-4 rounded-xl border border-slate-200/80 mb-4 font-mono">
              <div>Health = (PR_Latency × 0.30)</div>
              <div>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;+ (Workload_Balance × 0.25)</div>
              <div>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;+ (Issue_Hygiene × 0.25)</div>
              <div>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;+ (Sprint_Velocity × 0.20)</div>
            </div>
            <div className="flex justify-end">
              <button
                onClick={() => setShowFormulaModal(false)}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-xs font-semibold transition-colors"
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

export default HealthScoreCard;
