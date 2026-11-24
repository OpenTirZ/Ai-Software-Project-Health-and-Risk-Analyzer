import React from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { Users, AlertCircle } from 'lucide-react';
import type { WorkloadEntry } from '../../services/metricService';

// ---------------------------------------------------------------------------
// Colour tokens
// ---------------------------------------------------------------------------
const COMMIT_COLOR = '#0B6B63';
const PR_COLOR = '#16A34A';

// ---------------------------------------------------------------------------
// Workload Chart (Bus Factor Visualisation)
// ---------------------------------------------------------------------------
interface Props {
  data: WorkloadEntry[];
  isLoading: boolean;
  error: string | null;
}

export const WorkloadChart: React.FC<Props> = ({ data, isLoading, error }) => {
  if (isLoading) {
    return (
      <div className="rounded-xl border border-[#9ED4C8] bg-white p-6 shadow-sm animate-pulse">
        <div className="flex items-center gap-2 mb-4">
          <div className="h-5 w-5 rounded bg-slate-200" />
          <div className="h-5 w-48 rounded bg-slate-200" />
        </div>
        <div className="h-64 rounded-lg bg-slate-100" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-6">
        <div className="flex items-center gap-2 text-red-700">
          <AlertCircle className="h-5 w-5" />
          <span className="text-sm font-medium">Failed to load workload data</span>
        </div>
        <p className="mt-2 text-xs text-red-600">{error}</p>
      </div>
    );
  }

  // Bus factor warning: if one person owns > 50 % of total commits
  const totalCommits = data.reduce((s, d) => s + d.commits, 0);
  const topContributor = data[0];
  const busFactor =
    topContributor && totalCommits > 0
      ? Math.round((topContributor.commits / totalCommits) * 100)
      : 0;
  const busFactorWarning = busFactor > 50;

  return (
    <div className="rounded-xl border border-[#9ED4C8] bg-white p-6 shadow-sm">
      {/* Header */}
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <Users className="h-5 w-5 text-[#0B6B63]" />
          <h3 className="text-sm font-semibold text-slate-800">Workload Distribution</h3>
        </div>
        {data.length > 0 && (
          <span className="text-xs text-slate-500">
            {data.length} contributor{data.length !== 1 && 's'}
          </span>
        )}
      </div>

      {/* Bus factor alert */}
      {busFactorWarning && topContributor && (
        <div className="mb-3 flex items-center gap-2 rounded-lg bg-amber-50 border border-amber-200 px-3 py-2">
          <AlertCircle className="h-4 w-4 text-amber-600 shrink-0" />
          <p className="text-xs text-amber-800">
            <strong>Bus factor risk:</strong> {topContributor.contributor} owns {busFactor}% of commits.
            Consider spreading ownership.
          </p>
        </div>
      )}

      {data.length === 0 ? (
        <div className="flex flex-col items-center gap-2 py-12 text-slate-400">
          <Users className="h-8 w-8" />
          <p className="text-sm font-medium">No workload data available</p>
          <p className="text-xs">Sync commits and PRs to populate this chart</p>
        </div>
      ) : (
        <div className="w-full min-w-0" style={{ height: Math.max(240, data.length * 36) }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={data}
              layout="vertical"
              margin={{ top: 8, right: 20, left: 10, bottom: 8 }}
            >
            <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" horizontal={false} />
            <XAxis type="number" tick={{ fontSize: 11 }} />
            <YAxis
              dataKey="contributor"
              type="category"
              width={100}
              tick={{ fontSize: 11 }}
              tickLine={false}
            />
            <Tooltip
              contentStyle={{
                fontSize: 12,
                borderRadius: 8,
                border: '1px solid #E2E8F0',
                boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
              }}
            />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Bar dataKey="commits" name="Commits" fill={COMMIT_COLOR} radius={[0, 4, 4, 0]} barSize={14} />
            <Bar dataKey="pullRequests" name="Pull Requests" fill={PR_COLOR} radius={[0, 4, 4, 0]} barSize={14} />
          </BarChart>
        </ResponsiveContainer>
        </div>
      )}
    </div>
  );
};
