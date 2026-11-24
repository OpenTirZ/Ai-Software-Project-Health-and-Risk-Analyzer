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
import { Users, AlertTriangle, ShieldCheck, Info, UserCheck } from 'lucide-react';

/**
 * Custom X-Axis Tick Component
 * Renders contributor names clearly horizontally on two lines (First Name & Last Name)
 * to guarantee 100% visibility without any text clipping or angled distortion.
 */
const CustomXAxisTick = (props) => {
  const { x, y, payload } = props;
  if (!payload || !payload.value) return null;

  const fullName = String(payload.value);
  const parts = fullName.split(' ');
  const firstName = parts[0] || fullName;
  const lastName = parts.slice(1).join(' ') || '';

  return (
    <g transform={`translate(${x},${y})`}>
      <text textAnchor="middle" fill="#0f172a" fontSize={12} fontWeight={700}>
        <tspan x={0} dy={14}>{firstName}</tspan>
        {lastName && (
          <tspan x={0} dy={14} fill="#475569" fontWeight={600} fontSize={11}>
            {lastName}
          </tspan>
        )}
      </text>
    </g>
  );
};

/**
 * Custom Tooltip for Workload Distribution Bar Chart
 */
const CustomWorkloadTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    return (
      <div className="bg-slate-900/95 text-white p-3.5 rounded-xl shadow-xl text-xs border border-slate-700/80 backdrop-blur-md">
        <p className="font-bold text-indigo-300 text-sm mb-1.5 flex items-center gap-1.5">
          <UserCheck className="w-3.5 h-3.5 text-indigo-400" />
          <span>{label}</span>
        </p>
        <div className="space-y-1.5">
          <p className="flex items-center justify-between gap-5 text-slate-300">
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-sm bg-indigo-500 inline-block" />
              Commits:
            </span>
            <span className="font-mono font-bold text-white text-xs">{data.commits}</span>
          </p>
          <p className="flex items-center justify-between gap-5 text-slate-300">
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-sm bg-cyan-500 inline-block" />
              Pull Requests:
            </span>
            <span className="font-mono font-bold text-white text-xs">{data.prs}</span>
          </p>
          <div className="pt-1.5 mt-1 border-t border-slate-700/80 flex items-center justify-between text-slate-400">
            <span>Team Activity Share:</span>
            <span className="font-bold text-amber-300 text-xs">{data.percentage}%</span>
          </div>
          {data.isBusFactorRisk && (
            <p className="text-[10px] text-rose-400 font-semibold mt-1">
              ⚠️ Bus factor risk (&gt; 35% of total activity)
            </p>
          )}
        </div>
      </div>
    );
  }
  return null;
};

/**
 * WorkloadChart Component
 * Visualizes Commits and PRs per contributor to evaluate team balance and Bus Factor
 * with crystal-clear contributor names in both the chart and the contributor cards.
 */
