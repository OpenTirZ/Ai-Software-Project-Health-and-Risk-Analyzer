import { useState, useEffect, useCallback, useRef } from 'react';
import {
  BrowserRouter,
  Navigate,
  Outlet,
  Route,
  Routes,
  useLocation,
  useNavigate,
  useParams,
  useOutletContext,
} from 'react-router-dom';
import type { PageView, Repository, UserProfileData } from './types';
import { projectApi, authApi, dataSyncApi, type ProjectResponse, type User } from './services/api';
import { Layout } from './components/Layout';
import { ProtectedRoute } from './components/ProtectedRoute';
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
import { Dashboard } from './pages/Dashboard';
import { Appeals } from './pages/Appeals';
import { ProjectSettings } from './pages/ProjectSettings';
import { AuditLogs } from './pages/AuditLogs';

function getPageView(pathname: string): PageView {
  if (pathname === '/login') return 'login';
  if (pathname === '/signup') return 'signup';
  if (pathname === '/' || pathname === '/projects') return 'projects';
  if (pathname === '/projects/create') return 'create-project';
  if (pathname === '/projects/connect') return 'connect-repo';
  if (pathname.endsWith('/overview')) return 'overview';
  if (pathname.endsWith('/dashboard')) return 'dashboard';
  if (pathname.endsWith('/health')) return 'health-analysis';
  if (pathname.endsWith('/risk')) return 'risk-analysis';
  if (pathname.endsWith('/contributors')) return 'contributors';
  if (pathname.endsWith('/activity')) return 'activity';
  if (pathname.endsWith('/reports')) return 'reports';
  if (pathname.endsWith('/appeals')) return 'appeals';
  if (pathname.endsWith('/settings')) return 'project-settings';
  if (pathname === '/admin/audit-logs') return 'audit-logs';
  if (pathname === '/profile') return 'profile';
  if (pathname === '/admin') return 'admin';
  return 'projects';
}

function getProjectPath(projectId: string | undefined, view: PageView): string {
  const paths: Partial<Record<PageView, string>> = {
    overview: 'overview',
    dashboard: 'dashboard',
    'health-analysis': 'health',
    'risk-analysis': 'risk',
    contributors: 'contributors',
    activity: 'activity',
    reports: 'reports',
    appeals: 'appeals',
    'project-settings': 'settings',
  };
  const subPath = paths[view];
  return projectId && subPath ? `/projects/${encodeURIComponent(projectId)}/${subPath}` : '/projects';
}

function AuthenticatedLayout({
  projects,
  activeProject,
  currentUser,
  onSelectProject,
  onNavigate,
  onLogout,
  onSyncAll,
  isSyncing,
}: {
  projects: ProjectResponse[];
  activeProject: ProjectResponse | null;
  currentUser: UserProfileData;
  onSelectProject: (projectId: string) => void;
  onNavigate: (view: PageView) => void;
  onLogout: () => void;
  onSyncAll: () => void;
  isSyncing: boolean;
}) {
  const location = useLocation();
  const currentView = getPageView(location.pathname);

  return (
    <Layout
      currentView={currentView}
      projects={projects}
      activeProject={activeProject}
      currentUser={currentUser}
      onSelectProject={onSelectProject}
      onNavigate={onNavigate}
      onLogout={onLogout}
      onSyncAll={onSyncAll}
      isSyncing={isSyncing}
    >
      <Outlet />
    </Layout>
  );
}

function ProjectSelection({
  projects,
  activeProject,
  loadingProjects,
  onSelectProject,
}: {
  projects: ProjectResponse[];
  activeProject: ProjectResponse | null;
  loadingProjects: boolean;
  onSelectProject: (project: ProjectResponse) => void;
}) {
  const { id } = useParams();
  const project = projects.find((item) => item.id === id);

  useEffect(() => {
    if (project && project.id !== activeProject?.id) onSelectProject(project);
  }, [project, activeProject?.id, onSelectProject]);

  if (loadingProjects && !project) {
    return <div className="p-6 text-sm text-slate-500" role="status">Loading project...</div>;
  }

  if (!project) return <Navigate to="/projects" replace />;

  // Child pages receive the project resolved from the URL, not a stale prior selection.
  return <Outlet context={project} />;
}

function useRouteProject(): ProjectResponse {
  return useOutletContext<ProjectResponse>();
}

