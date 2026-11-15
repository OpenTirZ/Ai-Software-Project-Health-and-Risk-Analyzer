import { useState } from 'react';
import type { PageView, Repository, UserProfileData } from './types';
import type { ProjectResponse } from './services/api';
import { initialRepositories } from './data/mockData';
import { Layout } from './components/Layout';
import { Login } from './pages/Login';
import { SignUp } from './pages/SignUp';
import { Projects } from './pages/Projects';
import { CreateProject } from './pages/CreateProject';
import { ConnectRepository } from './pages/ConnectRepository';
import { ProjectOverview } from './pages/ProjectOverview';
import { HealthAnalysis } from './pages/HealthAnalysis';
import { RiskAnalysis } from './pages/RiskAnalysis';
import { Contributors } from './pages/Contributors';
import { Activity } from './pages/Activity';
import { Reports } from './pages/Reports';
import { UserProfile } from './pages/UserProfile';

export function App() {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [currentView, setCurrentView] = useState<PageView>('login');
  const [selectedRepo, setSelectedRepo] = useState<string>('core-api-service');
  const [repositories, setRepositories] = useState<Repository[]>(initialRepositories);
  const [currentProject, setCurrentProject] = useState<ProjectResponse | null>(null);
  const [loginPrefillEmail, setLoginPrefillEmail] = useState<string>('');
  const [loginSuccessMessage, setLoginSuccessMessage] = useState<string | null>(null);

  const [currentUser, setCurrentUser] = useState<UserProfileData>(() => {
    const saved = localStorage.getItem('aegis_user');
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch {
        // fallback
      }
    }
    return {
      fullName: 'John Developer',
      username: '@johndev',
      email: 'john.dev@aegis-health.io',
      role: 'Lead Architect',
      team: 'Enterprise Core Platform',
      bio: 'Leading backend architecture, microservices refactoring, and AI CI/CD guardrail adoption across all cloud clusters.',
    };
  });

  const handleAddRepo = (newRepo: Repository) => {
    setRepositories([newRepo, ...repositories]);
    setSelectedRepo(newRepo.name);
  };

  const handleLoginSuccess = (user: { email: string; name: string; username?: string }) => {
    setLoginSuccessMessage(null);
    setIsAuthenticated(true);
    localStorage.setItem('aegis_auth', 'true');
    const cleanUsername = user.username
      ? (user.username.startsWith('@') ? user.username : `@${user.username}`)
      : `@${user.email.split('@')[0]}`;
    const updated: UserProfileData = {
      ...currentUser,
      fullName: user.name || 'Developer',
      username: cleanUsername,
      email: user.email,
    };
    setCurrentUser(updated);
    localStorage.setItem('aegis_user', JSON.stringify(updated));
    // First page after login is always All Repositories
    setCurrentView('projects');
  };

  const handleSignUpSuccess = (user: { email: string; name: string; username?: string }) => {
    // Redirect to Login page requiring password authentication (do not auto-login)
    setLoginPrefillEmail(user.email);
    setLoginSuccessMessage('Account created successfully! Please enter your password to sign in.');
    setCurrentView('login');
  };

  const handleUpdateProfile = (updated: UserProfileData) => {
    setCurrentUser(updated);
    localStorage.setItem('aegis_user', JSON.stringify(updated));
  };

  const handleProjectCreated = (project: ProjectResponse) => {
    setCurrentProject(project);
    // Sprint 1 Flow: Create Project -> Connect GitHub Repository
    setCurrentView('connect-repo');
  };

  const handleRepoConnected = (repo: Repository) => {
    handleAddRepo(repo);
    // Completing Flow: Takes user to Project Overview
    setCurrentView('overview');
  };

  const handleLogout = () => {
    setIsAuthenticated(false);
    localStorage.removeItem('aegis_auth');
    localStorage.removeItem('aegis_token');
    localStorage.removeItem('aegis_user');
    setLoginSuccessMessage(null);
    setCurrentView('login');
  };

  // Full-screen auth views: Entry point is always Login / SignUp until authenticated
  if (!isAuthenticated || currentView === 'login' || currentView === 'signup') {
    if (currentView === 'signup') {
      return (
        <SignUp
          onNavigate={(view) => {
            setLoginSuccessMessage(null);
            setCurrentView(view);
          }}
          onSignUpSuccess={handleSignUpSuccess}
        />
      );
    }
    return (
      <Login
        onNavigate={(view) => {
          setLoginSuccessMessage(null);
          setCurrentView(view);
        }}
        onLoginSuccess={handleLoginSuccess}
        initialEmail={loginPrefillEmail}
        successMessage={loginSuccessMessage || undefined}
      />
    );
  }

  // Dashboard views wrapped in shared Layout (Sidebar & TopBar)
  return (
    <Layout
      currentView={currentView}
      selectedRepo={selectedRepo}
      currentUser={currentUser}
      onSelectRepo={setSelectedRepo}
      onNavigate={setCurrentView}
      onLogout={handleLogout}
    >
      {currentView === 'projects' && (
        <Projects
          repositories={repositories}
          onSelectRepo={setSelectedRepo}
          onNavigate={setCurrentView}
        />
      )}

      {currentView === 'create-project' && (
        <CreateProject
          onProjectCreated={handleProjectCreated}
          onNavigate={setCurrentView}
        />
      )}

      {currentView === 'connect-repo' && (
        <ConnectRepository
          project={currentProject}
          onRepoConnected={handleRepoConnected}
          onNavigate={setCurrentView}
        />
      )}

      {currentView === 'overview' && (
        <ProjectOverview
          selectedRepo={selectedRepo}
          onNavigate={setCurrentView}
        />
      )}

      {currentView === 'health-analysis' && (
        <HealthAnalysis
          selectedRepo={selectedRepo}
          onNavigate={setCurrentView}
        />
      )}

      {currentView === 'risk-analysis' && (
        <RiskAnalysis
          selectedRepo={selectedRepo}
          onNavigate={setCurrentView}
        />
      )}

      {currentView === 'contributors' && (
        <Contributors
          selectedRepo={selectedRepo}
          onNavigate={setCurrentView}
        />
      )}

      {currentView === 'activity' && (
        <Activity
          selectedRepo={selectedRepo}
          onNavigate={setCurrentView}
        />
      )}

      {currentView === 'reports' && (
        <Reports
          selectedRepo={selectedRepo}
          onNavigate={setCurrentView}
        />
      )}

      {currentView === 'profile' && (
        <UserProfile
          currentUser={currentUser}
          onUpdateProfile={handleUpdateProfile}
          onLogout={handleLogout}
          onNavigate={setCurrentView}
        />
      )}
    </Layout>
  );
}

export default App;