export const WorkloadChart = ({ workloadData }) => {
  const contributors = workloadData?.contributors ?? [
    { name: 'Sarah Connor', commits: 48, prs: 14, totalActivity: 62, percentage: 38.3, isBusFactorRisk: true },
    { name: 'Alex Chen', commits: 32, prs: 9, totalActivity: 41, percentage: 25.3, isBusFactorRisk: false },
    { name: 'Marcus Dev', commits: 22, prs: 6, totalActivity: 28, percentage: 17.3, isBusFactorRisk: false },
    { name: 'Elena Rostova', commits: 16, prs: 4, totalActivity: 20, percentage: 12.3, isBusFactorRisk: false },
    { name: 'David Kim', commits: 9, prs: 2, totalActivity: 11, percentage: 6.8, isBusFactorRisk: false },
  ];

  const busFactorScore = workloadData?.busFactorScore ?? 2;
  const busFactorRisk = workloadData?.busFactorRisk ?? 'Moderate Risk';

  return (
    <div className="bg-white rounded-2xl p-6 border border-slate-200/90 shadow-sm flex flex-col justify-between min-w-0">
      {/* Top Header */}
      <div className="flex flex-wrap items-center justify-between pb-4 border-b border-slate-100 gap-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="w-10 h-10 rounded-xl bg-cyan-50 border border-cyan-100 flex items-center justify-center text-cyan-600 shadow-sm shrink-0">
            <Users className="w-5 h-5" />
          </div>
          <div className="min-w-0">
            <h2 className="text-base sm:text-lg font-bold text-slate-900 tracking-tight truncate">
              Workload Distribution & Bus Factor
            </h2>
            <p className="text-xs text-slate-500 truncate">
              Commits & Pull Requests per contributor (bus factor analysis)
            </p>
          </div>
        </div>

        {/* Bus Factor Pill */}
        <div className="flex items-center gap-2 shrink-0">
          <div className="px-3 py-1 rounded-xl bg-amber-50 border border-amber-200 text-amber-800 flex items-center gap-1.5 text-xs font-bold">
            <AlertTriangle className="w-3.5 h-3.5 text-amber-600 shrink-0" />
            <span>Bus Factor: {busFactorScore} ({busFactorRisk})</span>
          </div>
        </div>
      </div>

      {/* 1. Bar Chart Section with Custom Crystal-Clear Contributor Names */}
      <div className="my-4 min-w-0">
        <div className="flex items-center justify-between text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">
          <span>Activity by Contributor</span>
          <span className="text-[11px] font-medium text-slate-500 lowercase">commits vs pull requests</span>
        </div>

        <div className="w-full h-64 sm:h-72">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={contributors}
              margin={{ top: 15, right: 15, left: -10, bottom: 35 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
              <XAxis
                dataKey="name"
                tick={<CustomXAxisTick />}
                interval={0}
                height={55}
                tickLine={false}
              />
              <YAxis
                tick={{ fill: '#94a3b8', fontSize: 10 }}
                width={30}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip content={<CustomWorkloadTooltip />} />
              <Legend
                verticalAlign="top"
                align="right"
                wrapperStyle={{ paddingBottom: 12, fontSize: 11 }}
              />
              <Bar
                dataKey="commits"
                name="Commits"
                fill="#6366f1"
                radius={[5, 5, 0, 0]}
                barSize={20}
              />
              <Bar
                dataKey="prs"
                name="Pull Requests"
                fill="#06b6d4"
                radius={[5, 5, 0, 0]}
                barSize={20}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* 2. Contributor Cards Breakdown with Full, Non-Truncated Names */}
      <div className="mt-4 pt-4 border-t border-slate-100 space-y-3 min-w-0">
        <div className="flex items-center justify-between text-xs font-bold uppercase tracking-wider text-slate-400">
          <span>Contributor Profiles & Share</span>
          <span className="text-[11px] font-medium text-slate-500">
            {contributors.length} active contributor{contributors.length === 1 ? '' : 's'}
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
          {contributors.map((c, idx) => (
            <div
              key={idx}
              className={`p-3 rounded-xl border transition-all flex flex-col justify-between gap-2 min-w-0 ${
                c.isBusFactorRisk
                  ? 'bg-amber-50/70 border-amber-300 ring-1 ring-amber-200'
                  : 'bg-slate-50/80 border-slate-200/80'
              }`}
            >
              {/* Header: Avatar + Full Name + Risk Badge */}
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-2.5 min-w-0">
                  <div className="w-8 h-8 rounded-lg bg-indigo-100 text-indigo-700 font-bold text-xs flex items-center justify-center shrink-0 shadow-xs">
                    {c.name
                      .split(' ')
                      .map((n) => n[0])
                      .join('')}
                  </div>
                  <div className="min-w-0">
                    {/* Contributor Full Name in Bold, Never Truncated */}
                    <p className="font-bold text-slate-900 text-sm whitespace-nowrap">
                      {c.name}
                    </p>
                    <p className="text-[11px] text-slate-500 whitespace-nowrap">
                      {c.commits} commits • {c.prs} PRs
                    </p>
                  </div>
                </div>

                {c.isBusFactorRisk && (
                  <span className="text-[10px] font-bold bg-amber-100 text-amber-800 px-2 py-0.5 rounded-full border border-amber-300 shrink-0">
                    Key Risk
                  </span>
                )}
              </div>

              {/* Progress & Percentage Share */}
              <div className="pt-1.5 border-t border-slate-200/50">
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="text-slate-500 text-[11px]">Throughput Share:</span>
                  <span className="font-extrabold text-slate-900">{c.percentage}%</span>
                </div>
                <div className="w-full bg-slate-200 h-1.5 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${
                      c.isBusFactorRisk ? 'bg-amber-500' : 'bg-indigo-500'
                    }`}
                    style={{ width: `${Math.min(c.percentage * 2, 100)}%` }}
                  />
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Bus Factor Insight Box with Highlighted Primary Contributor Name - Dynamically Calculated */}
        <div className="p-3 bg-amber-50/70 rounded-xl border border-amber-200/80 text-xs text-amber-900 flex items-start gap-2.5 mt-2">
          <Info className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
          <p className="leading-relaxed break-words">
            <strong>Bus Factor Warning:</strong>{' '}
            {workloadData?.busFactorDescription ? (
              workloadData.busFactorDescription
            ) : (
              <>
                Top contributor{' '}
                <strong className="text-amber-950 font-extrabold bg-amber-100 px-1.5 py-0.5 rounded border border-amber-300">
                  {contributors[0]?.name || 'Top Contributor'}
                </strong>{' '}
                accounts for <strong>{contributors[0]?.percentage || 0}%</strong> of all code activity, and the top 2 contributors represent{' '}
                <strong>
                  {(((contributors[0]?.percentage || 0) + (contributors[1]?.percentage || 0))).toFixed(1)}%
                </strong>{' '}
                of team throughput. Knowledge transfer is recommended to reduce single points of failure.
              </>
            )}
          </p>
        </div>
      </div>

      {/* Footer Insight */}
      <div className="pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500 mt-3">
        <span className="flex items-center gap-1.5 text-slate-600 truncate">
          <ShieldCheck className="w-3.5 h-3.5 text-indigo-600 shrink-0" />
          Optimal team bus factor is &gt; 3 with no single contributor holding &gt; 30% of critical paths.
        </span>
      </div>
    </div>
  );
};

export default WorkloadChart;
