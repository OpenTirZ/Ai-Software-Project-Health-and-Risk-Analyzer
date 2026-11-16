import React, { useState } from 'react';
import type { PageView } from '../types';
import type { ProjectResponse } from '../services/api';
import { Search, Plus, GitBranch, ArrowRight, Layers, ExternalLink, RefreshCw } from 'lucide-react';

interface ProjectsProps {
  projects: ProjectResponse[];
  onSelectProject: (projectId: string) => void;
  onNavigate: (view: PageView) => void;
  onRefreshProjects?: () => void;
}

export const Projects: React.FC<ProjectsProps> = ({
  projects = [],
  onSelectProject,
  onNavigate,
  onRefreshProjects,
}) => {
  const [searchTerm, setSearchTerm] = useState('');

  const filteredProjects = projects.filter((p) => {
    const q = searchTerm.toLowerCase();
    const name = (p.name || '').toLowerCase();
    const desc = (p.description || '').toLowerCase();
    const repo = (p.repo_url || '').toLowerCase();
    return name.includes(q) || desc.includes(q) || repo.includes(q);
  });

  const connectedCount = projects.filter((p) => Boolean(p.repo_url)).length;

  return (
    <div className="p-6 md:p-8 max-w-7xl mx-auto space-y-6">
      {/* Top Banner & Actions */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold text-slate-900 tracking-tight">
            Projects & Repositories
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Monitor automated health checks, git branch risks, and software quality audits.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {onRefreshProjects && (
            <button
              onClick={onRefreshProjects}
              className="p-2.5 bg-white border border-slate-200 text-slate-600 hover:text-slate-900 rounded-xl hover:bg-slate-50 shadow-sm transition-all cursor-pointer"
              title="Refresh projects list"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          )}

          <button
            onClick={() => onNavigate('create-project')}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-white text-xs font-bold shadow-md shadow-indigo-600/20 bg-indigo-600 hover:bg-indigo-700 transition-all cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            <span>+ Create New Project</span>
          </button>
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl p-5 border border-slate-200/90 shadow-sm">
          <p className="text-[11px] font-extrabold uppercase text-slate-400 tracking-wider">
            TOTAL PROJECTS
          </p>
          <p className="text-3xl font-bold text-slate-900 mt-2">{projects.length}</p>
          <p className="text-xs text-slate-500 mt-1">Configured in workspace</p>
        </div>

        <div className="bg-white rounded-xl p-5 border border-slate-200/90 shadow-sm">
          <p className="text-[11px] font-extrabold uppercase text-indigo-500 tracking-wider">
            CONNECTED REPOSITORIES
          </p>
          <p className="text-3xl font-bold text-slate-900 mt-2">{connectedCount}</p>
          <p className="text-xs text-slate-500 mt-1">GitHub integration active</p>
        </div>

        <div className="bg-white rounded-xl p-5 border border-slate-200/90 shadow-sm">
          <p className="text-[11px] font-extrabold uppercase text-emerald-500 tracking-wider">
            HEALTH STATUS
          </p>
          <p className="text-3xl font-bold text-slate-900 mt-2">Active</p>
          <p className="text-xs text-slate-500 mt-1">Deterministic risk engine ready</p>
        </div>
      </div>

      {/* Search Input */}
      <div className="flex items-center gap-2 bg-white px-4 py-2.5 rounded-xl border border-slate-200/90 shadow-sm">
        <Search className="w-4 h-4 text-slate-400 shrink-0" />
        <input
          type="text"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          placeholder="Search projects by name, description, or repository URL..."
          className="w-full text-xs text-slate-800 placeholder:text-slate-400 focus:outline-none bg-transparent"
        />
      </div>

      {/* Projects List Card */}
      <div className="bg-white rounded-2xl border border-slate-200/90 shadow-sm overflow-hidden">
        {filteredProjects.length === 0 ? (
          <div className="p-14 text-center space-y-4">
            <div className="w-12 h-12 bg-indigo-50 text-indigo-600 rounded-2xl flex items-center justify-center mx-auto shadow-inner">
              <Layers className="w-6 h-6" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-900">
                {projects.length === 0 ? 'No Projects Found' : 'No Matching Projects'}
              </h3>
              <p className="text-xs text-slate-500 max-w-sm mx-auto mt-1">
                {projects.length === 0
                  ? 'Get started by creating your first project and linking your GitHub repository.'
                  : 'Try adjusting your search query.'}
              </p>
            </div>
            {projects.length === 0 && (
              <button
                onClick={() => onNavigate('create-project')}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-indigo-600 text-white text-xs font-bold hover:bg-indigo-700 transition-colors shadow-md shadow-indigo-600/20 cursor-pointer"
              >
                <span>+ Create Your First Project</span>
              </button>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50/70 text-slate-600 text-xs font-bold uppercase tracking-wider">
                  <th className="py-4 px-6">Project Name</th>
                  <th className="py-4 px-6">GitHub Repository</th>
                  <th className="py-4 px-6">Default Branch</th>
                  <th className="py-4 px-6">Created</th>
                  <th className="py-4 px-6 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-sm">
                {filteredProjects.map((project) => {
                  return (
                    <tr
                      key={project.id}
                      onClick={() => {
                        onSelectProject(project.id);
                        onNavigate('overview');
                      }}
                      className="hover:bg-slate-50/80 transition-colors cursor-pointer group"
                    >
                      <td className="py-4 px-6">
                        <div className="font-semibold text-slate-900 group-hover:text-indigo-600 transition-colors">
                          {project.name}
                        </div>
                        {project.description && (
                          <p className="text-xs text-slate-400 line-clamp-1 mt-0.5">
                            {project.description}
                          </p>
                        )}
                      </td>

                      <td className="py-4 px-6">
                        {project.repo_url ? (
                          <div className="flex items-center gap-1.5 text-xs text-slate-700 font-mono">
                            <GitBranch className="w-3.5 h-3.5 text-indigo-500" />
                            <span>{project.repo_url.replace(/^https:\/\/github\.com\//, '')}</span>
                          </div>
                        ) : (
                          <span className="text-xs text-amber-600 font-medium bg-amber-50 px-2 py-0.5 rounded">
                            Not connected
                          </span>
                        )}
                      </td>

                      <td className="py-4 px-6 font-mono text-xs text-slate-600">
                        <span className="px-2 py-0.5 rounded bg-slate-100 border border-slate-200">
                          {project.default_branch || 'main'}
                        </span>
                      </td>

                      <td className="py-4 px-6 text-slate-500 text-xs">
                        {project.createdAt ? new Date(project.createdAt).toLocaleDateString() : 'Recent'}
                      </td>

                      <td className="py-4 px-6 text-right">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            onSelectProject(project.id);
                            onNavigate('overview');
                          }}
                          className="inline-flex items-center gap-1 text-xs font-bold text-indigo-600 hover:text-indigo-800 transition-colors cursor-pointer"
                        >
                          <span>Open Overview</span>
                          <ArrowRight className="w-3.5 h-3.5" />
                        </button>
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
