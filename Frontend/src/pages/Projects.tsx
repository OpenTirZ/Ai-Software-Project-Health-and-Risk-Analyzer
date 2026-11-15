import React, { useState } from 'react';
import type { PageView, Repository } from '../types';
import { Search, Plus, GitBranch, ShieldCheck, AlertTriangle, ArrowRight } from 'lucide-react';

interface ProjectsProps {
  repositories: Repository[];
  onSelectRepo: (repo: string) => void;
  onNavigate: (view: PageView) => void;
}

export const Projects: React.FC<ProjectsProps> = ({
  repositories,
  onSelectRepo,
  onNavigate,
}) => {
  const [searchTerm, setSearchTerm] = useState('');

  const filteredRepos = repositories.filter(
    (repo) =>
      repo.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      repo.branch.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const getRiskBadge = (risk: Repository['riskClassification']) => {
    switch (risk) {
      case 'LOW RISK':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
            LOW RISK
          </span>
        );
      case 'ELEVATED CHURN':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-bold bg-amber-50 text-amber-700 border border-amber-200">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-500"></span>
            ELEVATED CHURN
          </span>
        );
      case 'HIGH RISK':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-bold bg-rose-50 text-rose-700 border border-rose-200">
            <span className="w-1.5 h-1.5 rounded-full bg-rose-500"></span>
            HIGH RISK
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-bold bg-blue-50 text-blue-700 border border-blue-200">
            <span className="w-1.5 h-1.5 rounded-full bg-blue-500"></span>
            {risk}
          </span>
        );
    }
  };

  const getHealthScoreColor = (score: number) => {
    if (score >= 80) return 'text-emerald-600';
    if (score >= 60) return 'text-amber-500';
    return 'text-rose-600';
  };

  const getProgressColor = (score: number) => {
    if (score >= 80) return 'bg-emerald-500';
    if (score >= 60) return 'bg-amber-500';
    return 'bg-rose-500';
  };

  return (
    <div className="p-6 md:p-8 max-w-7xl mx-auto space-y-6">
      {/* Top Banner & KPI Cards */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold text-slate-900 tracking-tight">
            All Repositories
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Monitor automated health checks, git branch risks, and software quality audits.
          </p>
        </div>

        {/* Connect New Repository Button */}
        <button
          onClick={() => onNavigate('create-project')}
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-[10px] text-white text-sm font-semibold shadow-lg shadow-indigo-500/25 transition-all hover:opacity-95 active:scale-95 cursor-pointer"
          style={{
            background: 'linear-gradient(90deg, rgba(0, 0, 0, 0.2) 0%, rgba(0, 0, 0, 0.2) 100%), linear-gradient(90deg, rgb(99, 102, 241) 0%, rgb(168, 85, 247) 100%)',
          }}
        >
          <Plus className="w-4 h-4" />
          <span>+ Connect New</span>
        </button>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
        {/* TOTAL REPOSITORIES */}
        <div className="bg-white rounded-xl p-5 border border-slate-200/90 shadow-sm flex flex-col justify-between hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-[11px] font-extrabold uppercase tracking-wider text-slate-400">
              TOTAL REPOSITORIES
            </span>
            <GitBranch className="w-4 h-4 text-indigo-500" />
          </div>
          <div className="mt-3 flex items-baseline justify-between">
            <span className="text-3xl font-bold text-slate-900">
              8 Active
            </span>
            <span className="inline-flex items-center text-xs font-bold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-md">
              100% Monitored
            </span>
          </div>
        </div>

        {/* AVERAGE HEALTH SCORE */}
        <div className="bg-white rounded-xl p-5 border border-slate-200/90 shadow-sm flex flex-col justify-between hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-[11px] font-extrabold uppercase tracking-wider text-slate-400">
              AVERAGE HEALTH SCORE
            </span>
            <ShieldCheck className="w-4 h-4 text-emerald-500" />
          </div>
          <div className="mt-3 flex items-baseline justify-between">
            <span className="text-3xl font-bold text-slate-900">
              84.6 <span className="text-sm font-normal text-slate-400">/ 100</span>
            </span>
            <span className="inline-flex items-center text-xs font-bold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-md">
              +3.1% ↑
            </span>
          </div>
        </div>

        {/* SECURITY & RISK STATUS */}
        <div className="bg-white rounded-xl p-5 border border-slate-200/90 shadow-sm flex flex-col justify-between hover:shadow-md transition-shadow sm:col-span-2 lg:col-span-1">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-[11px] font-extrabold uppercase tracking-wider text-slate-400">
              RISK CLASSIFICATIONS
            </span>
            <AlertTriangle className="w-4 h-4 text-amber-500" />
          </div>
          <div className="mt-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-2xl font-bold text-slate-900">3</span>
              <span className="text-xs text-slate-500">Flags Raised</span>
            </div>
            <button
              onClick={() => onNavigate('risk-analysis')}
              className="text-xs font-semibold text-indigo-600 hover:text-indigo-800 transition-colors cursor-pointer"
            >
              Review Risks →
            </button>
          </div>
        </div>
      </div>

      {/* Search Bar */}
      <div className="bg-white rounded-xl p-3 border border-slate-200/90 shadow-sm flex items-center gap-3">
        <Search className="w-5 h-5 text-slate-400 ml-2" />
        <input
          type="text"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          placeholder="Search Project, repositories, branches..."
          className="w-full text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none bg-transparent"
        />
        {searchTerm && (
          <button
            onClick={() => setSearchTerm('')}
            className="text-xs text-slate-400 hover:text-slate-600 px-2 cursor-pointer"
          >
            Clear
          </button>
        )}
      </div>

      {/* Repositories Table */}
      <div className="bg-white rounded-xl border border-slate-200/90 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50/70 text-slate-600 text-xs font-bold uppercase tracking-wider">
                <th className="py-4 px-6">PROJECT NAME</th>
                <th className="py-4 px-6">BRANCH</th>
                <th className="py-4 px-6">AI HEALTH SCORE</th>
                <th className="py-4 px-6">RISK CLASSIFICATION</th>
                <th className="py-4 px-6">LAST AUDIT</th>
                <th className="py-4 px-6 text-right">ACTIONS</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-sm">
              {filteredRepos.length > 0 ? (
                filteredRepos.map((repo) => (
                  <tr
                    key={repo.id}
                    onClick={() => {
                      onSelectRepo(repo.name);
                      onNavigate('overview');
                    }}
                    className="hover:bg-indigo-50/40 transition-colors cursor-pointer group"
                  >
                    <td className="py-4 px-6">
                      <div className="font-semibold text-slate-900 group-hover:text-indigo-600 transition-colors">
                        {repo.name}
                      </div>
                      {repo.description && (
                        <p className="text-xs text-slate-400 line-clamp-1 mt-0.5">
                          {repo.description}
                        </p>
                      )}
                    </td>
                    <td className="py-4 px-6 font-mono text-xs text-slate-600">
                      <span className="px-2 py-0.5 rounded bg-slate-100 border border-slate-200">
                        {repo.branch}
                      </span>
                    </td>
                    <td className="py-4 px-6">
                      <div className="flex items-center gap-3">
                        <div className="w-24 bg-slate-100 h-2 rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full ${getProgressColor(repo.healthScore)}`}
                            style={{ width: `${repo.healthScore}%` }}
                          />
                        </div>
                        <span className={`font-bold text-xs ${getHealthScoreColor(repo.healthScore)}`}>
                          {repo.healthScore}%
                        </span>
                      </div>
                    </td>
                    <td className="py-4 px-6">
                      {getRiskBadge(repo.riskClassification)}
                    </td>
                    <td className="py-4 px-6 text-slate-500 text-xs">
                      {repo.lastAudit}
                    </td>
                    <td className="py-4 px-6 text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectRepo(repo.name);
                          onNavigate('overview');
                        }}
                        className="inline-flex items-center gap-1 text-xs font-bold text-indigo-700 hover:text-indigo-900 group-hover:translate-x-0.5 transition-all cursor-pointer"
                      >
                        <span>View Audit</span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-slate-400 text-sm">
                    No repositories matched your search query.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
