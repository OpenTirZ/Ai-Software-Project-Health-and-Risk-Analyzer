import React, { useState, useEffect, useRef } from 'react';
import {
  X,
  AlertCircle,
  AlertTriangle,
  Info,
  ShieldAlert,
  Zap,
  Clock,
  ChevronRight,
  Loader2,
} from 'lucide-react';
import { reportService, type FlagExplanation } from '../../services/reportService';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface FlagData {
  id: string;
  type: string;
  severity: string;
  message: string;
  evidence?: any;
}

interface Props {
  projectId: string;
  flag: FlagData | null;
  isOpen: boolean;
  onClose: () => void;
}

// ---------------------------------------------------------------------------
// Colour helpers
// ---------------------------------------------------------------------------

const SEVERITY_STYLES: Record<string, { bg: string; border: string; text: string; icon: React.ElementType }> = {
  CRITICAL: { bg: '#FEF2F2', border: '#FCA5A5', text: '#991B1B', icon: Zap },
  HIGH: { bg: '#FEF2F2', border: '#FECACA', text: '#991B1B', icon: ShieldAlert },
  MEDIUM: { bg: '#FFFBEB', border: '#FDE68A', text: '#92400E', icon: AlertTriangle },
  LOW: { bg: '#F0FDF4', border: '#BBF7D0', text: '#166534', icon: AlertCircle },
  INFO: { bg: '#EFF6FF', border: '#BFDBFE', text: '#1E40AF', icon: Info },
};

function getSeverityStyle(sev: string) {
  return SEVERITY_STYLES[sev.toUpperCase()] ?? SEVERITY_STYLES.MEDIUM;
}

// ---------------------------------------------------------------------------
// ExplanationDrawer
// ---------------------------------------------------------------------------

export const ExplanationDrawer: React.FC<Props> = ({ projectId, flag, isOpen, onClose }) => {
  const [explanation, setExplanation] = useState<FlagExplanation | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const drawerRef = useRef<HTMLDivElement>(null);

  // Fetch AI explanation when a flag is selected
  useEffect(() => {
    if (!isOpen || !flag) {
      setExplanation(null);
      setError(null);
      return;
    }

    setIsLoading(true);
    setError(null);

    reportService
      .explainFlag(projectId, flag)
      .then(setExplanation)
      .catch((e) => setError(e.message || 'Failed to load explanation'))
      .finally(() => setIsLoading(false));
  }, [isOpen, flag?.id, projectId]);

  // Close on Escape
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) onClose();
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen || !flag) return null;

  const style = getSeverityStyle(flag.severity);
  const SeverityIcon = style.icon;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/30 transition-opacity"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Drawer panel */}
      <div
        ref={drawerRef}
        role="dialog"
        aria-modal="true"
        aria-label="Risk flag explanation"
        className="fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col bg-white shadow-2xl transition-transform duration-300 ease-out"
        style={{ transform: isOpen ? 'translateX(0)' : 'translateX(100%)' }}
      >
        {/* Header */}
        <div
          className="flex items-start justify-between gap-3 border-b px-5 py-4"
          style={{ borderColor: style.border, backgroundColor: style.bg }}
        >
          <div className="flex items-start gap-3 min-w-0">
            <SeverityIcon className="h-5 w-5 mt-0.5 shrink-0" style={{ color: style.text }} />
            <div className="min-w-0">
              <span
                className="inline-block rounded-full px-2 py-0.5 text-[10px] font-bold uppercase mb-1"
                style={{ backgroundColor: `${style.text}18`, color: style.text }}
              >
                {flag.severity}
              </span>
              <h2 className="text-sm font-semibold text-slate-800 leading-snug">{flag.message}</h2>
              <p className="mt-1 text-[11px] text-slate-500">
                Flag: <code className="font-mono text-[10px]">{flag.id}</code> · Type: {flag.type}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="shrink-0 rounded-md p-1.5 text-slate-400 hover:bg-white/60 hover:text-slate-700"
            aria-label="Close drawer"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-5 py-5 space-y-5">
          {isLoading && (
            <div className="flex flex-col items-center gap-3 py-12 text-slate-400">
              <Loader2 className="h-8 w-8 animate-spin" />
              <p className="text-sm font-medium">Generating AI explanation…</p>
              <p className="text-xs">Analyzing flag evidence with LLM</p>
            </div>
          )}

          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 p-4">
              <div className="flex items-center gap-2 text-red-700">
                <AlertCircle className="h-4 w-4" />
                <span className="text-sm font-medium">Explanation unavailable</span>
              </div>
              <p className="mt-1 text-xs text-red-600">{error}</p>
            </div>
          )}

          {explanation && !isLoading && (
            <>
              {/* Plain-language explanation */}
              <section>
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">
                  Why This Was Flagged
                </h3>
                <p className="text-sm leading-relaxed text-slate-700">{explanation.explanation}</p>
              </section>

              {/* Contributing metrics */}
              {Object.keys(explanation.contributingMetrics).length > 0 && (
                <section>
                  <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">
                    Contributing Metrics
                  </h3>
                  <div className="space-y-1.5">
                    {Object.entries(explanation.contributingMetrics).map(([key, value]) => (
                      <div
                        key={key}
                        className="flex items-center justify-between rounded-lg border border-slate-100 bg-slate-50 px-3 py-2"
                      >
                        <span className="text-xs text-slate-600 font-medium">
                          {key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
                        </span>
                        <span className="text-xs font-semibold text-slate-800 font-mono">
                          {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                        </span>
                      </div>
                    ))}
                  </div>
                </section>
              )}

              {/* Evidence points */}
              {explanation.evidence.length > 0 && (
                <section>
                  <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">
                    Evidence
                  </h3>
                  <ul className="space-y-1.5">
                    {explanation.evidence.map((point, idx) => (
                      <li key={idx} className="flex items-start gap-2 text-xs text-slate-600">
                        <ChevronRight className="h-3.5 w-3.5 mt-0.5 shrink-0 text-slate-400" />
                        <span>{point}</span>
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              {/* Source period */}
              {explanation.sourcePeriod && (
                <div className="flex items-center gap-2 rounded-lg bg-blue-50 border border-blue-100 px-3 py-2">
                  <Clock className="h-3.5 w-3.5 text-blue-500" />
                  <span className="text-xs text-blue-700">
                    Analysis period: {explanation.sourcePeriod}
                  </span>
                </div>
              )}

              {/* Caveats */}
              {explanation.uncertaintyOrCaveats && (
                <div className="rounded-lg bg-amber-50 border border-amber-100 px-3 py-2">
                  <p className="text-[11px] text-amber-700 leading-relaxed">
                    <strong>Note:</strong> {explanation.uncertaintyOrCaveats}
                  </p>
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-slate-100 px-5 py-3">
          <button
            type="button"
            onClick={onClose}
            className="w-full rounded-lg border border-slate-200 bg-white py-2 text-sm font-medium text-slate-600 hover:bg-slate-50 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </>
  );
};
