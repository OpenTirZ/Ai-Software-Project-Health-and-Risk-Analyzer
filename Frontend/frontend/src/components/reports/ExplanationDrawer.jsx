import React, { useEffect } from 'react';
import { 
  X, 
  AlertTriangle, 
  Clock, 
  Info, 
  CheckCircle2, 
  ArrowRight, 
  TrendingDown, 
  Sparkles,
  Database
} from 'lucide-react';

/**
 * AI Explanation Drawer Component
 * Interactive popover on metric flags explaining why a risk was flagged,
 * citing explicit telemetry data timestamps, raw metrics, and architectural impacts.
 */
export const ExplanationDrawer = ({ isOpen, onClose, flag, repoName = 'repository', onNavigate }) => {
  // Handle ESC key to dismiss drawer
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen || !flag) return null;

  const {
    metric = 'Metric Risk',
    value = 'N/A',
    benchmark = 'Standard',
    delta = '',
    severity = 'Medium',
    detectedAt = new Date().toISOString(),
    summary = '',
    detailedExplanation = '',
    impactAnalysis = '',
    citedTelemetry = [],
    remedy = '',
  } = flag;

  const getSeverityBadge = () => {
    switch (severity) {
      case 'High':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-rose-50 text-rose-700 border border-rose-200">
            <AlertTriangle className="w-3.5 h-3.5 text-rose-600" />
            HIGH RISK FLAG
          </span>
        );
      case 'Medium':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-amber-50 text-amber-700 border border-amber-200">
            <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
            CAUTION RISK FLAG
          </span>
        );
      case 'Low':
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-blue-50 text-blue-700 border border-blue-200">
            <Info className="w-3.5 h-3.5 text-blue-600" />
            ADVISORY FLAG
          </span>
        );
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-slate-900/50 backdrop-blur-xs transition-opacity duration-300">
      {/* Backdrop click to dismiss */}
      <div className="flex-1 cursor-pointer" onClick={onClose} />

      {/* Drawer Container */}
      <div className="relative w-full max-w-lg bg-white h-full shadow-2xl flex flex-col border-l border-slate-200 animate-in slide-in-from-right duration-200 overflow-hidden">
        {/* Top Header */}
        <div className="p-6 border-b border-slate-100 flex items-start justify-between gap-4 bg-slate-50/50">
          <div>
            <div className="flex items-center gap-2 mb-2">
              {getSeverityBadge()}
              <span className="text-xs text-slate-400 font-mono flex items-center gap-1">
                <Clock className="w-3 h-3 text-slate-400" />
                {detectedAt}
              </span>
            </div>
            <h2 className="text-xl font-bold text-slate-900 tracking-tight">
              {metric}
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Target repository: <span className="font-semibold text-slate-700">{repoName}</span>
            </p>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-200/60 transition-colors cursor-pointer"
            aria-label="Close Drawer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Drawer Body Scrollable Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Metric Comparison Card */}
          <div className="grid grid-cols-2 gap-3 bg-slate-50 p-4 rounded-xl border border-slate-200/80">
            <div>
              <p className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">
                Observed Telemetry
              </p>
              <p className="text-xl font-bold text-slate-900 mt-1 font-mono">
                {value}
              </p>
              {delta && (
                <span className="text-[11px] font-semibold text-rose-600 flex items-center gap-1 mt-0.5">
                  <TrendingDown className="w-3 h-3" />
                  {delta}
                </span>
              )}
            </div>

            <div>
              <p className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">
                Target Benchmark
              </p>
              <p className="text-xl font-bold text-emerald-600 mt-1 font-mono">
                {benchmark}
              </p>
              <span className="text-[11px] font-medium text-slate-500 block mt-0.5">
                Expected healthy SLA
              </span>
            </div>
          </div>

          {/* AI Explanation / Why Flagged */}
          <div className="space-y-2">
            <div className="flex items-center gap-1.5 text-xs font-bold text-indigo-700 uppercase tracking-wider">
              <Sparkles className="w-3.5 h-3.5 text-indigo-600" />
              <span>Why Was This Risk Flagged?</span>
            </div>
            <p className="text-sm font-medium text-slate-900 leading-relaxed bg-indigo-50/60 p-3.5 rounded-xl border border-indigo-100">
              {summary}
            </p>
            <p className="text-xs text-slate-600 leading-relaxed pt-1">
              {detailedExplanation}
            </p>
          </div>

          {/* Cited Telemetry & Timestamps */}
          {citedTelemetry && citedTelemetry.length > 0 && (
            <div className="space-y-2.5">
              <div className="flex items-center gap-1.5 text-xs font-bold text-slate-700 uppercase tracking-wider">
                <Database className="w-3.5 h-3.5 text-slate-500" />
                <span>Cited Telemetry Evidence & Timestamps</span>
              </div>
              <div className="space-y-1.5">
                {citedTelemetry.map((item, idx) => (
                  <div
                    key={idx}
                    className="flex items-start gap-2 p-2 rounded-lg bg-slate-50 border border-slate-100 text-xs font-mono text-slate-700"
                  >
                    <span className="text-indigo-500 font-bold">•</span>
                    <span>{item}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Architectural Impact */}
          {impactAnalysis && (
            <div className="space-y-2">
              <div className="flex items-center gap-1.5 text-xs font-bold text-slate-700 uppercase tracking-wider">
                <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />
                <span>Delivery & Architectural Impact</span>
              </div>
              <p className="text-xs text-slate-600 leading-relaxed p-3 rounded-xl bg-amber-50/50 border border-amber-100">
                {impactAnalysis}
              </p>
            </div>
          )}

          {/* Actionable Countermeasure */}
          {remedy && (
            <div className="space-y-2">
              <div className="flex items-center gap-1.5 text-xs font-bold text-emerald-700 uppercase tracking-wider">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                <span>Recommended Countermeasure</span>
              </div>
              <p className="text-xs text-slate-700 leading-relaxed p-3.5 rounded-xl bg-emerald-50/60 border border-emerald-100">
                {remedy}
              </p>
            </div>
          )}
        </div>

        {/* Drawer Footer */}
        <div className="p-4 border-t border-slate-100 bg-slate-50/80 flex items-center justify-between gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-xl border border-slate-200 text-slate-700 text-xs font-semibold hover:bg-slate-100 transition-colors cursor-pointer"
          >
            Close Explanation
          </button>

          {onNavigate && (
            <button
              onClick={() => {
                onClose();
                onNavigate('activity');
              }}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold transition-all shadow-md shadow-indigo-600/20 cursor-pointer"
            >
              <span>Inspect in Activity Queue</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default ExplanationDrawer;
