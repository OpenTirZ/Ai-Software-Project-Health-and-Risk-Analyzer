import React, { useState, useEffect } from 'react';
import type { PageView } from '../types';
import {
  dataSyncApi,
  type ProjectResponse,
} from '../services/api';
import { GitCommit, Clock, ExternalLink, RefreshCw, Users, ArrowLeft } from 'lucide-react';

interface ContributorsProps {
  project: ProjectResponse | null;
  onNavigate: (view: PageView) => void;
}

export const Contributors: React.FC<ContributorsProps> = ({ project, onNavigate }) => {
  const [contributors, setContributors] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isSyncing, setIsSyncing] = useState<boolean>(false);
  const [syncFeedback, setSyncFeedback] = useState<string | null>(null);

  const loadContributors = async (projectId: string) => {
    setIsLoading(true);
    try {
      const data = await dataSyncApi.getContributors(projectId);
      setContributors(Array.isArray(data) ? data : []);
    } catch (err: any) {
      console.warn('Could not load contributors:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (project?.id) {
      loadContributors(project.id);
    }
  }, [project?.id]);

  const handleSyncContributors = async () => {
    if (!project?.id) return;
    setIsSyncing(true);
    setSyncFeedback('Synchronizing contributors from GitHub...');
    try {
      await dataSyncApi.syncContributors(project.id);
      setSyncFeedback('Contributors synchronized successfully!');
      await loadContributors(project.id);
      setTimeout(() => setSyncFeedback(null), 3500);
    } catch (err: any) {
      setSyncFeedback(`Sync note: ${err.message || 'Contributor sync failed.'}`);
      setTimeout(() => setSyncFeedback(null), 4000);
    } finally {
      setIsSyncing(false);
    }
  };

  if (!project) {
    return (
      <div className="p-8 max-w-4xl mx-auto text-center space-y-4">
        <p className="text-slate-500">Please select an active project to view team contributors.</p>
        <button
          onClick={() => onNavigate('projects')}
          className="px-4 py-2 bg-indigo-600 text-white rounded-xl text-xs font-bold"
        >
          View Projects
        </button>
      </div>
    );
  }

  return (
    <div className="p-6 md:p-8 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <button
            onClick={() => onNavigate('overview')}
            className="inline-flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-800 font-medium mb-1 cursor-pointer"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Back to Project Overview</span>
          </button>
          <h1 className="text-2xl md:text-3xl font-bold text-slate-900 tracking-tight">
            Team & Contributors
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Active GitHub repository contributors and commit share for <span className="font-semibold text-slate-700">{project.name}</span>.
          </p>
        </div>

        <button
          onClick={handleSyncContributors}
          disabled={isSyncing}
          className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-xs font-bold shadow-md shadow-indigo-600/20 transition-all cursor-pointer disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isSyncing ? 'animate-spin' : ''}`} />
          <span>{isSyncing ? 'Synchronizing...' : 'Sync Contributors'}</span>
        </button>
      </div>

      {syncFeedback && (
        <div className="p-3 bg-indigo-50 border border-indigo-200 rounded-xl text-xs text-indigo-900 animate-fadeIn">
          {syncFeedback}
        </div>
      )}

      {/* Contributors Table Card */}
      <div className="bg-white rounded-2xl border border-slate-200/90 shadow-sm overflow-hidden">
        {contributors.length === 0 ? (
          <div className="p-12 text-center text-slate-400 text-xs space-y-2">
            <Users className="w-8 h-8 text-slate-300 mx-auto" />
            <p>No contributors found. Click "Sync Contributors" to ingest contributor activity from GitHub.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50/70 text-slate-600 text-xs font-bold uppercase tracking-wider">
                  <th className="py-4 px-6">Contributor</th>
                  <th className="py-4 px-6">GitHub Username</th>
                  <th className="py-4 px-6">Contributions</th>
                  <th className="py-4 px-6 text-right">GitHub Profile</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-sm">
                {contributors.map((contrib, i) => {
                  const username = contrib.github_username || contrib.login || contrib.username || 'unknown';
                  const count = contrib.contributions || contrib.commits || 1;
                  const initial = username.charAt(0).toUpperCase();

                  return (
                    <tr key={contrib._id || username || i} className="hover:bg-slate-50/80 transition-colors">
                      <td className="py-4 px-6">
                        <div className="flex items-center gap-3">
                          <div className="w-9 h-9 rounded-full bg-gradient-to-tr from-indigo-500 to-purple-600 text-white font-bold text-xs flex items-center justify-center shrink-0 shadow-sm">
                            {initial}
                          </div>
                          <div>
                            <div className="font-semibold text-slate-900">{username}</div>
                            <div className="text-xs text-slate-400">Contributor</div>
                          </div>
                        </div>
                      </td>

                      <td className="py-4 px-6 font-mono text-xs text-slate-600">
                        <span className="px-2.5 py-1 rounded-md bg-slate-100 border border-slate-200">
                          @{username}
                        </span>
                      </td>

                      <td className="py-4 px-6">
                        <div className="flex items-center gap-2">
                          <GitCommit className="w-4 h-4 text-indigo-500" />
                          <span className="font-bold text-slate-900">{count}</span>
                        </div>
                      </td>

                      <td className="py-4 px-6 text-right">
                        <a
                          href={`https://github.com/${username}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 text-xs font-semibold text-indigo-600 hover:text-indigo-800 transition-colors"
                        >
                          <span>View Profile</span>
                          <ExternalLink className="w-3.5 h-3.5" />
                        </a>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
