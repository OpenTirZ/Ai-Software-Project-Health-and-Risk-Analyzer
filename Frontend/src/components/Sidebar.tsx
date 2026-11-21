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

export const Sidebar: React.FC<SidebarProps> = ({ currentView, currentUser, onNavigate, onLogout }) => {
  const isAdmin = currentUser?.role === 'admin';

  const navItems = [
    { id: 'projects',       label: 'All Repositories',       icon: FolderGit2 },
    { id: 'overview',       label: 'Project Overview',        icon: LayoutDashboard },
    { id: 'health-analysis',label: 'Health Analysis',         icon: HeartPulse },
    { id: 'risk-analysis',  label: 'Risk and Vulnerability',  icon: ShieldAlert },
    { id: 'contributors',   label: 'Team and Contributors',   icon: Users },
    { id: 'activity',       label: 'Activity',                icon: ActivityIcon },
    { id: 'reports',        label: 'Reports',                 icon: FileText },
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
    <aside className="w-[260px] bg-[#0c1022] text-slate-300 flex flex-col shrink-0 min-h-screen border-r border-[#1e293b]/70 select-none">
      {/* Brand Header */}
      <div 
        onClick={() => onNavigate('overview')}
        className="px-5 py-5 border-b border-slate-800/80 cursor-pointer hover:opacity-95 transition-opacity"
      >
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-indigo-500 via-indigo-600 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-500/30">
            <ShieldCheck className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-[17px] font-bold text-white tracking-tight leading-tight">
              Aegis AI
            </h1>
            <p className="text-[10px] text-slate-400 font-medium tracking-tight">
              AI Software Project Health &amp; Risk Analyzer
            </p>
          </div>
        </div>
      </div>

      {/* Navigation Menu */}
      <nav className="flex-1 px-3 py-6 space-y-1.5 overflow-y-auto">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = currentView === item.id;
          
          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id as PageView)}
              className={`w-full text-left px-3.5 py-2.5 rounded-[10px] text-[14px] font-medium transition-all duration-200 flex items-center gap-3 ${
                isActive
                  ? 'text-white shadow-md shadow-indigo-600/30 relative overflow-hidden font-semibold'
                  : 'text-slate-300 hover:text-white hover:bg-slate-800/60'
              }`}
              style={
                isActive
                  ? {
                      background: 'linear-gradient(90deg, rgba(0, 0, 0, 0.2) 0%, rgba(0, 0, 0, 0.2) 100%), linear-gradient(90deg, rgb(99, 102, 241) 0%, rgb(168, 85, 247) 100%)',
                    }
                  : undefined
              }
            >
              <Icon className={`w-4 h-4 shrink-0 ${isActive ? 'text-white' : 'text-slate-400'}`} />
              <span className="truncate">{item.label}</span>
            </button>
          );
        })}

        {/* Admin Panel — only visible to admins */}
        {isAdmin && (
          <>
            <div className="pt-3 pb-1 px-1">
              <p className="text-[10px] font-bold uppercase tracking-widest text-slate-600">
                Administration
              </p>
            </div>
            <button
              onClick={() => onNavigate('admin')}
              className={`w-full text-left px-3.5 py-2.5 rounded-[10px] text-[14px] font-medium transition-all duration-200 flex items-center gap-3 ${
                currentView === 'admin'
                  ? 'text-white shadow-md shadow-purple-600/30 relative overflow-hidden font-semibold'
                  : 'text-slate-300 hover:text-white hover:bg-slate-800/60'
              }`}
              style={
                currentView === 'admin'
                  ? {
                      background: 'linear-gradient(90deg, rgba(0,0,0,0.2), rgba(0,0,0,0.2)), linear-gradient(90deg, rgb(147,51,234), rgb(99,102,241))',
                    }
                  : undefined
              }
            >
              <Settings2 className={`w-4 h-4 shrink-0 ${currentView === 'admin' ? 'text-white' : 'text-slate-400'}`} />
              <span className="truncate">Admin Panel</span>
            </button>
          </>
        )}
      </nav>

      {/* User Footer Profile */}
      <div className="p-3 border-t border-slate-800/80 bg-[#090d1c]">
        <button
          onClick={() => onNavigate('profile')}
          className="w-full flex items-center gap-3 p-2.5 rounded-xl bg-slate-900/80 hover:bg-slate-800/80 border border-slate-800 transition-colors text-left cursor-pointer"
        >
          <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-indigo-500 to-purple-600 text-white font-bold text-xs flex items-center justify-center shrink-0 shadow-inner">
            {initials}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-[13px] font-semibold text-slate-100 truncate">
              {displayName}
            </p>
            <p className="text-[11px] text-slate-400 truncate">
              {currentUser?.username ? `${currentUser.username}` : displayRole}
            </p>
          </div>
        </button>

        {/* Logout */}
        <button
          onClick={onLogout}
          className="mt-2.5 w-full flex items-center justify-center gap-2 py-1.5 text-xs font-medium text-slate-400 hover:text-red-400 transition-colors cursor-pointer"
        >
          <LogOut className="w-3.5 h-3.5" />
          <span>Logout</span>
        </button>
      </div>
    </aside>
  );
};
