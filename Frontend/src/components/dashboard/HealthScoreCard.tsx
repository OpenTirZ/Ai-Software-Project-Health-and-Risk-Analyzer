import React from 'react';
import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts';
import { ShieldCheck, AlertTriangle, AlertCircle, Info, TrendingUp, TrendingDown } from 'lucide-react';
import type { HealthGaugeData } from '../../services/metricService';

// ---------------------------------------------------------------------------
// Design tokens (match project palette)
// ---------------------------------------------------------------------------
const GREEN = '#16A34A';
const AMBER = '#B45309';
const RED = '#CC1F2E';
const TRACK_BG = '#E5E7EB';

function statusColor(status: string): string {
  switch (status) {
    case 'Good':
      return GREEN;
    case 'Caution':
      return AMBER;
    case 'At Risk':
      return RED;
    default:
      return '#64748B';
  }
}

function StatusIcon({ status }: { status: string }) {
  switch (status) {
    case 'Good':
      return <ShieldCheck className="h-5 w-5" style={{ color: GREEN }} />;
    case 'Caution':
      return <AlertTriangle className="h-5 w-5" style={{ color: AMBER }} />;
    case 'At Risk':
      return <AlertCircle className="h-5 w-5" style={{ color: RED }} />;
    default:
      return <Info className="h-5 w-5 text-slate-400" />;
  }
}

// ---------------------------------------------------------------------------
// Health Score Card
// ---------------------------------------------------------------------------
interface Props {
  data: HealthGaugeData | null;
  isLoading: boolean;
  error: string | null;
}

export const HealthScoreCard: React.FC<Props> = ({ data, isLoading, error }) => {
  if (isLoading) {
    return (
      <div className="rounded-xl border border-[#9ED4C8] bg-white p-6 shadow-sm animate-pulse">
        <div className="flex items-center gap-3 mb-4">
          <div className="h-5 w-5 rounded bg-slate-200" />
          <div className="h-5 w-32 rounded bg-slate-200" />
        </div>
        <div className="flex items-center justify-center py-8">
          <div className="h-40 w-40 rounded-full bg-slate-100" />
        </div>
        <div className="mt-4 space-y-2">
          <div className="h-3 w-full rounded bg-slate-100" />
          <div className="h-3 w-3/4 rounded bg-slate-100" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-6">
        <div className="flex items-center gap-2 text-red-700">
          <AlertCircle className="h-5 w-5" />
          <span className="text-sm font-medium">Failed to load health score</span>
        </div>
        <p className="mt-2 text-xs text-red-600">{error}</p>
      </div>
    );
  }

  if (!data) return null;

  const score = data.score ?? 0;
  const color = statusColor(data.status);

  // Gauge data: filled arc + track
  const gaugeData = [
    { name: 'score', value: score },
    { name: 'track', value: 100 - score },
  ];

  return (
    <div className="rounded-xl border border-[#9ED4C8] bg-white p-6 shadow-sm">
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <StatusIcon status={data.status} />
          <h3 className="text-sm font-semibold text-slate-800">Overall Health Score</h3>
        </div>
        <span
          className="inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold"
          style={{
            backgroundColor: `${color}18`,
            color,
          }}
        >
          {data.status}
        </span>
      </div>

      {/* Gauge */}
      <div className="relative mx-auto w-full max-w-[180px] h-[110px]">
        <ResponsiveContainer width="100%" height={110}>
          <PieChart>
            <Pie
              data={gaugeData}
              cx="50%"
              cy="100%"
              startAngle={180}
              endAngle={0}
              innerRadius={60}
              outerRadius={80}
              paddingAngle={0}
              dataKey="value"
              stroke="none"
            >
              <Cell fill={color} />
              <Cell fill={TRACK_BG} />
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        {/* Score label */}
        <div className="absolute inset-x-0 bottom-0 flex flex-col items-center pointer-events-none">
          <span className="text-3xl font-bold" style={{ color }}>
            {score}
          </span>
          <span className="text-[10px] text-slate-500 font-medium">/ 100</span>
        </div>
      </div>

      {/* Summary */}
      <p className="mt-3 text-xs text-slate-600 leading-relaxed">{data.summaryStatement}</p>

      {/* Factor breakdown */}
      {data.factors.length > 0 && (
        <div className="mt-4 space-y-2">
          <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">Contributing Factors</p>
          {data.factors.map((f) => (
            <div key={f.label} className="flex items-center gap-2">
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-700 truncate">{f.label}</span>
                  <span className="text-xs font-semibold" style={{ color: statusColor(f.status) }}>
                    {f.score !== null ? f.score : '—'}
                  </span>
                </div>
                <div className="mt-1 h-1.5 w-full rounded-full bg-slate-100 overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-500"
                    style={{
                      width: `${f.score ?? 0}%`,
                      backgroundColor: statusColor(f.status),
                    }}
                  />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Flags summary */}
      {data.flags.total > 0 && (
        <div className="mt-4 flex items-center gap-3 rounded-lg bg-slate-50 px-3 py-2">
          <span className="text-xs text-slate-500">Flags:</span>
          {data.flags.high > 0 && (
            <span className="inline-flex items-center gap-1 text-xs font-medium text-red-600">
              <TrendingDown className="h-3 w-3" /> {data.flags.high} High
            </span>
          )}
          {data.flags.medium > 0 && (
            <span className="inline-flex items-center gap-1 text-xs font-medium" style={{ color: AMBER }}>
              <AlertTriangle className="h-3 w-3" /> {data.flags.medium} Med
            </span>
          )}
          {data.flags.low > 0 && (
            <span className="inline-flex items-center gap-1 text-xs font-medium text-green-600">
              <TrendingUp className="h-3 w-3" /> {data.flags.low} Low
            </span>
          )}
        </div>
      )}
    </div>
  );
};
