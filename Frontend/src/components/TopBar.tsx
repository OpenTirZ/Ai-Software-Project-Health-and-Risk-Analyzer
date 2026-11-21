import React from 'react';
import type { PageView, UserProfileData } from '../types';
import type { ProjectResponse } from '../services/api';
import { ChevronRight, Bell, GitBranch, RefreshCw, Plus } from 'lucide-react';

interface TopBarProps {
  currentView: PageView;
  projects?: ProjectResponse[];
  activeProject?: ProjectResponse | null;
  currentUser?: UserProfileData;
  onSelectProject?: (projectId: string) => void;
  onNavigate: (view: PageView) => void;
  onSyncAll?: () => void;
  isSyncing?: boolean;
}

export const TopBar: React.FC<TopBarProps> = ({
  currentView,
  projects = [],
  activeProject,
  currentUser,
  onSelectProject,
  onNavigate,
  onSyncAll,
  isSyncing = false,
}) => {
  const getBreadcrumbTitle = () => {
    switch (currentView) {
      case 'projects':
        return 'All Repositories';
      case 'create-project':
        return 'Create New Project';
      case 'connect-repo':
        return 'Connect Repository';
      case 'overview':
        return 'Project Overview';
      case 'health-analysis':
        return 'Health Analysis';
      case 'risk-analysis':
        return 'Risk and Vulnerabilities';
      case 'contributors':
        return 'Team and Contributors';
      case 'activity':
        return 'Project Activity';
      case 'reports':
        return 'Reports';
      case 'profile':
        return 'User Profile';
      default:
        return 'Dashboard';
    }
  };

  const initials = currentUser?.fullName
    ? currentUser.fullName
        .trim()
        .split(/\s+/)
        .map((part) => part[0])
        .slice(0, 2)
        .join('')
        .toUpperCase()
    : 'U';

  const isProjectSpecificView =
    currentView !== 'projects' &&
    currentView !== 'profile' &&
    currentView !== 'create-project' &&
    currentView !== 'connect-repo';

  return (
    <header className="h-[68px] bg-[#0c1022] border-b border-slate-800/80 px-6 flex items-center justify-between text-slate-300 shrink-0">
      {/* Breadcrumb path */}
      <div className="flex items-center gap-2 text-[13px] min-w-0">
        <button
          onClick={() => onNavigate('projects')}
          className="text-slate-400 hover:text-slate-200 transition-colors font-medium cursor-pointer shrink-0"
        >
          Projects
        </button>
        <ChevronRight className="w-3.5 h-3.5 text-slate-600 shrink-0" />

        {isProjectSpecificView && activeProject && (
          <>
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-slate-800/60 border border-slate-700/60 text-slate-300 text-xs font-mono truncate max-w-[220px]">
              <GitBranch className="w-3 h-3 text-indigo-400 shrink-0" />
              <span className="truncate">{activeProject.name}</span>
              <span className="text-slate-500 text-[10px]">({activeProject.default_branch || 'main'})</span>
            </div>
            <ChevronRight className="w-3.5 h-3.5 text-slate-600 shrink-0" />
          </>
        )}

        {currentView === 'profile' && (
          <>
            <span className="text-slate-400">Settings</span>
            <ChevronRight className="w-3.5 h-3.5 text-slate-600" />
          </>
        )}

        <span className="text-white font-semibold text-[14px] truncate">
          {getBreadcrumbTitle()}
        </span>
      </div>

      {/* Right controls */}
      <div className="flex items-center gap-3 shrink-0">
        {/* Quick Sync Button */}
        {isProjectSpecificView && activeProject?.repo_url && onSyncAll && (
          <button
            onClick={onSyncAll}
            disabled={isSyncing}
            className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-indigo-300 bg-indigo-950/60 border border-indigo-700/50 rounded-lg hover:bg-indigo-900/60 hover:text-white transition-all cursor-pointer disabled:opacity-50"
            title="Fetch latest GitHub commits, PRs and issues"
            aria-label="Fetch latest GitHub commits, PRs and issues"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isSyncing ? 'animate-spin text-indigo-400' : ''}`} />
            <span>{isSyncing ? 'Syncing...' : 'Sync Telemetry'}</span>
          </button>
        )}

        {/* Dynamic Project Selector */}
        {isProjectSpecificView && (
          <div className="flex items-center gap-1.5">
            <select
              value={activeProject?.id || ''}
              onChange={(e) => onSelectProject && onSelectProject(e.target.value)}
              className="bg-slate-900 border border-slate-700 text-xs text-slate-300 rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-indigo-500 cursor-pointer max-w-[200px]"
            >
              {projects.length === 0 ? (
                <option value="">No projects found</option>
              ) : (
                projects.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))
              )}
            </select>

            <button
              onClick={() => onNavigate('create-project')}
              className="p-1.5 text-slate-400 hover:text-white bg-slate-900 border border-slate-700 rounded-lg hover:border-slate-600 transition-colors cursor-pointer"
              title="Create new project"
              aria-label="Create new project"
            >
              <Plus className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        <button
          onClick={() => onNavigate('profile')}
          className="p-2 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800/60 transition-colors relative cursor-pointer"
          title="Notifications"
          aria-label="Notifications"
        >
          <Bell className="w-4 h-4" />
          <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-indigo-500 ring-2 ring-[#0c1022]"></span>
        </button>

        <button
          onClick={() => onNavigate('profile')}
          className="w-8 h-8 rounded-full bg-gradient-to-tr from-indigo-500 to-purple-600 text-white font-bold text-xs flex items-center justify-center hover:ring-2 hover:ring-indigo-400 transition-all cursor-pointer"
          title={`View profile (${currentUser?.fullName || 'User'})`}
          aria-label={`View profile for ${currentUser?.fullName || 'User'}`}
        >
          {initials}
        </button>
      </div>
    </header>
  );
};