function ProjectOverviewRoute({ onNavigate, onRefreshProject }: { onNavigate: (view: PageView) => void; onRefreshProject: () => void }) {
  const project = useRouteProject();
  return <ProjectOverview project={project} onNavigate={onNavigate} onRefreshProject={onRefreshProject} />;
}

function HealthAnalysisRoute({ onNavigate }: { onNavigate: (view: PageView) => void }) {
  const project = useRouteProject();
  return <HealthAnalysis project={project} onNavigate={onNavigate} />;
}

function DashboardRoute({ onNavigate }: { onNavigate: (view: PageView) => void }) {
  const project = useRouteProject();
  return <Dashboard project={project} onNavigate={onNavigate} />;
}

function RiskAnalysisRoute({ onNavigate }: { onNavigate: (view: PageView) => void }) {
  const project = useRouteProject();
  return <RiskAnalysis project={project} onNavigate={onNavigate} />;
}

function ContributorsRoute({ onNavigate }: { onNavigate: (view: PageView) => void }) {
  const project = useRouteProject();
  return <Contributors project={project} onNavigate={onNavigate} />;
}

function ActivityRoute({ onNavigate }: { onNavigate: (view: PageView) => void }) {
  const project = useRouteProject();
  return <Activity project={project} onNavigate={onNavigate} />;
}

function ReportsRoute({ onNavigate }: { onNavigate: (view: PageView) => void }) {
  const project = useRouteProject();
  return <Reports selectedRepo={project.name || 'Project'} project={project} onNavigate={onNavigate} />;
}

function AppealsRoute({ onNavigate }: { onNavigate: (view: PageView) => void }) {
  const project = useRouteProject();
  return <Appeals project={project} onNavigate={onNavigate} />;
}

function ProjectSettingsRoute({ onNavigate, onProjectChanged }: { onNavigate: (view: PageView) => void; onProjectChanged: () => void }) {
  const project = useRouteProject();
  return <ProjectSettings project={project} onNavigate={onNavigate} onProjectChanged={onProjectChanged} />;
}

