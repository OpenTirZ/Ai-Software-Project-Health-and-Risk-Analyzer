import React from 'react';
import type { PageView, UserProfileData } from '../types';
import {
  FolderGit2,
  LayoutDashboard,
  HeartPulse,
  ShieldAlert,
  Users,
  Activity as ActivityIcon,
  FileText,
  LogOut,
  ShieldCheck,
  Settings2,
} from 'lucide-react';

interface SidebarProps {
  currentView: PageView;
  currentUser?: UserProfileData;
  onNavigate: (view: PageView) => void;
  onLogout: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentView,
  currentUser,
  onNavigate,
  onLogout,
}) => {
  const isAdmin = currentUser?.role === 'admin';

  const navItems = [
    { id: 'projects', label: 'All Repositories', icon: FolderGit2 },
    { id: 'overview', label: 'Project Overview', icon: LayoutDashboard },
    { id: 'health-analysis', label: 'Health Analysis', icon: HeartPulse },
    { id: 'risk-analysis', label: 'Risk and Vulnerability', icon: ShieldAlert },
    { id: 'contributors', label: 'Team and Contributors', icon: Users },
    { id: 'activity', label: 'Activity', icon: ActivityIcon },
    { id: 'reports', label: 'Reports', icon: FileText },
  ] as const;

  const initials = currentUser?.fullName
    ? currentUser.fullName
        .trim()
        .split(/\s+/)
        .map((part) => part[0])
        .slice(0, 2)
        .join('')
        .toUpperCase()
    : 'U';

  const displayName = currentUser?.fullName || 'Developer';
  const displayRole = currentUser?.role || 'Team Member';

  return (
    <aside className="flex min-h-screen w-[260px] shrink-0 flex-col hero-vibrant select-none text-white">

      <button
        type="button"
        onClick={() => onNavigate('overview')}
        aria-label="Go to project overview"
        className="flex w-full items-center gap-3 border-b border-white/15 px-5 py-5 text-left"
      >
        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl overflow-hidden bg-white/10 backdrop-blur-md border border-white/20 p-1 shadow-lg shadow-black/30">
          <img 
            src="/assets/kavach-logo.png" 
            alt="कVaच Logo" 
            className="w-full h-full object-contain filter drop-shadow-md"
          />
        </div>

        <div className="min-w-0">
          <h1 className="text-[20px] font-black leading-tight tracking-tight text-white flex items-center">
            <span>क</span>
            <span className="text-[#FF8A95]">Va</span>
            <span>च</span>
          </h1>
          <p className="mt-1 text-[9.5px] font-medium leading-relaxed text-[#F0FDE5]/80">
            See the Risks. Strengthen the Project.
          </p>
        </div>
      </button>

      <nav
        aria-label="Main navigation"
        className="flex-1 space-y-1 overflow-y-auto px-3 py-6"
      >
        <p className="mb-3 px-3 text-[10px] font-semibold uppercase tracking-[0.12em] text-white/55">
          Workspace
        </p>

        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = currentView === item.id;

          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onNavigate(item.id as PageView)}
              aria-current={isActive ? 'page' : undefined}
              className={`flex w-full items-center gap-3 rounded-md border-l-[3px] px-3 py-2.5 text-left text-[13px] ${
                isActive
                  ? 'border-[#FF8A95] bg-gradient-to-r from-[#C8102E] to-[#8A000F] font-semibold text-white shadow-lg shadow-black/30'
                  : 'border-transparent font-medium text-white/75 hover:translate-x-1 hover:bg-white/10 hover:text-white'
              }`}
            >
              <Icon
                className={`h-[17px] w-[17px] shrink-0 ${
                  isActive ? 'text-white' : 'text-white/70'
                }`}
                strokeWidth={1.9}
              />

              <span className="truncate">{item.label}</span>
            </button>
          );
        })}

        {isAdmin && (
          <>
            <div className="px-3 pb-1 pt-4 text-[10px] font-bold uppercase tracking-widest text-white/55">
              Administration
            </div>
            <button
              onClick={() => onNavigate('admin')}
              className={`flex w-full items-center gap-3 rounded-md border-l-[3px] px-3 py-2.5 text-left text-[13px] ${
                currentView === 'admin'
                  ? 'border-[#FF8A95] bg-gradient-to-r from-[#C8102E] to-[#8A000F] font-semibold text-white shadow-lg shadow-black/30'
                  : 'border-transparent font-medium text-white/75 hover:translate-x-1 hover:bg-white/10 hover:text-white'
              }`}
            >
              <Settings2 className="h-[17px] w-[17px] shrink-0" />
              <span className="truncate">Admin Panel</span>
            </button>
          </>
        )}
      </nav>

      <div className="border-t border-white/15 p-3">

        <button
          type="button"
          onClick={() => onNavigate('profile')}
          className="flex w-full items-center gap-3 rounded-md border border-white/15 bg-white/10 p-3 text-left hover:bg-white/15"
        >
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-[#E5344A] to-[#990011] text-xs font-bold text-white">
            {initials}
          </div>

          <div className="min-w-0 flex-1">
            <p className="truncate text-[13px] font-semibold text-white">
              {displayName}
            </p>

            <p className="mt-0.5 truncate text-[11px] text-white/65">
              {currentUser?.username || displayRole}
            </p>
          </div>
        </button>

        <button
          type="button"
          onClick={onLogout}
          className="mt-3 flex w-full items-center justify-center gap-2 rounded-md py-2 text-xs font-medium text-white/70 hover:bg-white/10 hover:text-white"
        >
          <LogOut className="h-4 w-4" />
          <span>Logout</span>
        </button>
      </div>
    </aside>
  );
};
