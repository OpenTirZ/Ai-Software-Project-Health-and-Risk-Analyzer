import React from 'react';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';
import type { PageView, UserProfileData } from '../types';
import type { ProjectResponse } from '../services/api';

interface LayoutProps {
  currentView: PageView;
  projects?: ProjectResponse[];
  activeProject?: ProjectResponse | null;
  currentUser?: UserProfileData;
  onSelectProject?: (projectId: string) => void;
  onNavigate: (view: PageView) => void;
  onLogout: () => void;
  onSyncAll?: () => void;
  isSyncing?: boolean;
  children: React.ReactNode;
}

export const Layout: React.FC<LayoutProps> = ({
  currentView,
  projects = [],
  activeProject,
  currentUser,
  onSelectProject,
  onNavigate,
  onLogout,
  onSyncAll,
  isSyncing = false,
  children,
}) => {
  return (
    <div className="flex h-screen w-full bg-[#f8fafc] text-slate-800 overflow-hidden font-['Inter',sans-serif]">
      {/* Sidebar */}
      <Sidebar
        currentView={currentView}
        currentUser={currentUser}
        onNavigate={onNavigate}
        onLogout={onLogout}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <TopBar
          currentView={currentView}
          projects={projects}
          activeProject={activeProject}
          currentUser={currentUser}
          onSelectProject={onSelectProject}
          onNavigate={onNavigate}
          onSyncAll={onSyncAll}
          isSyncing={isSyncing}
        />

        <main className="flex-1 overflow-y-auto bg-[#f8fafc]">
          {children}
        </main>
      </div>
    </div>
  );
};
