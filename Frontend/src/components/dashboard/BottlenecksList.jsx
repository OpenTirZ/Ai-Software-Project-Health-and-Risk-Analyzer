import React, { useState } from 'react';
import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
} from 'recharts';
import {
  GitPullRequest,
  Clock,
  AlertTriangle,
  User,
} from 'lucide-react';

/**
 * Custom Tooltip for the Delivery Bottleneck Radar Chart
 */
const CustomRadarTooltip = ({ active, payload }) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    return (
      <div className="bg-slate-900/95 text-white p-3 rounded-xl shadow-xl text-xs border border-slate-700/80 backdrop-blur-md">
        <p className="font-bold text-indigo-300">{data.metric}</p>
        <p className="mt-1">
          Health Index: <span className="font-bold text-white">{data.score}/100</span>
        </p>
        <p className="text-slate-400">
          Raw Metric: <span className="text-amber-400 font-semibold">{data.display}</span>
        </p>
        <p className="text-slate-400">
          Target SLA: <span className="text-emerald-400 font-semibold">{data.threshold}</span>
        </p>
      </div>
    );
  }
  return null;
};

/**
 * BottlenecksList Component
 * Visualizes the Delivery Bottleneck Radar (Pending PRs > 48h, Review latency)
 * and detailed pending pull request bottleneck items without text collision.
 */
