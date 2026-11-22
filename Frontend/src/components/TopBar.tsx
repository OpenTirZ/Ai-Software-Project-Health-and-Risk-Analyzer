import React from 'react';
import type { PageView, UserProfileData } from '../types';
import type { ProjectResponse } from '../services/api';
import {
  ChevronRight,
  Bell,
  GitBranch,
  RefreshCw,
  Plus,
  Menu,
} from 'lucide-react';

interface TopBarProps {
  currentView: PageView;
  projects?: ProjectResponse[];
  activeProject?: ProjectResponse | null;
  currentUser?: UserProfileData;
  onSelectProject?: (projectId: string) => void;
  onNavigate: (view: PageView) => void;
  onSyncAll?: () => void;
  isSyncing?: boolean;
  onOpenMenu?: () => void;
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
  onOpenMenu,
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
      case 'admin':
        return 'Admin Panel';
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
    currentView !== 'connect-repo' &&
    currentView !== 'admin';

  return (
    <header className="relative z-10 flex h-[68px] shrink-0 items-center justify-between gap-4 topbar-accent border-b border-[#9ED4C8] bg-white px-4 sm:px-6">

      <div className="flex min-w-0 items-center gap-2 text-[13px]">

        {onOpenMenu && (
          <button
            type="button"
            onClick={onOpenMenu}
            aria-label="Open navigation menu"
            className="-ml-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-slate-600 hover:bg-[#CDEFE6] hover:text-[#0B6B63] lg:hidden"
          >
            <Menu className="h-5 w-5" />
          </button>
        )}

        <button
          type="button"
          onClick={() => onNavigate('projects')}
          className="shrink-0 font-medium text-slate-500 hover:text-[#0B6B63]"
        >
          Projects
        </button>

        <ChevronRight className="h-3.5 w-3.5 shrink-0 text-slate-400" />

        {isProjectSpecificView && activeProject && (
          <>
            <div className="flex max-w-[180px] min-w-0 items-center gap-2 rounded-md border border-[#9ED4C8] bg-[#CDEFE6]/50 px-2.5 py-1.5 text-xs text-slate-700 sm:max-w-[220px]">
              <GitBranch className="h-3.5 w-3.5 shrink-0 text-[#0B6B63]" />

              <span className="truncate font-medium">
                {activeProject.name}
              </span>

              <span className="shrink-0 text-[10px] text-slate-500">
                ({activeProject.default_branch || 'main'})
              </span>
            </div>

            <ChevronRight className="h-3.5 w-3.5 shrink-0 text-slate-400" />
          </>
        )}

        {currentView === 'profile' && (
          <>
            <span className="text-slate-500">Settings</span>
            <ChevronRight className="h-3.5 w-3.5 text-slate-400" />
          </>
        )}

        <span className="truncate text-sm font-semibold text-[#0E2A2A]">
          {getBreadcrumbTitle()}
        </span>
      </div>

      <div className="flex shrink-0 items-center gap-2 sm:gap-3">

        {isProjectSpecificView && activeProject?.repo_url && onSyncAll && (
          <button
            type="button"
            onClick={onSyncAll}
            disabled={isSyncing}
            title="Fetch latest GitHub commits, PRs and issues"
            className="hidden items-center gap-2 rounded-md border border-[#0B6B63] bg-[#0B6B63] px-3 py-2 text-xs font-semibold text-white hover:bg-[#084F49] disabled:cursor-not-allowed disabled:opacity-60 sm:inline-flex"
          >
            <RefreshCw className="h-3.5 w-3.5" />

            <span>
              {isSyncing ? 'Syncing...' : 'Sync Telemetry'}
            </span>
          </button>
        )}

        {isProjectSpecificView && (
          <div className="flex items-center gap-1.5">

            <select
              aria-label="Select project"
              value={activeProject?.id || ''}
              onChange={(e) =>
                onSelectProject && onSelectProject(e.target.value)
              }
              className="max-w-[140px] cursor-pointer rounded-md border border-[#9ED4C8] bg-white px-2 py-2 text-xs text-slate-700 outline-none focus:border-[#0B6B63] sm:max-w-[200px] sm:px-3"
            >
              {projects.length === 0 ? (
                <option value="">No projects found</option>
              ) : (
                projects.map((project) => (
                  <option key={project.id} value={project.id}>
                    {project.name}
                  </option>
                ))
              )}
            </select>

            <button
              type="button"
              onClick={() => onNavigate('create-project')}
              title="Create new project"
              aria-label="Create new project"
              className="flex h-8 w-8 items-center justify-center rounded-md border border-[#9ED4C8] bg-white text-slate-600 hover:border-[#0B6B63] hover:bg-[#CDEFE6] hover:text-[#0B6B63]"
            >
              <Plus className="h-4 w-4" />
            </button>
          </div>
        )}

        <button
          type="button"
          onClick={() => onNavigate('profile')}
          title="Notifications"
          aria-label="Notifications"
          className="relative flex h-8 w-8 items-center justify-center rounded-md text-slate-500 hover:bg-[#CDEFE6] hover:text-[#0B6B63]"
        >
          <Bell className="h-[17px] w-[17px]" />

          <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-[#CC1F2E] ring-2 ring-white" />
        </button>

        <button
          type="button"
          onClick={() => onNavigate('profile')}
          title={`View profile (${currentUser?.fullName || 'User'})`}
          aria-label="View user profile"
          className="flex h-8 w-8 items-center justify-center rounded-full bg-[#0B6B63] text-xs font-bold text-white hover:bg-[#084F49]"
        >
          {initials}
        </button>
      </div>
    </header>
  );
};
