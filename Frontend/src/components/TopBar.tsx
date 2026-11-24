import React from 'react';
import type { PageView, Repository, UserProfileData } from '../types';
import { ChevronRight, Bell, GitBranch, Plus } from 'lucide-react';

interface TopBarProps {
  currentView: PageView;
  selectedRepo: string;
  repositories?: Repository[];
  currentUser?: UserProfileData;
  onSelectRepo: (repo: string) => void;
  onNavigate: (view: PageView) => void;
}

export const TopBar: React.FC<TopBarProps> = ({
  currentView,
  selectedRepo,
  repositories = [],
  currentUser,
  onSelectRepo,
  onNavigate,
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
      case 'dashboard':
        return 'Health Dashboard';
      case 'risk-analysis':
        return 'Risk Analysis & Vulnerability';
      case 'contributors':
        return 'Contributors';
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

  return (
    <header className="h-[68px] bg-[#0c1022] border-b border-slate-800/80 px-6 flex items-center justify-between text-slate-300 shrink-0">
      {/* Breadcrumb path */}
      <div className="flex items-center gap-2 text-[13px]">
        <button 
          onClick={() => onNavigate('projects')}
          className="text-slate-400 hover:text-slate-200 transition-colors font-medium cursor-pointer"
        >
          Repositories
        </button>
        <ChevronRight className="w-3.5 h-3.5 text-slate-600" />
        
        {currentView !== 'projects' && currentView !== 'profile' && currentView !== 'create-project' && currentView !== 'connect-repo' && selectedRepo && (
          <>
            <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-slate-800/50 border border-slate-700/50 text-slate-300 text-xs font-mono">
              <GitBranch className="w-3 h-3 text-indigo-400" />
              <span>{selectedRepo}</span>
            </div>
            <ChevronRight className="w-3.5 h-3.5 text-slate-600" />
          </>
        )}

        {currentView === 'profile' && (
          <>
            <span className="text-slate-400">Settings</span>
            <ChevronRight className="w-3.5 h-3.5 text-slate-600" />
          </>
        )}

        <span className="text-white font-semibold text-[14px]">
          {getBreadcrumbTitle()}
        </span>
      </div>

      {/* Right controls */}
      <div className="flex items-center gap-3">
        {/* Dynamic Repository selector */}
        {currentView !== 'projects' && currentView !== 'profile' && currentView !== 'create-project' && currentView !== 'connect-repo' && (
          repositories.length > 0 ? (
            <select
              value={selectedRepo}
              onChange={(e) => {
                onSelectRepo(e.target.value);
                onNavigate('overview');
              }}
              className="bg-slate-900 border border-slate-700 text-xs text-slate-300 rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-indigo-500 cursor-pointer"
            >
              {repositories.map((r) => (
                <option key={r.id} value={r.name}>
                  {r.name} ({r.branch})
                </option>
              ))}
            </select>
          ) : (
            <button
              onClick={() => onNavigate('create-project')}
              className="inline-flex items-center gap-1 text-xs text-indigo-300 hover:text-white font-medium px-2.5 py-1 rounded bg-indigo-950/60 border border-indigo-700/60 transition-colors cursor-pointer"
            >
              <Plus className="w-3 h-3" />
              <span>Connect Repo</span>
            </button>
          )
        )}

        <button 
          onClick={() => onNavigate('profile')}
          className="p-2 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800/60 transition-colors relative cursor-pointer"
          title="Notifications"
        >
          <Bell className="w-4 h-4" />
          <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-indigo-500 ring-2 ring-[#0c1022]"></span>
        </button>

        <button
          onClick={() => onNavigate('profile')}
          className="w-8 h-8 rounded-full bg-gradient-to-tr from-indigo-500 to-purple-600 text-white font-bold text-xs flex items-center justify-center hover:ring-2 hover:ring-indigo-400 transition-all cursor-pointer"
          title={`View profile (${currentUser?.fullName || 'User'})`}
        >
          {initials}
        </button>
      </div>
    </header>
  );
};