export const BottlenecksList = ({ bottleneckData }) => {
  const [severityFilter, setSeverityFilter] = useState('ALL');

  const radarData = bottleneckData?.radarData ?? [
    { metric: 'Pending >48h', score: 68, benchmark: 85, display: '4 PRs', threshold: '≤ 2' },
    { metric: 'Review Latency', score: 62, benchmark: 80, display: '34h avg', threshold: '≤ 24h' },
    { metric: 'CI/CD Speed', score: 94, benchmark: 90, display: '8.4m', threshold: '≤ 15m' },
    { metric: 'Merge Conflicts', score: 88, benchmark: 85, display: '4.2%', threshold: '≤ 8%' },
    { metric: 'Stale Branches', score: 71, benchmark: 80, display: '6 branches', threshold: '≤ 3' },
    { metric: 'PR Churn Size', score: 74, benchmark: 75, display: '+310 lines', threshold: '≤ 250' },
  ];

  const pendingOver48h = bottleneckData?.pendingPrsOver48hCount ?? 4;
  const avgReviewLatency = bottleneckData?.avgReviewLatencyHours ?? 34.2;

  const bottlenecks = bottleneckData?.criticalBottlenecks ?? [
    {
      id: 'PR-104',
      title: 'refactor(auth): migrate token rotation to asymmetric keypairs',
      author: 'sarah-connor',
      reviewer: 'alex-chen',
      hoursPending: 74,
      status: 'Waiting for Reviewer',
      severity: 'High',
      additions: 420,
      deletions: 110,
    },
    {
      id: 'PR-99',
      title: 'feat(ingest): batch pipeline streaming ingestion',
      author: 'dev-marcus',
      reviewer: 'sarah-connor',
      hoursPending: 61,
      status: 'Changes Requested',
      severity: 'High',
      additions: 780,
      deletions: 45,
    },
    {
      id: 'PR-112',
      title: 'fix(db): connection pool starvation during spike query',
      author: 'elena-rostova',
      reviewer: 'dev-marcus',
      hoursPending: 52,
      status: 'CI Failing',
      severity: 'Medium',
      additions: 65,
      deletions: 18,
    },
    {
      id: 'PR-115',
      title: 'chore: bump dependencies and security patches for vite',
      author: 'alex-chen',
      reviewer: 'elena-rostova',
      hoursPending: 49,
      status: 'Waiting for Reviewer',
      severity: 'Low',
      additions: 120,
      deletions: 95,
    },
  ];

  const filteredBottlenecks = bottlenecks.filter((item) => {
    if (severityFilter === 'ALL') return true;
    return item.severity.toUpperCase() === severityFilter;
  });

  const getSeverityBadge = (sev) => {
    switch (sev.toLowerCase()) {
      case 'high':
        return 'bg-rose-100 text-rose-800 border-rose-300';
      case 'medium':
        return 'bg-amber-100 text-amber-800 border-amber-300';
      default:
        return 'bg-blue-100 text-blue-800 border-blue-300';
    }
  };

  return (
    <div className="bg-white rounded-2xl p-6 border border-slate-200/90 shadow-sm flex flex-col justify-between min-w-0">
      {/* Top Header */}
      <div className="flex flex-wrap items-center justify-between pb-4 border-b border-slate-100 gap-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="w-10 h-10 rounded-xl bg-purple-50 border border-purple-100 flex items-center justify-center text-purple-600 shadow-sm shrink-0">
            <GitPullRequest className="w-5 h-5" />
          </div>
          <div className="min-w-0">
            <h2 className="text-base sm:text-lg font-bold text-slate-900 tracking-tight truncate">
              Delivery Bottleneck Radar
            </h2>
            <p className="text-xs text-slate-500 truncate">
              PR review friction, latency spikes & merge aging
            </p>
          </div>
        </div>

        {/* Top Mini Badges */}
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-xs font-semibold px-2.5 py-1 rounded-lg bg-rose-50 text-rose-700 border border-rose-200 flex items-center gap-1 shrink-0">
            <Clock className="w-3.5 h-3.5" />
            {pendingOver48h} PRs &gt; 48h
          </span>
          <span className="text-xs font-semibold px-2.5 py-1 rounded-lg bg-indigo-50 text-indigo-700 border border-indigo-200 hidden sm:inline-flex shrink-0">
            {avgReviewLatency}h Avg Latency
          </span>
        </div>
      </div>

      {/* Main Grid: Radar Chart + Bottleneck List */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 my-4 items-center min-w-0">
        {/* Left: Recharts Radar Chart (5 cols) with reduced outerRadius to prevent label clipping */}
        <div className="lg:col-span-5 flex flex-col items-center justify-center min-w-0">
          <div className="w-full h-64 sm:h-72 relative">
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart cx="50%" cy="50%" outerRadius="58%" data={radarData}>
                <PolarGrid stroke="#e2e8f0" strokeDasharray="3 3" />
                <PolarAngleAxis
                  dataKey="metric"
                  tick={{ fill: '#475569', fontSize: 10, fontWeight: 600 }}
                />
                <PolarRadiusAxis
                  angle={30}
                  domain={[0, 100]}
                  tick={{ fill: '#94a3b8', fontSize: 9 }}
                />
                <Radar
                  name="Current Project"
                  dataKey="score"
                  stroke="#8b5cf6"
                  fill="#8b5cf6"
                  fillOpacity={0.4}
                />
                <RechartsTooltip content={<CustomRadarTooltip />} />
              </RadarChart>
            </ResponsiveContainer>
          </div>
          <p className="text-[11px] text-slate-400 text-center mt-1">
            Higher area represents healthier, low-friction delivery velocity.
          </p>
        </div>

        {/* Right: Critical Bottlenecks List (7 cols) */}
        <div className="lg:col-span-7 space-y-3 min-w-0">
          <div className="flex flex-wrap items-center justify-between gap-2 pb-1">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-400 truncate">
              Pending PRs Aging &gt; 48h ({filteredBottlenecks.length})
            </span>

            {/* Severity Filter Pills */}
            <div className="flex items-center gap-1 text-[11px] shrink-0">
              {['ALL', 'HIGH', 'MEDIUM'].map((sev) => (
                <button
                  key={sev}
                  onClick={() => setSeverityFilter(sev)}
                  className={`px-2 py-0.5 rounded-md font-medium transition-colors ${
                    severityFilter === sev
                      ? 'bg-slate-800 text-white'
                      : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                  }`}
                >
                  {sev}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-2.5 max-h-[260px] overflow-y-auto pr-1">
            {filteredBottlenecks.map((pr) => (
              <div
                key={pr.id}
                className="p-3 rounded-xl bg-slate-50/90 border border-slate-200/80 hover:border-purple-300 hover:shadow-xs transition-all flex flex-col justify-between min-w-0"
              >
                {/* PR Top Row: ID, Severity, Hours Pending */}
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="text-xs font-extrabold text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded border border-indigo-200 font-mono shrink-0">
                      {pr.id}
                    </span>
                    <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded border shrink-0 ${getSeverityBadge(pr.severity)}`}>
                      {pr.severity}
                    </span>
                  </div>

                  <span className="text-xs font-bold text-rose-600 bg-rose-50 border border-rose-200 px-2 py-0.5 rounded-full flex items-center gap-1 shrink-0 ml-auto">
                    <Clock className="w-3 h-3" />
                    {pr.hoursPending}h pending
                  </span>
                </div>

                {/* PR Title */}
                <p className="text-xs font-semibold text-slate-800 mt-1.5 leading-snug break-words">
                  {pr.title}
                </p>

                {/* PR Bottom Meta: Author, Reviewer, Churn Diff */}
                <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 text-[11px] text-slate-500 mt-2 pt-2 border-t border-slate-200/60">
                  <div className="flex items-center gap-2 flex-wrap min-w-0">
                    <span className="flex items-center gap-1 truncate">
                      <User className="w-3 h-3 text-slate-400 shrink-0" />
                      <span className="text-slate-400">Author:</span> <strong className="text-slate-700">{pr.author}</strong>
                    </span>
                    <span className="hidden sm:inline text-slate-300">•</span>
                    <span className="truncate">
                      <span className="text-slate-400">Reviewer:</span> <strong className="text-slate-700">{pr.reviewer}</strong>
                    </span>
                  </div>

                  <div className="flex items-center gap-1.5 font-mono text-[10px] shrink-0 ml-auto">
                    <span className="text-emerald-600 font-semibold">+{pr.additions}</span>
                    <span className="text-rose-600 font-semibold">-{pr.deletions}</span>
                  </div>
                </div>
              </div>
            ))}

            {filteredBottlenecks.length === 0 && (
              <div className="p-6 text-center text-xs text-slate-400 bg-slate-50 rounded-xl border border-dashed border-slate-200">
                No bottlenecks found matching filter.
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Bottom Alert Note */}
      <div className="pt-3 border-t border-slate-100 flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500 mt-2">
        <span className="flex items-center gap-1.5 text-amber-700 font-medium">
          <AlertTriangle className="w-3.5 h-3.5 text-amber-500 shrink-0" />
          Review SLA Target: All PRs should receive initial review within 24 hours.
        </span>
        <span className="text-[11px] text-slate-400 hidden sm:inline shrink-0">
          {pendingOver48h} PRs exceed threshold
        </span>
      </div>
    </div>
  );
};

export default BottlenecksList;
