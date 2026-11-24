import { useState, useEffect } from 'react';
import type { PageView, Repository, UserProfileData } from './types';
import { repositoryApi, type ProjectResponse } from './services/api';
import { initialRepositories } from './data/mockData';
import { Layout } from './components/Layout';
import { ErrorBoundary } from './components/ErrorBoundary';
import { Login } from './pages/Login';
import { SignUp } from './pages/SignUp';
import { Projects } from './pages/Projects';
import { CreateProject } from './pages/CreateProject';
import { ConnectRepository } from './pages/ConnectRepository';
import { ProjectOverview } from './pages/ProjectOverview';
import { Dashboard } from './pages/Dashboard';
import { RiskAnalysis } from './pages/RiskAnalysis';
import { Contributors } from './pages/Contributors';
import { Activity } from './pages/Activity';
import { Reports } from './pages/Reports';
import { UserProfile } from './pages/UserProfile';

// Known demo/seed user emails that come pre-loaded with demo repository data
const SEED_USER_EMAILS = ['john.dev@aegis-health.io', 'demo@aegis.io'];

export function App() {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);

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

  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [selectedRepo, setSelectedRepo] = useState<string>('');
  const [currentView, setCurrentView] = useState<PageView>('login');

  const [currentProject, setCurrentProject] = useState<ProjectResponse | null>(null);
  const [loginPrefillEmail, setLoginPrefillEmail] = useState<string>('');
  const [loginSuccessMessage, setLoginSuccessMessage] = useState<string | null>(null);

  // Sync repositories from server whenever authenticated
  useEffect(() => {
    if (isAuthenticated && currentUser?.email) {
      const emailKey = currentUser.email.trim().toLowerCase();
      repositoryApi
        .list(emailKey)
        .then((serverRepos) => {
          if (serverRepos && serverRepos.length > 0) {
            setRepositories(serverRepos);
            setSelectedRepo((prev) => prev || serverRepos[0].name);
          } else if (SEED_USER_EMAILS.includes(emailKey)) {
            setRepositories(initialRepositories);
            setSelectedRepo((prev) => prev || 'core-api-service');
          }
        })
        .catch((err) => {
          console.warn('Could not load repositories from server:', err);
        });
    }
  }, [isAuthenticated, currentUser?.email]);

  const handleSelectRepo = (repoName: string) => {
    setSelectedRepo(repoName);
  };

  const handleAddRepo = (newRepo: Repository) => {
    setRepositories((prev) => {
      const filtered = prev.filter((r) => r.id !== newRepo.id && r.name !== newRepo.name);
      return [newRepo, ...filtered];
    });
    setSelectedRepo(newRepo.name);
  };

  const handleLoginSuccess = async (user: { email: string; name: string; username?: string }) => {
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

    const emailKey = user.email.trim().toLowerCase();
    const isDemoUser = SEED_USER_EMAILS.includes(emailKey);

    // Fetch user repositories directly from the server database
    try {
      const serverRepos = await repositoryApi.list(emailKey);
      if (serverRepos && serverRepos.length > 0) {
        setRepositories(serverRepos);
        setSelectedRepo(serverRepos[0].name);
        setCurrentView('projects');
        return;
      }
    } catch (e) {
      console.warn('Could not query user repositories from server on login:', e);
    }

    if (isDemoUser) {
      // Demo user: pre-seeded demo repositories
      setRepositories(initialRepositories);
      setSelectedRepo('core-api-service');
      setCurrentView('projects');
    } else {
      // New user without any repositories on server: clean slate, route straight to Create Project
      setRepositories([]);
      setSelectedRepo('');
      setCurrentView('create-project');
    }
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
    // Completing Flow: Takes user to Project Overview for the newly connected repo
    setCurrentView('overview');
  };

  const handleLogout = () => {
    setIsAuthenticated(false);
    setRepositories([]);
    setSelectedRepo('');
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

  const activeProjectId = (repositories.find((r) => r.name === selectedRepo) as any)?.projectId || currentProject?.id || 'proj_core_platform';

  // Dashboard views wrapped in shared Layout (Sidebar & TopBar)
  return (
    <Layout
      currentView={currentView}
      selectedRepo={selectedRepo}
      repositories={repositories}
      currentUser={currentUser}
      onSelectRepo={handleSelectRepo}
      onNavigate={setCurrentView}
      onLogout={handleLogout}
    >
      {currentView === 'projects' && (
        <Projects
          repositories={repositories}
          onSelectRepo={handleSelectRepo}
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

      {currentView === 'dashboard' && (
        <ErrorBoundary fallbackTitle="Unable to Display Project Health Dashboard">
          <Dashboard
            projectId={activeProjectId}
            selectedRepo={selectedRepo}
            onNavigate={setCurrentView}
          />
        </ErrorBoundary>
      )}

      {currentView === 'overview' && (
        <ProjectOverview
          projectId={activeProjectId}
          selectedRepo={selectedRepo}
          onNavigate={setCurrentView}
        />
      )}

      {currentView === 'risk-analysis' && (
        <RiskAnalysis
          projectId={activeProjectId}
          selectedRepo={selectedRepo}
          onNavigate={setCurrentView}
        />
      )}

      {currentView === 'contributors' && (
        <Contributors
          projectId={activeProjectId}
          selectedRepo={selectedRepo}
          onNavigate={setCurrentView}
        />
      )}

      {currentView === 'activity' && (
        <Activity
          projectId={activeProjectId}
          selectedRepo={selectedRepo}
          onNavigate={setCurrentView}
        />
      )}

      {currentView === 'reports' && (
        <Reports
          projectId={activeProjectId}
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