function AppRoutes() {
  const navigate = useNavigate();
  const location = useLocation();
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(Boolean(localStorage.getItem('aegis_token')));
  const [isAuthLoading, setIsAuthLoading] = useState<boolean>(Boolean(localStorage.getItem('aegis_token')));
  const [projects, setProjects] = useState<ProjectResponse[]>([]);
  const [activeProject, setActiveProject] = useState<ProjectResponse | null>(null);
  const activeProjectIdRef = useRef<string | undefined>(undefined);

  useEffect(() => {
    activeProjectIdRef.current = activeProject?.id;
  }, [activeProject?.id]);
  const [loadingProjects, setLoadingProjects] = useState<boolean>(false);
  const [isGlobalSyncing, setIsGlobalSyncing] = useState<boolean>(false);
  const [loginPrefillEmail, setLoginPrefillEmail] = useState<string>('');
  const [loginSuccessMessage, setLoginSuccessMessage] = useState<string | null>(null);

  const [currentUser, setCurrentUser] = useState<UserProfileData>(() => {
    const saved = localStorage.getItem('aegis_user');
    if (saved) {
      try {
        // Cached profile data must never grant admin privileges before session verification.
        return { ...JSON.parse(saved), role: 'developer' };
      } catch {
        // Fall through to the default profile.
      }
    }
    return {
      fullName: 'Developer',
      username: '@developer',
      email: 'dev@kavach.ai',
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
      setActiveProject((previous) => {
        return (previous && list.find((project) => project.id === previous.id)) || list[0] || null;
      });
    } catch (error) {
      console.warn('Could not load projects from API:', error);
    } finally {
      setLoadingProjects(false);
    }
  }, []);

  useEffect(() => {
    const token = localStorage.getItem('aegis_token');
    if (!token) {
      setIsAuthenticated(false);
      setIsAuthLoading(false);
      return;
    }

    setIsAuthLoading(true);
    authApi.getMe()
      .then((user) => {
        if (!user) throw new Error('Session could not be verified');
        if (localStorage.getItem('aegis_token') !== token) return;
        setIsAuthenticated(true);
        setCurrentUser((previous) => {
          const cleanUsername = user.username?.startsWith('@')
            ? user.username
            : `@${user.username || user.email.split('@')[0]}`;
          const updated: UserProfileData = {
            ...previous,
            fullName: user.name || 'Developer',
            username: cleanUsername,
            email: user.email,
            role: user.role || 'developer',
          };
          localStorage.setItem('aegis_user', JSON.stringify(updated));
          return updated;
        });
        void loadProjects();
      })
      .catch(() => {
        const currentToken = localStorage.getItem('aegis_token');
        if (!currentToken || currentToken === token) {
          localStorage.removeItem('aegis_token');
          localStorage.removeItem('aegis_auth');
          localStorage.removeItem('aegis_user');
          setIsAuthenticated(false);
        }
      })
      .finally(() => setIsAuthLoading(false));
  }, [loadProjects]);

  const handleSelectProject = useCallback((projectId: string) => {
    const selected = projects.find((project) => project.id === projectId);
    if (!selected) return;
    setActiveProject(selected);
    activeProjectIdRef.current = selected.id;
    const currentView = getPageView(location.pathname);
    if (['overview', 'dashboard', 'health-analysis', 'risk-analysis', 'contributors', 'activity', 'reports', 'appeals', 'project-settings'].includes(currentView)) {
      navigate(getProjectPath(projectId, currentView), { replace: false });
    }
  }, [projects, location.pathname, navigate]);

  const handleNavigate = useCallback((view: PageView) => {
    if (view === 'admin' && currentUser.role !== 'admin') {
      window.alert('Access denied. Admin privileges required.');
      navigate(getProjectPath(activeProjectIdRef.current, 'overview'));
      return;
    }

    const staticPaths: Partial<Record<PageView, string>> = {
      login: '/login',
      signup: '/signup',
      projects: '/projects',
      'create-project': '/projects/create',
      'connect-repo': '/projects/connect',
      profile: '/profile',
      admin: '/admin',
      'audit-logs': '/admin/audit-logs',
    };
    navigate(staticPaths[view] || getProjectPath(activeProjectIdRef.current, view));
  }, [currentUser.role, navigate]);

  const handleLoginSuccess = async (user: User) => {
    setLoginSuccessMessage(null);
    setIsAuthenticated(true);
    setIsAuthLoading(false);
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

    // If the user was redirected here from a protected deep link, return to
    // that URL after successful authentication. Normal logins still land on
    // the projects page.
    const requestedLocation = (location.state as {
      from?: { pathname?: string; search?: string; hash?: string };
    } | null)?.from;
    const requestedPath = requestedLocation?.pathname;
    const returnTo = requestedPath && requestedPath !== '/login' && requestedPath !== '/signup'
      ? `${requestedPath}${requestedLocation?.search || ''}${requestedLocation?.hash || ''}`
      : '/projects';

    navigate(returnTo, { replace: true });
  };

  const handleSignUpSuccess = (user: { email: string; name: string; username?: string }) => {
    setLoginPrefillEmail(user.email);
    setLoginSuccessMessage('Account created successfully! Please sign in with your password.');
    navigate('/login');
  };

  const handleUpdateProfile = (updated: UserProfileData) => {
    setCurrentUser(updated);
    localStorage.setItem('aegis_user', JSON.stringify(updated));
  };

  const handleProjectCreated = (newProject: ProjectResponse) => {
    setProjects((previous) => [newProject, ...previous]);
    setActiveProject(newProject);
    activeProjectIdRef.current = newProject.id;
  };

  const handleRepoConnected = async (_repo: Repository) => {
    await loadProjects();
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
    } catch (error) {
      console.warn('Global sync error:', error);
    } finally {
      setIsGlobalSyncing(false);
    }
  };

  const handleLogout = () => {
    void authApi.logout();
    setIsAuthenticated(false);
    setIsAuthLoading(false);
    localStorage.removeItem('aegis_auth');
    localStorage.removeItem('aegis_token');
    localStorage.removeItem('aegis_user');
    setProjects([]);
    setActiveProject(null);
    activeProjectIdRef.current = undefined;
    setLoginSuccessMessage(null);
    navigate('/login', { replace: true });
  };

  const onSelectProjectObject = useCallback((project: ProjectResponse) => {
    setActiveProject(project);
    activeProjectIdRef.current = project.id;
  }, []);

  return (
    <Routes>
      <Route path="/login" element={
        isAuthenticated && !isAuthLoading ? <Navigate to="/projects" replace /> : (
          <Login
            onNavigate={(view) => { setLoginSuccessMessage(null); handleNavigate(view); }}
            onLoginSuccess={handleLoginSuccess}
            initialEmail={loginPrefillEmail}
            successMessage={loginSuccessMessage || undefined}
          />
        )
      } />
      <Route path="/signup" element={
        isAuthenticated && !isAuthLoading ? <Navigate to="/projects" replace /> : (
          <SignUp onNavigate={handleNavigate} onSignUpSuccess={handleSignUpSuccess} />
        )
      } />

      <Route element={
        <ProtectedRoute isLoading={isAuthLoading} isAuthenticated={isAuthenticated}>
          <AuthenticatedLayout
            projects={projects}
            activeProject={activeProject}
            currentUser={currentUser}
            onSelectProject={handleSelectProject}
            onNavigate={handleNavigate}
            onLogout={handleLogout}
            onSyncAll={handleSyncAllActive}
            isSyncing={isGlobalSyncing}
          />
        </ProtectedRoute>
      }>
        <Route index element={<Navigate to="/projects" replace />} />
        <Route path="projects" element={
          <div className="page-enter"><Projects projects={projects} onSelectProject={handleSelectProject} onNavigate={handleNavigate} onRefreshProjects={loadProjects} /></div>
        } />
        <Route path="projects/create" element={
          <div className="page-enter"><CreateProject onProjectCreated={handleProjectCreated} onNavigate={handleNavigate} /></div>
        } />
        <Route path="projects/connect" element={
          <div className="page-enter"><ConnectRepository project={activeProject} onRepoConnected={handleRepoConnected} onNavigate={handleNavigate} /></div>
        } />
        <Route path="projects/:id" element={
          <ProjectSelection projects={projects} activeProject={activeProject} loadingProjects={loadingProjects} onSelectProject={onSelectProjectObject} />
        }>
          <Route path="overview" element={<div className="page-enter"><ProjectOverviewRoute onNavigate={handleNavigate} onRefreshProject={loadProjects} /></div>} />
          <Route path="dashboard" element={<div className="page-enter"><DashboardRoute onNavigate={handleNavigate} /></div>} />
          <Route path="health" element={<div className="page-enter"><HealthAnalysisRoute onNavigate={handleNavigate} /></div>} />
          <Route path="risk" element={<div className="page-enter"><RiskAnalysisRoute onNavigate={handleNavigate} /></div>} />
          <Route path="contributors" element={<div className="page-enter"><ContributorsRoute onNavigate={handleNavigate} /></div>} />
          <Route path="activity" element={<div className="page-enter"><ActivityRoute onNavigate={handleNavigate} /></div>} />
          <Route path="reports" element={<div className="page-enter"><ReportsRoute onNavigate={handleNavigate} /></div>} />
          <Route path="appeals" element={<div className="page-enter"><AppealsRoute onNavigate={handleNavigate} /></div>} />
          <Route path="settings" element={<div className="page-enter"><ProjectSettingsRoute onNavigate={handleNavigate} onProjectChanged={loadProjects} /></div>} />
          <Route index element={<Navigate to="overview" replace />} />
          <Route path="*" element={<Navigate to="/projects" replace />} />
        </Route>
        <Route path="profile" element={
          <div className="page-enter"><UserProfile currentUser={currentUser} onUpdateProfile={handleUpdateProfile} onLogout={handleLogout} onNavigate={handleNavigate} projects={projects} loadingProjects={loadingProjects} /></div>
        } />
        <Route path="admin" element={
          <ProtectedRoute isLoading={isAuthLoading} isAuthenticated={isAuthenticated} userRole={currentUser.role} requiredRole="admin">
            <div className="page-enter"><AdminPanel /></div>
          </ProtectedRoute>
        } />
        <Route path="admin/audit-logs" element={
          <ProtectedRoute isLoading={isAuthLoading} isAuthenticated={isAuthenticated} userRole={currentUser.role} requiredRole="admin">
            <div className="page-enter"><AuditLogs /></div>
          </ProtectedRoute>
        } />
      </Route>
      <Route path="*" element={<Navigate to="/projects" replace />} />
    </Routes>
  );
}

export function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  );
}

export default App;
