
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
    <div className="flex h-screen min-h-screen w-full overflow-hidden app-canvas text-[var(--color-text-primary)] font-['Inter',sans-serif]">

      {/* Application Sidebar */}
      <Sidebar
        currentView={currentView}
        currentUser={currentUser}
        onNavigate={onNavigate}
        onLogout={onLogout}
      />

      {/* Main Application Area */}
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">

        {/* Application Header */}
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

        {/* Page Content */}
        <main
          className="app-main min-h-0 flex-1 overflow-x-hidden overflow-y-auto"
        >
          {children}
        </main>
      </div>
    </div>
  );
};
