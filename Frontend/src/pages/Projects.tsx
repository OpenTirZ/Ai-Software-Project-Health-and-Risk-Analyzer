
import React, { useState } from 'react';
import type { PageView } from '../types';
import type { ProjectResponse } from '../services/api';
import {
  Search,
  Plus,
  GitBranch,
  ArrowRight,
  Layers,
  RefreshCw,
  FolderGit2,
  Activity,
} from 'lucide-react';

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

  const filteredProjects = projects.filter((project) => {
    const query = searchTerm.toLowerCase();
    const name = (project.name || '').toLowerCase();
    const description = (project.description || '').toLowerCase();
    const repository = (project.repo_url || '').toLowerCase();

    return (
      name.includes(query) ||
      description.includes(query) ||
      repository.includes(query)
    );
  });

  const connectedCount = projects.filter(
    (project) => Boolean(project.repo_url)
  ).length;

  const openProject = (projectId: string) => {
    onSelectProject(projectId);
    onNavigate('overview');
  };

  return (
    <main className="mx-auto w-full max-w-7xl space-y-6 p-4 sm:p-6 lg:p-8">
      {/* Page heading and actions */}
      <section className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-slate-500">
            Workspace
          </p>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
            Projects & Repositories
          </h1>
          <p className="mt-2 max-w-2xl text-sm text-slate-600">
            Manage connected repositories and review the health of your
            software projects.
          </p>
        </div>

        <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto">
          {onRefreshProjects && (
            <button
              type="button"
              onClick={onRefreshProjects}
              title="Refresh projects list"
              aria-label="Refresh projects list"
              className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-3 text-sm font-medium text-slate-700 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-teal-700 focus:ring-offset-2"
            >
              <RefreshCw className="h-4 w-4" />
              <span className="sm:hidden">Refresh</span>
            </button>
          )}

          <button
            type="button"
            onClick={() => onNavigate('create-project')}
            className="inline-flex min-h-10 flex-1 items-center justify-center gap-2 rounded-lg bg-[#0B6B63] px-4 py-2 text-sm font-semibold text-white hover:bg-[#084F49] focus:outline-none focus:ring-2 focus:ring-teal-700 focus:ring-offset-2 sm:flex-none"
          >
            <Plus className="h-4 w-4" />
            Create New Project
          </button>
        </div>
      </section>

      {/* Summary cards */}
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="rounded-xl border border-[#9ED4C8] bg-white p-5">
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Total Projects
            </p>
            <div className="rounded-lg bg-[#CDEFE6] p-2 text-[#0B6B63]">
              <FolderGit2 className="h-5 w-5" />
            </div>
          </div>
          <p className="mt-3 text-3xl font-bold tabular-nums text-[#0E2A2A]">
            {projects.length}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            Configured in workspace
          </p>
        </div>

        <div className="rounded-xl border border-[#9ED4C8] bg-white p-5">
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Connected Repositories
            </p>
            <div className="rounded-lg bg-[#CDEFE6] p-2 text-[#0B6B63]">
              <GitBranch className="h-5 w-5" />
            </div>
          </div>
          <p className="mt-3 text-3xl font-bold tabular-nums text-[#0E2A2A]">
            {connectedCount}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            GitHub repositories linked
          </p>
        </div>

        <div className="rounded-xl border border-[#9ED4C8] bg-white p-5">
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Health Status
            </p>
            <div className="rounded-lg bg-[#CDEFE6] p-2 text-[#0B6B63]">
              <Activity className="h-5 w-5" />
            </div>
          </div>
          <p className="mt-3 text-3xl font-bold text-[#0B6B63]">Active</p>
          <p className="mt-1 text-xs text-slate-500">
            Risk analysis engine ready
          </p>
        </div>
      </section>

      {/* Search */}
      <section>
        <label htmlFor="project-search" className="sr-only">
          Search projects
        </label>
        <div className="flex items-center gap-3 rounded-xl border border-[#9ED4C8] bg-white px-4 py-3">
          <Search className="h-4 w-4 shrink-0 text-slate-400" />
          <input
            id="project-search"
            type="search"
            value={searchTerm}
            onChange={(event) => setSearchTerm(event.target.value)}
            placeholder="Search by project name, description, or repository URL..."
            className="w-full bg-transparent text-sm text-slate-800 outline-none placeholder:text-slate-400 focus:ring-0"
          />
          {searchTerm && (
            <button
              type="button"
              onClick={() => setSearchTerm('')}
              className="shrink-0 text-xs font-medium text-[#0B6B63] hover:underline"
            >
              Clear
            </button>
          )}
        </div>
        {searchTerm && (
          <p className="mt-2 text-xs text-slate-500">
            {filteredProjects.length} of {projects.length} projects found
          </p>
        )}
      </section>

      {/* Projects table or empty state */}
      <section className="overflow-hidden rounded-xl border border-[#9ED4C8] bg-white">
        <div className="flex flex-col gap-1 border-b border-[#9ED4C8] px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-base font-semibold text-slate-900">
              Your Projects
            </h2>
            <p className="mt-1 text-xs text-slate-500">
              Select a project to view its health and risk analysis.
            </p>
          </div>
          <span className="text-xs font-medium text-slate-500">
            {filteredProjects.length} {filteredProjects.length === 1 ? 'project' : 'projects'}
          </span>
        </div>

        {filteredProjects.length === 0 ? (
          <div className="flex flex-col items-center px-5 py-14 text-center">
            <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-[#CDEFE6] text-[#0B6B63]">
              <Layers className="h-6 w-6" />
            </div>

            <h3 className="text-base font-semibold text-slate-900">
              {projects.length === 0
                ? 'No Projects Found'
                : 'No Matching Projects'}
            </h3>

            <p className="mt-2 max-w-sm text-sm text-slate-500">
              {projects.length === 0
                ? 'Create your first project and connect a GitHub repository to get started.'
                : 'No projects match your search. Try another name or repository URL.'}
            </p>

            {projects.length === 0 && (
              <button
                type="button"
                onClick={() => onNavigate('create-project')}
                className="mt-5 inline-flex items-center gap-2 rounded-lg bg-[#0B6B63] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#084F49] focus:outline-none focus:ring-2 focus:ring-teal-700 focus:ring-offset-2"
              >
                <Plus className="h-4 w-4" />
                Create Your First Project
              </button>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] border-collapse text-left">
              <thead>
                <tr className="border-b border-[#9ED4C8] bg-[#EAF8F3] text-xs font-semibold uppercase tracking-wider text-slate-500">
                  <th scope="col" className="px-5 py-4">
                    Project
                  </th>
                  <th scope="col" className="px-5 py-4">
                    GitHub Repository
                  </th>
                  <th scope="col" className="px-5 py-4">
                    Default Branch
                  </th>
                  <th scope="col" className="px-5 py-4">
                    Created
                  </th>
                  <th scope="col" className="px-5 py-4 text-right">
                    Action
                  </th>
                </tr>
              </thead>

              <tbody className="divide-y divide-[#9ED4C8]">
                {filteredProjects.map((project) => (
                  <tr
                    key={project.id}
                    onClick={() => openProject(project.id)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault();
                        openProject(project.id);
                      }
                    }}
                    tabIndex={0}
                    role="button"
                    aria-label={`Open ${project.name} project overview`}
                    className="cursor-pointer text-sm hover:bg-[#EAF8F3] focus:outline-none focus:ring-2 focus:ring-inset focus:ring-teal-700"
                  >
                    <td className="px-5 py-4">
                      <p className="font-semibold text-slate-900">
                        {project.name}
                      </p>
                      {project.description && (
                        <p className="mt-1 line-clamp-1 max-w-xs text-xs text-slate-500">
                          {project.description}
                        </p>
                      )}
                    </td>

                    <td className="px-5 py-4">
                      {project.repo_url ? (
                        <div className="flex max-w-xs items-center gap-2 text-xs text-slate-700">
                          <GitBranch className="h-4 w-4 shrink-0 text-[#0B6B63]" />
                          <span className="truncate font-mono">
                            {project.repo_url.replace(
                              /^https:\/\/github\.com\//,
                              ''
                            )}
                          </span>
                        </div>
                      ) : (
                        <span className="inline-flex rounded-md border border-amber-200 bg-amber-50 px-2 py-1 text-xs font-medium text-[#B45309]">
                          Not connected
                        </span>
                      )}
                    </td>

                    <td className="px-5 py-4">
                      <span className="inline-flex rounded-md border border-[#9ED4C8] bg-[#EAF8F3] px-2 py-1 font-mono text-xs text-slate-700">
                        {project.default_branch || 'main'}
                      </span>
                    </td>

                    <td className="whitespace-nowrap px-5 py-4 text-xs text-slate-600">
                      {project.createdAt
                        ? new Date(project.createdAt).toLocaleDateString()
                        : 'Recent'}
                    </td>

                    <td className="px-5 py-4 text-right">
                      <button
                        type="button"
                        onClick={(event) => {
                          event.stopPropagation();
                          openProject(project.id);
                        }}
                        className="inline-flex items-center justify-end gap-1 whitespace-nowrap text-xs font-semibold text-[#0B6B63] hover:underline focus:outline-none focus:ring-2 focus:ring-teal-700 focus:ring-offset-2"
                      >
                        Open Overview
                        <ArrowRight className="h-3.5 w-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
};
