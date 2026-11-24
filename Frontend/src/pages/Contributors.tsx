import React, { useState, useEffect } from 'react';
import type { PageView } from '../types';
import { contributorsData } from '../data/mockData';
import { GitCommit, Clock, ExternalLink, GitPullRequest, AlertTriangle } from 'lucide-react';
import { metricService } from '../services/metricService';

interface ContributorsProps {
  projectId?: string;
  selectedRepo: string;
  onNavigate: (view: PageView) => void;
}

interface ContributorItem {
  id: string;
  name: string;
  username: string;
  commits: number;
  prs?: number;
  percentage?: number;
  isBusFactorRisk?: boolean;
  lastActive: string;
}

export const Contributors: React.FC<ContributorsProps> = ({ 
  projectId = 'proj_core_platform', 
  selectedRepo 
}) => {
  const [healthSummary, setHealthSummary] = useState<any>(null);

  useEffect(() => {
    let isMounted = true;
    metricService.getHealthSummary(projectId, selectedRepo)
      .then((data) => {
        if (isMounted && data) setHealthSummary(data);
      })
      .catch((err) => {
        console.warn('Could not load dynamic health summary in Contributors:', err);
      });
    return () => { isMounted = false; };
  }, [projectId, selectedRepo]);

  const apiContributors = healthSummary?.workload?.contributors;
  const list: ContributorItem[] = apiContributors && apiContributors.length > 0
    ? apiContributors.map((c: any, idx: number) => ({
        id: `c_${idx}`,
        name: c.name,
        username: c.name.toLowerCase().replace(/\s+/g, ''),
        commits: c.commits,
        prs: c.prs,
        percentage: c.percentage,
        isBusFactorRisk: c.isBusFactorRisk,
        lastActive: 'Recently',
      }))
    : contributorsData.map((c) => ({
        ...c,
        prs: undefined,
        percentage: undefined,
        isBusFactorRisk: undefined,
      }));
  return (
    <div className="p-6 md:p-8 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl md:text-3xl font-bold text-slate-900 tracking-tight">
          Contributors
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          Project Contributors from github for <span className="font-semibold text-slate-700">{selectedRepo}</span>.
        </p>
      </div>

      {/* Contributors Table Card */}
      <div className="bg-white rounded-2xl border border-slate-200/90 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50/70 text-slate-600 text-xs font-bold uppercase tracking-wider">
                <th className="py-4 px-6">Name</th>
                <th className="py-4 px-6">Username</th>
                <th className="py-4 px-6">Commits</th>
                <th className="py-4 px-6">PRs</th>
                <th className="py-4 px-6">Activity Share</th>
                <th className="py-4 px-6">Last Active</th>
                <th className="py-4 px-6 text-right">Profile</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-sm">
              {list.map((contributor) => (
                <tr key={contributor.id} className="hover:bg-slate-50/80 transition-colors">
                  {/* Name with Avatar */}
                  <td className="py-4 px-6">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-full bg-gradient-to-tr from-indigo-500 to-purple-600 text-white font-bold text-sm flex items-center justify-center shrink-0 shadow-sm">
                        {contributor.name
                          .split(' ')
                          .map((n: string) => n[0])
                          .join('')}
                      </div>
                      <div>
                        <div className="font-semibold text-slate-900">
                          {contributor.name}
                        </div>
                        <div className="text-xs text-slate-400">
                          GitHub Contributor
                        </div>
                      </div>
                    </div>
                  </td>

                  {/* Username */}
                  <td className="py-4 px-6 font-mono text-xs text-slate-600">
                    <span className="px-2.5 py-1 rounded-md bg-slate-100 border border-slate-200">
                      @{contributor.username}
                    </span>
                  </td>

                  {/* Commits */}
                  <td className="py-4 px-6">
                    <div className="flex items-center gap-2">
                      <GitCommit className="w-4 h-4 text-indigo-500" />
                      <span className="font-bold text-slate-900">
                        {contributor.commits}
                      </span>
                    </div>
                  </td>

                  {/* PRs */}
                  <td className="py-4 px-6">
                    <div className="flex items-center gap-2">
                      <GitPullRequest className="w-4 h-4 text-emerald-500" />
                      <span className="font-bold text-slate-900">
                        {contributor.prs ?? '—'}
                      </span>
                    </div>
                  </td>

                  {/* Activity Share */}
                  <td className="py-4 px-6">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-slate-900 text-xs">
                        {contributor.percentage ? `${contributor.percentage}%` : '—'}
                      </span>
                      {contributor.isBusFactorRisk && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-bold bg-amber-50 text-amber-700 border border-amber-200">
                          <AlertTriangle className="w-3 h-3 text-amber-500" />
                          <span>Bus Factor (38%)</span>
                        </span>
                      )}
                    </div>
                  </td>

                  {/* Last Active */}
                  <td className="py-4 px-6">
                    <div className="flex items-center gap-1.5 text-xs text-slate-500">
                      <Clock className="w-3.5 h-3.5 text-slate-400" />
                      <span>{contributor.lastActive}</span>
                    </div>
                  </td>

                  {/* Action */}
                  <td className="py-4 px-6 text-right">
                    <a
                      href={`https://github.com/${contributor.username}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-xs font-semibold text-indigo-600 hover:text-indigo-800 transition-colors"
                    >
                      <span>View GitHub</span>
                      <ExternalLink className="w-3.5 h-3.5" />
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
