import React from 'react';
import { CalendarClock, AlertCircle, CheckCircle2, Target } from 'lucide-react';
import type { SprintVelocity } from '../../services/metricService';

// ---------------------------------------------------------------------------
// Sprint Velocity / Burndown Indicator
// ---------------------------------------------------------------------------
interface Props {
  data: SprintVelocity[];
  isLoading: boolean;
  error: string | null;
}

function progressColor(pct: number, daysRemaining: number | null): string {
  if (daysRemaining !== null && daysRemaining < 0) return '#CC1F2E'; // overdue
  if (pct >= 80) return '#16A34A';
  if (pct >= 50) return '#B45309';
  return '#CC1F2E';
}

export const SprintVelocityCard: React.FC<Props> = ({ data, isLoading, error }) => {
  if (isLoading) {
    return (
      <div className="rounded-xl border border-[#9ED4C8] bg-white p-6 shadow-sm animate-pulse">
        <div className="flex items-center gap-2 mb-4">
          <div className="h-5 w-5 rounded bg-slate-200" />
          <div className="h-5 w-44 rounded bg-slate-200" />
        </div>
        <div className="h-28 rounded-lg bg-slate-100" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-6">
        <div className="flex items-center gap-2 text-red-700">
          <AlertCircle className="h-5 w-5" />
          <span className="text-sm font-medium">Failed to load sprint data</span>
        </div>
        <p className="mt-2 text-xs text-red-600">{error}</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-[#9ED4C8] bg-white p-6 shadow-sm">
      {/* Header */}
      <div className="flex items-center gap-2 mb-4">
        <CalendarClock className="h-5 w-5 text-[#0B6B63]" />
        <h3 className="text-sm font-semibold text-slate-800">Sprint Burndown / Velocity</h3>
      </div>

      {data.length === 0 ? (
        <div className="flex flex-col items-center gap-2 py-8 text-slate-400">
          <Target className="h-8 w-8" />
          <p className="text-sm font-medium">No active sprints</p>
          <p className="text-xs">Create milestones in GitHub to track sprint velocity</p>
        </div>
      ) : (
        <div className="space-y-4">
          {data.map((sprint) => {
            const color = progressColor(sprint.completionPct, sprint.daysRemaining);
            const isOverdue = sprint.daysRemaining !== null && sprint.daysRemaining < 0;

            return (
              <div key={sprint.milestoneName} className="rounded-lg border border-slate-100 p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-semibold text-slate-800 truncate">{sprint.milestoneName}</span>
                  {isOverdue ? (
                    <span className="rounded-full bg-red-50 px-2 py-0.5 text-[10px] font-bold text-red-700 uppercase">
                      Overdue
                    </span>
                  ) : sprint.daysRemaining !== null ? (
                    <span className="text-[11px] text-slate-500">
                      {sprint.daysRemaining} day{sprint.daysRemaining !== 1 && 's'} left
                    </span>
                  ) : null}
                </div>

                {/* Progress bar */}
                <div className="h-2.5 w-full rounded-full bg-slate-100 overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-700"
                    style={{
                      width: `${sprint.completionPct}%`,
                      backgroundColor: color,
                    }}
                  />
                </div>

                {/* Stats row */}
                <div className="mt-2 flex items-center gap-4 text-xs text-slate-500">
                  <span className="inline-flex items-center gap-1">
                    <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
                    {sprint.closedIssues} closed
                  </span>
                  <span className="inline-flex items-center gap-1">
                    <AlertCircle className="h-3.5 w-3.5 text-amber-500" />
                    {sprint.openIssues} open
                  </span>
                  <span className="ml-auto font-semibold" style={{ color }}>
                    {sprint.completionPct}%
                  </span>
                </div>

                {sprint.dueDate && (
                  <p className="mt-1 text-[11px] text-slate-400">
                    Due: {new Date(sprint.dueDate).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                  </p>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
