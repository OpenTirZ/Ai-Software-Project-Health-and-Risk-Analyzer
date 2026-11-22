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
  Settings2,
} from 'lucide-react';

interface SidebarProps {
  currentView: PageView;
  currentUser?: UserProfileData;
  onNavigate: (view: PageView) => void;
  onLogout: () => void;
  isOpen?: boolean;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentView,
  currentUser,
  onNavigate,
  onLogout,
  isOpen = false,
}) => {
  const isAdmin = currentUser?.role === 'admin';

  const navGroups = [
    {
      label: 'Portfolio',
      items: [{ id: 'projects', label: 'All Repositories', icon: FolderGit2 }],
    },
    {
      label: 'Active project',
      items: [
        { id: 'overview', label: 'Project Overview', icon: LayoutDashboard },
        { id: 'health-analysis', label: 'Health Analysis', icon: HeartPulse },
        { id: 'risk-analysis', label: 'Risk and Vulnerability', icon: ShieldAlert },
        { id: 'contributors', label: 'Team and Contributors', icon: Users },
        { id: 'activity', label: 'Activity', icon: ActivityIcon },
        { id: 'reports', label: 'Reports', icon: FileText },
      ],
    },
  ] as const;

  const navItemClass = (isActive: boolean) =>
    `group relative flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-[13px] ${
      isActive
        ? 'bg-gradient-to-r from-[#C8102E] to-[#8A000F] font-semibold text-white shadow-lg shadow-black/30'
        : 'font-medium text-white/75 hover:bg-white/10 hover:text-white'
    }`

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
    <aside
      className={`fixed inset-y-0 left-0 z-40 flex min-h-screen w-[260px] shrink-0 flex-col hero-vibrant select-none text-white transition-transform duration-200 lg:static lg:translate-x-0 ${
        isOpen ? 'translate-x-0' : '-translate-x-full'
      }`}
    >

      <button
        type="button"
        onClick={() => onNavigate('overview')}
        aria-label="Go to project overview"
        className="flex w-full items-center gap-3 border-b border-white/15 px-5 py-5 text-left"
      >
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl overflow-hidden bg-white/10 backdrop-blur-md border border-white/20 p-1 shadow-lg shadow-black/30">
          <img 
            src="/assets/kavach-logo.png" 
            alt="कVaच Logo" 
            className="w-full h-full object-contain"
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
        className="flex-1 space-y-6 overflow-y-auto px-3 py-6"
      >
        {navGroups.map((group) => (
          <div key={group.label} className="space-y-1">
            <p className="mb-2 px-3 text-[11px] font-semibold tracking-wide text-white/55">
              {group.label}
            </p>

            {group.items.map((item) => {
              const Icon = item.icon;
              const isActive = currentView === item.id;

              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => onNavigate(item.id as PageView)}
                  aria-current={isActive ? 'page' : undefined}
                  className={navItemClass(isActive)}
                >
                  <Icon
                    className={`h-[17px] w-[17px] shrink-0 ${
                      isActive ? 'text-white' : 'text-white/70 group-hover:text-white'
                    }`}
                    strokeWidth={1.9}
                  />

                  <span className="truncate">{item.label}</span>
                </button>
              );
            })}
          </div>
        ))}

        {isAdmin && (
          <div className="space-y-1">
            <p className="mb-2 px-3 text-[11px] font-semibold tracking-wide text-white/55">
              Administration
            </p>
            <button
              type="button"
              onClick={() => onNavigate('admin')}
              aria-current={currentView === 'admin' ? 'page' : undefined}
              className={navItemClass(currentView === 'admin')}
            >
              <Settings2 className="h-[17px] w-[17px] shrink-0" />
              <span className="truncate">Admin Panel</span>
            </button>
          </div>
        )}
      </nav>

      <div className="border-t border-white/15 p-3">

        <button
          type="button"
          onClick={() => onNavigate('profile')}
          className="flex w-full items-center gap-3 rounded-xl border border-white/15 bg-white/10 p-3 text-left hover:bg-white/15"
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
