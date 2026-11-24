import React from 'react';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';
import type { PageView, Repository, UserProfileData } from '../types';

interface LayoutProps {
  currentView: PageView;
  selectedRepo: string;
  repositories?: Repository[];
  currentUser?: UserProfileData;
  onSelectRepo: (repo: string) => void;
  onNavigate: (view: PageView) => void;
  onLogout: () => void;
  children: React.ReactNode;
}

export const Layout: React.FC<LayoutProps> = ({
  currentView,
  selectedRepo,
  repositories = [],
  currentUser,
  onSelectRepo,
  onNavigate,
  onLogout,
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
          selectedRepo={selectedRepo} 
          repositories={repositories}
          currentUser={currentUser}
          onSelectRepo={onSelectRepo} 
          onNavigate={onNavigate} 
        />
        
        <main className="flex-1 overflow-y-auto bg-[#f8fafc]">
          {children}
        </main>
      </div>
    </div>
  );
};
