import React, { useState, useEffect } from 'react';
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
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  const handleNavigate = (view: PageView) => {
    setIsMenuOpen(false);
    onNavigate(view);
  };

  useEffect(() => {
    if (!isMenuOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setIsMenuOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isMenuOpen]);

  useEffect(() => {
    if (!isMenuOpen) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [isMenuOpen]);

  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth >= 768 && isMenuOpen) {
        setIsMenuOpen(false);
      }
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [isMenuOpen]);

  return (
    <div className="flex h-screen min-h-screen w-full overflow-hidden app-canvas text-[var(--color-text-primary)] font-sans">
      <Sidebar
        currentView={currentView}
        currentUser={currentUser}
        onNavigate={handleNavigate}
        onLogout={onLogout}
        isOpen={isMenuOpen}
        onClose={() => setIsMenuOpen(false)}
      />

      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <TopBar
          currentView={currentView}
          projects={projects}
          activeProject={activeProject}
          currentUser={currentUser}
          onSelectProject={onSelectProject}
          onNavigate={handleNavigate}
          onSyncAll={onSyncAll}
          isSyncing={isSyncing}
          onOpenMenu={() => setIsMenuOpen(true)}
          isMenuOpen={isMenuOpen}
        />

        <main
          className="app-main min-h-0 flex-1 overflow-x-hidden overflow-y-auto"
        >
          {children}
        </main>
      </div>
    </div>
  );
};
