import React, { useState } from 'react';
import {
  GitPullRequest,
  Clock,
  AlertCircle,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  Radar,
} from 'lucide-react';
import type { BottleneckItem } from '../../services/metricService';

// ---------------------------------------------------------------------------
// Colour helpers
// ---------------------------------------------------------------------------
const SEVERITY_MAP: Record<string, { bg: string; text: string; border: string; label: string }> = {
  high: { bg: '#FEF2F2', text: '#991B1B', border: '#FECACA', label: 'Critical' },
  medium: { bg: '#FFFBEB', text: '#92400E', border: '#FDE68A', label: 'Warning' },
  low: { bg: '#F0FDF4', text: '#166534', border: '#BBF7D0', label: 'Info' },
};

function severityStyle(sev: string) {
  return SEVERITY_MAP[sev] ?? SEVERITY_MAP.low;
}

// ---------------------------------------------------------------------------
// Bottlenecks List  (Delivery Bottleneck Radar)
// ---------------------------------------------------------------------------
interface Props {
  items: BottleneckItem[];
  isLoading: boolean;
  error: string | null;
}

export const BottlenecksList: React.FC<Props> = ({ items, isLoading, error }) => {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [visibleCount, setVisibleCount] = useState(5);

  const toggle = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  if (isLoading) {
    return (
      <div className="rounded-xl border border-[#9ED4C8] bg-white p-6 shadow-sm animate-pulse">
        <div className="flex items-center gap-2 mb-4">
          <div className="h-5 w-5 rounded bg-slate-200" />
          <div className="h-5 w-44 rounded bg-slate-200" />
        </div>
        {[...Array(3)].map((_, i) => (
          <div key={i} className="mb-3 h-14 rounded-lg bg-slate-100" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-6">
        <div className="flex items-center gap-2 text-red-700">
          <AlertCircle className="h-5 w-5" />
          <span className="text-sm font-medium">Failed to load bottlenecks</span>
        </div>
        <p className="mt-2 text-xs text-red-600">{error}</p>
      </div>
    );
  }

  const highCount = items.filter((i) => i.severity === 'high').length;
  const medCount = items.filter((i) => i.severity === 'medium').length;

  return (
    <div className="rounded-xl border border-[#9ED4C8] bg-white p-6 shadow-sm">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Radar className="h-5 w-5 text-[#0B6B63]" />
          <h3 className="text-sm font-semibold text-slate-800">Delivery Bottleneck Radar</h3>
        </div>
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <span>Pending PRs &gt; 48 h</span>
          {items.length > 0 && (
            <span className="inline-flex items-center rounded-full bg-red-50 px-2 py-0.5 text-xs font-semibold text-red-700">
              {items.length}
            </span>
          )}
        </div>
      </div>

      {items.length === 0 ? (
        <div className="flex flex-col items-center gap-2 py-8 text-slate-400">
          <GitPullRequest className="h-8 w-8" />
          <p className="text-sm font-medium">No bottlenecks detected</p>
          <p className="text-xs">All PRs are within healthy review windows</p>
        </div>
      ) : (
        <>
          {/* Summary badges */}
          <div className="flex flex-wrap gap-2 mb-3">
            {highCount > 0 && (
              <span className="inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold" style={{ backgroundColor: '#FEF2F2', color: '#991B1B' }}>
                {highCount} Critical
              </span>
            )}
            {medCount > 0 && (
              <span className="inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold" style={{ backgroundColor: '#FFFBEB', color: '#92400E' }}>
                {medCount} Warning
              </span>
            )}
          </div>

          {/* List */}
          <div className="space-y-2">
            {items.slice(0, visibleCount).map((item) => {
              const sev = severityStyle(item.severity);
              const isOpen = expanded.has(item.id);

              return (
                <div
                  key={item.id}
                  className="rounded-lg border transition-colors"
                  style={{ borderColor: sev.border, backgroundColor: sev.bg }}
                >
                  <button
                    type="button"
                    className="flex w-full items-center gap-3 px-4 py-3 text-left"
                    onClick={() => toggle(item.id)}
                  >
                    <GitPullRequest className="h-4 w-4 shrink-0" style={{ color: sev.text }} />
                    <div className="min-w-0 flex-1">
                      <span className="text-xs font-semibold block truncate" style={{ color: sev.text }}>
                        {item.title}
                      </span>
                      <span className="text-[11px] text-slate-500">
                        by {item.author} · {item.detail}
                      </span>
                    </div>
                    <span
                      className="shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold uppercase"
                      style={{ backgroundColor: `${sev.text}18`, color: sev.text }}
                    >
                      {sev.label}
                    </span>
                    {isOpen ? (
                      <ChevronUp className="h-4 w-4 text-slate-400" />
                    ) : (
                      <ChevronDown className="h-4 w-4 text-slate-400" />
                    )}
                  </button>

                  {isOpen && (
                    <div className="border-t px-4 py-3 text-xs" style={{ borderColor: sev.border }}>
                      <div className="flex items-center gap-4 text-slate-600">
                        <span className="inline-flex items-center gap-1">
                          <Clock className="h-3.5 w-3.5" /> Age: {item.ageHours ? `${item.ageHours}h` : 'N/A'}
                        </span>
                        {item.prNumber && (
                          <span className="inline-flex items-center gap-1">
                            <ExternalLink className="h-3.5 w-3.5" /> PR #{item.prNumber}
                          </span>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Show more */}
          {items.length > visibleCount && (
            <button
              type="button"
              className="mt-3 w-full rounded-lg bg-slate-50 py-2 text-xs font-medium text-slate-600 hover:bg-slate-100 transition-colors"
              onClick={() => setVisibleCount((prev) => prev + 5)}
            >
              Show more ({items.length - visibleCount} remaining)
            </button>
          )}
        </>
      )}
    </div>
  );
};
