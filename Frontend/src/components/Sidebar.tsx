import React from 'react';
import type { PageView, UserProfileData } from '../types';
import {
  FolderGit2,
  LayoutDashboard,
  Gauge,
  HeartPulse,
  ShieldAlert,
  Users,
  Activity as ActivityIcon,
  FileText,
  LogOut,
  Settings2,
  MessageSquareWarning,
  Settings,
  ScrollText,
  X,
} from 'lucide-react';

interface SidebarProps {
  currentView: PageView;
  currentUser?: UserProfileData;
  onNavigate: (view: PageView) => void;
  onLogout: () => void;
  isOpen?: boolean;
  onClose?: () => void;
}

interface SidebarContentProps {
  currentView: PageView;
  currentUser?: UserProfileData;
  onNavigate: (view: PageView) => void;
  onLogout: () => void;
  onClose?: () => void;
  showCloseButton?: boolean;
}

const SidebarContent: React.FC<SidebarContentProps> = ({
  currentView,
  currentUser,
  onNavigate,
  onLogout,
  onClose,
  showCloseButton = false,
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
        { id: 'dashboard', label: 'Dashboard', icon: Gauge },
        { id: 'health-analysis', label: 'Health Analysis', icon: HeartPulse },
        { id: 'risk-analysis', label: 'Risk and Vulnerability', icon: ShieldAlert },
        { id: 'contributors', label: 'Team and Contributors', icon: Users },
        { id: 'activity', label: 'Activity', icon: ActivityIcon },
        { id: 'reports', label: 'Reports', icon: FileText },
        { id: 'appeals', label: 'Appeals', icon: MessageSquareWarning },
        { id: 'project-settings', label: 'Project Settings', icon: Settings },
      ],
    },
  ] as const;

  const navItemClass = (isActive: boolean) =>
    `group relative flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-[13px] ${
      isActive
        ? 'bg-gradient-to-r from-[#C8102E] to-[#8A000F] font-semibold text-white shadow-lg shadow-black/30'
        : 'font-medium text-white/75 hover:bg-white/10 hover:text-white'
    }`;

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

  const handleItemClick = (view: PageView) => {
    onNavigate(view);
    onClose?.();
  };

  return (
    <div className="flex h-full min-h-0 flex-1 flex-col select-none">
      <div className="flex items-center justify-between border-b border-white/15 px-4 py-4 sm:px-5 sm:py-5">
        <button
          type="button"
          onClick={() => handleItemClick('overview')}
          aria-label="Go to project overview"
          className="flex min-w-0 items-center gap-3 text-left"
        >
          <div className="flex h-10 w-10 sm:h-12 sm:w-12 shrink-0 items-center justify-center rounded-xl overflow-hidden bg-white/10 backdrop-blur-md border border-white/20 p-1 shadow-lg shadow-black/30">
            <img
              src="/assets/kavach-logo.png"
              alt="कVaच Logo"
              className="w-full h-full object-contain filter drop-shadow-md"
            />
          </div>

          <div className="min-w-0">
            <h1 className="text-[18px] sm:text-[20px] font-black leading-tight tracking-tight text-white flex items-center">
              <span>क</span>
              <span className="text-[#FF8A95]">Va</span>
              <span>च</span>
            </h1>
            <p className="mt-0.5 sm:mt-1 text-[9px] sm:text-[9.5px] font-medium leading-relaxed text-[#F0FDE5]/80 truncate">
              See the Risks. Strengthen the Project.
            </p>
          </div>
        </button>

        {showCloseButton && onClose && (
          <button
            type="button"
            onClick={onClose}
            aria-label="Close navigation menu"
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-white/80 hover:bg-white/10 hover:text-white md:hidden"
          >
            <X className="h-5 w-5" />
          </button>
        )}
      </div>

      <nav
        aria-label="Main navigation"
        className="flex-1 space-y-6 overflow-y-auto px-3 py-4 sm:py-6"
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
                  onClick={() => handleItemClick(item.id as PageView)}
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
              onClick={() => handleItemClick('admin')}
              aria-current={currentView === 'admin' ? 'page' : undefined}
              className={navItemClass(currentView === 'admin')}
            >
              <Settings2 className="h-[17px] w-[17px] shrink-0" />
              <span className="truncate">Admin Panel</span>
            </button>
            <button
              type="button"
              onClick={() => handleItemClick('audit-logs' as PageView)}
              aria-current={currentView === ('audit-logs' as PageView) ? 'page' : undefined}
              className={navItemClass(currentView === ('audit-logs' as PageView))}
            >
              <ScrollText className="h-[17px] w-[17px] shrink-0" />
              <span className="truncate">Audit Logs</span>
            </button>
          </div>
        )}
      </nav>

      <div className="border-t border-white/15 p-3">
        <button
          type="button"
          onClick={() => handleItemClick('profile')}
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
          onClick={() => {
            onLogout();
            onClose?.();
          }}
          className="mt-3 flex w-full items-center justify-center gap-2 rounded-md py-2 text-xs font-medium text-white/70 hover:bg-white/10 hover:text-white"
        >
          <LogOut className="h-4 w-4" />
          <span>Logout</span>
        </button>
      </div>
    </div>
  );
};

export const Sidebar: React.FC<SidebarProps> = ({
  currentView,
  currentUser,
  onNavigate,
  onLogout,
  isOpen = false,
  onClose,
}) => {
  return (
    <>
      {/* Desktop sidebar */}
      <aside className="hidden md:flex md:w-[260px] md:shrink-0 md:flex-col hero-vibrant select-none text-white min-h-screen">
        <SidebarContent
          currentView={currentView}
          currentUser={currentUser}
          onNavigate={onNavigate}
          onLogout={onLogout}
        />
      </aside>

      {/* Mobile drawer */}
      {isOpen && (
        <div className="md:hidden">
          <button
            type="button"
            aria-label="Close navigation menu"
            onClick={onClose}
            className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm md:hidden cursor-default"
          />
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Navigation drawer"
            className="fixed inset-y-0 left-0 z-50 flex w-[260px] flex-col hero-vibrant text-white shadow-2xl transition-transform duration-300 md:hidden"
          >
            <SidebarContent
              currentView={currentView}
              currentUser={currentUser}
              onNavigate={onNavigate}
              onLogout={onLogout}
              onClose={onClose}
              showCloseButton
            />
          </div>
        </div>
      )}
    </>
  );
};
