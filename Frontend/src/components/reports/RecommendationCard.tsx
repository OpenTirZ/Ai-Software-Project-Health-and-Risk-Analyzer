import React from 'react';
import {
  ArrowUpRight,
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  Lightbulb,
  User,
  Info,
} from 'lucide-react';
import type { Recommendation } from '../../services/reportService';

// ---------------------------------------------------------------------------
// Priority badge styling
// ---------------------------------------------------------------------------

const PRIORITY_STYLES: Record<string, { bg: string; text: string; border: string }> = {
  HIGH: { bg: '#FEF2F2', text: '#991B1B', border: '#FECACA' },
  MEDIUM: { bg: '#FFFBEB', text: '#92400E', border: '#FDE68A' },
  LOW: { bg: '#F0FDF4', text: '#166534', border: '#BBF7D0' },
};

function priorityStyle(level: string) {
  return PRIORITY_STYLES[level.toUpperCase()] ?? PRIORITY_STYLES.MEDIUM;
}

function PriorityIcon({ priority }: { priority: string }) {
  switch (priority.toUpperCase()) {
    case 'HIGH':
      return <AlertCircle className="h-4 w-4 text-red-600" />;
    case 'MEDIUM':
      return <AlertTriangle className="h-4 w-4 text-amber-600" />;
    case 'LOW':
      return <CheckCircle2 className="h-4 w-4 text-green-600" />;
    default:
      return <Info className="h-4 w-4 text-slate-500" />;
  }
}

// ---------------------------------------------------------------------------
// RecommendationCard
// ---------------------------------------------------------------------------

interface CardProps {
  recommendation: Recommendation;
}

export const RecommendationCard: React.FC<CardProps> = ({ recommendation }) => {
  const pStyle = priorityStyle(recommendation.priority);

  return (
    <div
      className="rounded-xl border bg-white p-5 transition-shadow hover:shadow-md"
      style={{ borderColor: pStyle.border }}
    >
      {/* Top row: priority badge + category */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <PriorityIcon priority={recommendation.priority} />
          <span
            className="inline-flex items-center rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase"
            style={{ backgroundColor: pStyle.bg, color: pStyle.text }}
          >
            {recommendation.priority}
          </span>
          <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-[10px] font-semibold text-slate-600">
            {recommendation.category.replace(/_/g, ' ')}
          </span>
        </div>
        {recommendation.targetRole && (
          <span className="inline-flex items-center gap-1 text-[11px] text-slate-400">
            <User className="h-3 w-3" />
            {recommendation.targetRole}
          </span>
        )}
      </div>

      {/* Condition */}
      <div className="mb-2 flex items-start gap-2 rounded-lg border border-slate-100 bg-slate-50 px-3 py-2">
        <AlertTriangle className="h-3.5 w-3.5 mt-0.5 shrink-0 text-amber-500" />
        <p className="text-xs text-slate-600 leading-relaxed">{recommendation.condition}</p>
      </div>

      {/* Action */}
      <div className="mb-3 flex items-start gap-2">
        <Lightbulb className="h-4 w-4 mt-0.5 shrink-0 text-[#0B6B63]" />
        <div>
          <p className="text-sm font-semibold text-slate-800 leading-snug">{recommendation.action}</p>
          {recommendation.rationale && (
            <p className="mt-1.5 text-xs text-slate-500 leading-relaxed">{recommendation.rationale}</p>
          )}
        </div>
      </div>

      {/* Advisory disclaimer */}
      {recommendation.isAdvisory && (
        <div className="rounded-lg bg-blue-50 border border-blue-100 px-3 py-1.5">
          <p className="text-[10px] text-blue-600 leading-relaxed">
            <strong>Advisory:</strong> {recommendation.disclaimer}
          </p>
        </div>
      )}
    </div>
  );
};

// ---------------------------------------------------------------------------
// RecommendationCards list
// ---------------------------------------------------------------------------

interface ListProps {
  recommendations: Recommendation[];
  isLoading: boolean;
  error: string | null;
}

export const RecommendationCards: React.FC<ListProps> = ({
  recommendations,
  isLoading,
  error,
}) => {
  if (isLoading) {
    return (
      <div className="space-y-4 animate-pulse">
        <div className="flex items-center gap-2 mb-2">
          <div className="h-5 w-5 rounded bg-slate-200" />
          <div className="h-5 w-48 rounded bg-slate-200" />
        </div>
        {[...Array(3)].map((_, i) => (
          <div key={i} className="h-32 rounded-xl bg-slate-100" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-5">
        <div className="flex items-center gap-2 text-red-700">
          <AlertCircle className="h-5 w-5" />
          <span className="text-sm font-medium">Failed to load recommendations</span>
        </div>
        <p className="mt-1 text-xs text-red-600">{error}</p>
      </div>
    );
  }

  if (recommendations.length === 0) {
    return (
      <div className="flex flex-col items-center gap-2 py-8 text-slate-400">
        <Lightbulb className="h-8 w-8" />
        <p className="text-sm font-medium">No recommendations available</p>
        <p className="text-xs">Generate a report to get AI-powered advisory recommendations</p>
      </div>
    );
  }

  // Sort by priority: HIGH → MEDIUM → LOW
  const priorityOrder: Record<string, number> = { HIGH: 0, MEDIUM: 1, LOW: 2 };
  const sorted = [...recommendations].sort(
    (a, b) => (priorityOrder[a.priority] ?? 1) - (priorityOrder[b.priority] ?? 1)
  );

  return (
    <div>
      <div className="flex items-center gap-2 mb-4">
        <ArrowUpRight className="h-5 w-5 text-[#0B6B63]" />
        <h3 className="text-sm font-semibold text-slate-800">Advisory Recommendations</h3>
        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-600">
          {recommendations.length}
        </span>
      </div>
      <div className="space-y-3">
        {sorted.map((rec, idx) => (
          <RecommendationCard key={`${rec.category}-${idx}`} recommendation={rec} />
        ))}
      </div>
    </div>
  );
};
