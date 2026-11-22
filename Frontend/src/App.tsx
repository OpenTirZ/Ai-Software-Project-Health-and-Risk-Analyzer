import { useState, useEffect, useCallback } from 'react';
import type { PageView, Repository, UserProfileData } from './types';
import { projectApi, authApi, dataSyncApi, type ProjectResponse, type User } from './services/api';
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
import { AdminPanel } from './pages/AdminPanel';

export function App() {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(() => {
    return Boolean(localStorage.getItem('aegis_token') || localStorage.getItem('aegis_auth'));
  });
  const [currentView, setCurrentView] = useState<PageView>(() => {
    return localStorage.getItem('aegis_token') ? 'projects' : 'login';
  });

  const [projects, setProjects] = useState<ProjectResponse[]>([]);
  const [activeProject, setActiveProject] = useState<ProjectResponse | null>(null);
  const [loadingProjects, setLoadingProjects] = useState<boolean>(false);
  const [isGlobalSyncing, setIsGlobalSyncing] = useState<boolean>(false);

  const [loginPrefillEmail, setLoginPrefillEmail] = useState<string>('');
  const [loginSuccessMessage, setLoginSuccessMessage] = useState<string | null>(null);

  const [currentUser, setCurrentUser] = useState<UserProfileData>(() => {
    const saved = localStorage.getItem('aegis_user');
    if (saved) {
      try {
        // Only the authenticated API response can grant an admin role.
        return { ...JSON.parse(saved), role: 'developer' };
      } catch {
      }
    }
    return {
      fullName: 'Developer',
      username: '@developer',
      email: 'dev@aegis-health.io',
      role: 'developer',
      team: 'Core Platform Engineering',
      bio: 'Leading backend architecture, metrics analysis, and AI telemetry guardrails.',
    };
  });

  const loadProjects = useCallback(async () => {
    if (!localStorage.getItem('aegis_token')) return;
    setLoadingProjects(true);
    try {
      const list = await projectApi.getProjects();
      setProjects(list);
      setActiveProject((prev) => {
        if (!prev && list.length > 0) return list[0];
        if (prev) {
          const match = list.find((p) => p.id === prev.id);
          return match || (list.length > 0 ? list[0] : null);
        }
        return list.length > 0 ? list[0] : null;
      });
    } catch (err) {
      console.warn('Could not load projects from API:', err);
    } finally {
      setLoadingProjects(false);
    }
  }, []);

  useEffect(() => {
    const token = localStorage.getItem('aegis_token');
    if (token) {
      authApi
        .getMe()
        .then((user) => {
          if (user) {
            if (localStorage.getItem('aegis_token') !== token) return;
            setIsAuthenticated(true);
            const cleanUsername = user.username?.startsWith('@') ? user.username : `@${user.username || user.email.split('@')[0]}`;
            const updated: UserProfileData = {
              ...currentUser,
              fullName: user.name || 'Developer',
              username: cleanUsername,
              email: user.email,
              role: user.role || 'developer',
            };
            setCurrentUser(updated);
            localStorage.setItem('aegis_user', JSON.stringify(updated));
            loadProjects();
          } else {
            localStorage.removeItem('aegis_token');
            localStorage.removeItem('aegis_auth');
            localStorage.removeItem('aegis_user');
            setIsAuthenticated(false);
            setCurrentView('login');
          }
        })
        .catch(() => {
          localStorage.removeItem('aegis_token');
          localStorage.removeItem('aegis_auth');
          localStorage.removeItem('aegis_user');
          setIsAuthenticated(false);
          setCurrentView('login');
        });
    } else {
      setIsAuthenticated(false);
    }
  }, [loadProjects]);

  const handleSelectProject = (projectId: string) => {
    const match = projects.find((p) => p.id === projectId);
    if (match) {
      setActiveProject(match);
    }
  };

  const handleLoginSuccess = async (user: User) => {
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
      role: user.role || 'developer',
    };
    setCurrentUser(updated);
    localStorage.setItem('aegis_user', JSON.stringify(updated));

    await loadProjects();
    setCurrentView('projects');
  };

  const handleSignUpSuccess = (user: { email: string; name: string; username?: string }) => {
    setLoginPrefillEmail(user.email);
    setLoginSuccessMessage('Account created successfully! Please sign in with your password.');
    setCurrentView('login');
  };

  const handleUpdateProfile = (updated: UserProfileData) => {
    setCurrentUser(updated);
    localStorage.setItem('aegis_user', JSON.stringify(updated));
  };

  const handleProjectCreated = (newProject: ProjectResponse) => {
    setProjects([newProject, ...projects]);
    setActiveProject(newProject);
    setCurrentView('connect-repo');
  };

  const handleRepoConnected = async (_repo: Repository) => {
    await loadProjects();
    setCurrentView('overview');
  };

  const handleSyncAllActive = async () => {
    if (!activeProject?.id) return;
    setIsGlobalSyncing(true);
    try {
      await Promise.allSettled([
        dataSyncApi.syncCommits(activeProject.id, activeProject.default_branch || 'main'),
        dataSyncApi.syncPRs(activeProject.id),
        dataSyncApi.syncIssues(activeProject.id),
        dataSyncApi.syncContributors(activeProject.id),
        dataSyncApi.syncMilestones(activeProject.id),
      ]);
      await loadProjects();
    } catch (err) {
      console.warn('Global sync error:', err);
    } finally {
      setIsGlobalSyncing(false);
    }
  };

  const handleLogout = () => {
    authApi.logout();
    setIsAuthenticated(false);
    localStorage.removeItem('aegis_auth');
    localStorage.removeItem('aegis_token');
    localStorage.removeItem('aegis_user');
    setProjects([]);
    setActiveProject(null);
    setLoginSuccessMessage(null);
    setCurrentView('login');
  };

  const handleNavigate = (view: PageView) => {
    if (view === 'admin' && currentUser?.role !== 'admin') {
      alert('Access denied. Admin privileges required.');
      setCurrentView('overview');
      return;
    }
    setCurrentView(view);
  };

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

  return (
    <Layout
      currentView={currentView}
      projects={projects}
      activeProject={activeProject}
      currentUser={currentUser}
      onSelectProject={handleSelectProject}
      onNavigate={handleNavigate}
      onLogout={handleLogout}
      onSyncAll={handleSyncAllActive}
      isSyncing={isGlobalSyncing}
    >

      <div key={currentView} className="page-enter">
      {currentView === 'projects' && (
        <Projects
          projects={projects}
          onSelectProject={handleSelectProject}
          onNavigate={handleNavigate}
          onRefreshProjects={loadProjects}
        />
      )}

      {currentView === 'create-project' && (
        <CreateProject
          onProjectCreated={handleProjectCreated}
          onNavigate={handleNavigate}
        />
      )}

      {currentView === 'connect-repo' && (
        <ConnectRepository
          project={activeProject}
          onRepoConnected={handleRepoConnected}
          onNavigate={handleNavigate}
        />
      )}

      {currentView === 'overview' && (
        <ProjectOverview
          project={activeProject}
          onNavigate={handleNavigate}
          onRefreshProject={loadProjects}
        />
      )}

      {currentView === 'health-analysis' && (
        <HealthAnalysis
          project={activeProject}
          onNavigate={handleNavigate}
        />
      )}

      {currentView === 'risk-analysis' && (
        <RiskAnalysis
          project={activeProject}
          onNavigate={handleNavigate}
        />
      )}

      {currentView === 'contributors' && (
        <Contributors
          project={activeProject}
          onNavigate={handleNavigate}
        />
      )}

      {currentView === 'activity' && (
        <Activity
          project={activeProject}
          onNavigate={handleNavigate}
        />
      )}

      {currentView === 'reports' && (
        <Reports
          selectedRepo={activeProject?.name || 'Project'}
          project={activeProject}
          onNavigate={handleNavigate}
        />
      )}

      {currentView === 'profile' && (
        <UserProfile
          currentUser={currentUser}
          onUpdateProfile={handleUpdateProfile}
          onLogout={handleLogout}
          onNavigate={handleNavigate}
          projects={projects}
          loadingProjects={loadingProjects}
        />
      )}

      {currentView === 'admin' && currentUser?.role === 'admin' && (
        <AdminPanel />
      )}
      </div>
    </Layout>
  );
}

export default App;
