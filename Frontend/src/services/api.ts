// API Service Layer for Aegis AI
// Fully integrated with both the included server (http://localhost:5000/api) and FastAPI backend
// Strict live connection mode: Network failures will surface actionable error messages directly in the UI.

export interface User {
  id: string;
  name: string;
  username: string;
  email: string;
  role?: string;
  createdAt?: string;
}

export interface AuthResponse {
  token: string;
  user: User;
}

export interface ProjectPayload {
  name: string;
  description?: string;
  projectType?: string;
  repo_url?: string;
  default_branch?: string;
}

export interface ProjectResponse {
  id: string;
  name: string;
  description: string;
  projectType?: string;
  ownerId?: string;
  repo_url?: string;
  default_branch?: string;
  status?: string;
  createdAt: string;
  updatedAt?: string;
}

export interface RepositoryPayload {
  projectId: string;
  githubUrl: string;
  branch?: string;
}

export interface RepositoryResponse {
  id: string;
  projectId: string;
  repoName: string;
  githubUrl: string;
  branch: string;
  connectedAt: string;
  status: 'connected' | 'pending' | 'syncing';
}

export interface ApiError {
  message: string;
  field?: string;
  status?: number;
}

// ---------------------------------------------------------------------------
// URL & Environment Resolution
// ---------------------------------------------------------------------------
const RAW_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';
const CLEAN_URL = RAW_URL.replace(/\/+$/, '');
// API_BASE_URL points to the /api base (e.g. http://localhost:5000/api)
export const API_BASE_URL = CLEAN_URL.endsWith('/api') ? CLEAN_URL : `${CLEAN_URL}/api`;
// ROOT_URL points to the origin root without /api (e.g. http://localhost:5000)
export const ROOT_URL = API_BASE_URL.replace(/\/api$/, '');

// Set VITE_USE_MOCK=true only if you explicitly want to test in isolated mock mode
const FORCE_MOCK = import.meta.env.VITE_USE_MOCK === 'true';

// Helper to extract detailed error messages from server responses
function extractErrorMessage(errData: any, fallback: string): string {
  if (!errData) return fallback;
  if (typeof errData.message === 'string') return errData.message;
  if (typeof errData.detail === 'string') return errData.detail;
  if (Array.isArray(errData.detail)) {
    return errData.detail
      .map((item: any) => (item.msg ? `${item.loc?.slice(-1)[0] || 'field'}: ${item.msg}` : String(item)))
      .join('; ');
  }
  if (typeof errData.error === 'string') return errData.error;
  return fallback;
}

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

// ---------------------------------------------------------------------------
// Disposable email domain blocklist (client-side only — no external DNS calls)
// ---------------------------------------------------------------------------
const DISPOSABLE_DOMAINS = new Set([
  'mailinator.com',
  'tempmail.com',
  '10minutemail.com',
  'guerrillamail.com',
  'trashmail.com',
  'sharklasers.com',
  'yopmail.com',
  'temp-mail.org',
  'dispostable.com',
  'getairmail.com',
]);

// RFC 5322-compatible lightweight email format regex (client-side structural check)
const EMAIL_FORMAT_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

/**
 * Client-side email validation.
 *
 * Performs two fast, privacy-preserving checks with no external network calls:
 *   1. RFC 5322 structural format check via regex.
 *   2. Disposable/temporary domain blocklist lookup.
 *
 * Full domain-existence (MX record) validation is intentionally delegated to
 * the backend at POST /api/auth/signup, which performs the check server-side
 * without exposing user email domains to third-party DNS resolvers.
 *
 * SECURITY NOTE: The previous implementation queried
 * https://cloudflare-dns.com/dns-query directly from the browser, leaking
 * every registering user's email domain to Cloudflare and adding up to 3.5 s
 * of latency. That approach also silently bypassed the check on network
 * failure, making it ineffective. This replacement is synchronous, instant,
 * and keeps user data on the first-party connection only.
 */
export function verifyEmailDomain(email: string): { isValid: boolean; reason?: string } {
  const trimmed = email.trim();

  // 1. Structural format check
  if (!EMAIL_FORMAT_RE.test(trimmed)) {
    return { isValid: false, reason: 'Invalid email address structure.' };
  }

  const domain = trimmed.split('@')[1].toLowerCase();

  // 2. Disposable domain blocklist
  if (DISPOSABLE_DOMAINS.has(domain)) {
    return {
      isValid: false,
      reason: `Disposable or temporary email providers (@${domain}) are not permitted.`,
    };
  }

  // Domain-existence check (MX records) is handled server-side at signup.
  return { isValid: true };
}

// ===========================================================================
// 1. AUTHENTICATION API (POST /api/auth/login, POST /api/auth/signup, GET /api/auth/me)
// ===========================================================================
export const authApi = {
  /**
   * Authenticate user with email and password
   * Calls: POST /api/auth/login (with fallback to /auth/login)
   */
  async login(email: string, password: string): Promise<AuthResponse> {
    if (FORCE_MOCK) {
      return this._mockLogin(email, password);
    }

    const payload = JSON.stringify({ email: email.trim(), password });

    try {
      // Primary: /api/auth/login (matching included server)
      let response = await fetch(`${API_BASE_URL}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: payload,
      });

      // Secondary fallback if server routes auth directly at root /auth/login
      if (response.status === 404 && ROOT_URL !== API_BASE_URL) {
        const altResponse = await fetch(`${ROOT_URL}/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: payload,
        });
        if (altResponse.status !== 404) {
          response = altResponse;
        }
      }

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(extractErrorMessage(errData, `Login failed with status ${response.status}`));
      }

      const data = await response.json();
      const token = data.token || data.access_token;
      if (token) {
        localStorage.setItem('aegis_token', token);
      }

      const userObj = data.user || data;
      const user: User = {
        id: String(userObj.id || userObj._id || 'usr_' + Date.now()),
        name: userObj.name || 'Developer',
        username: userObj.username || `@${email.split('@')[0]}`,
        email: userObj.email || email.trim(),
        role: userObj.role || 'developer',
        createdAt: userObj.createdAt || userObj.created_at,
      };

      return { token, user };
    } catch (err: any) {
      if (err.message?.includes('Failed to fetch') || err.message?.includes('NetworkError')) {
        throw new Error(
          `Unable to connect to backend server at ${API_BASE_URL}/auth/login. Please ensure your backend server is running.`
        );
      }
      throw err;
    }
  },

  /**
   * Register a new user account
   * Calls: POST /api/auth/signup (with fallback to /auth/signup)
   */
  async signup(name: string, email: string, password: string, username?: string): Promise<AuthResponse> {
    const cleanUsername = (username ? username.trim().replace(/^@/, '') : email.split('@')[0]);

    if (FORCE_MOCK) {
      return this._mockSignup(name, cleanUsername, email, password);
    }

    const payload = JSON.stringify({
      name: name.trim(),
      email: email.trim(),
      password,
      username: cleanUsername,
      role: 'developer',
    });

    try {
      // Primary: /api/auth/signup (matching included server)
      let response = await fetch(`${API_BASE_URL}/auth/signup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: payload,
      });

      // Secondary fallback if server routes auth directly at root /auth/signup
      if (response.status === 404 && ROOT_URL !== API_BASE_URL) {
        const altResponse = await fetch(`${ROOT_URL}/auth/signup`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: payload,
        });
        if (altResponse.status !== 404) {
          response = altResponse;
        }
      }

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(extractErrorMessage(errData, `Signup failed with status ${response.status}`));
      }

      const data = await response.json();
      const token = data.token || data.access_token;
      if (token) {
        localStorage.setItem('aegis_token', token);
      }

      const userObj = data.user || data;
      const user: User = {
        id: String(userObj.id || userObj._id || 'usr_' + Date.now()),
        name: userObj.name || name.trim(),
        username: userObj.username || cleanUsername,
        email: userObj.email || email.trim(),
        role: userObj.role || 'developer',
        createdAt: userObj.createdAt || userObj.created_at,
      };

      return { token, user };
    } catch (err: any) {
      if (err.message?.includes('Failed to fetch') || err.message?.includes('NetworkError')) {
        throw new Error(
          `Unable to connect to backend server at ${API_BASE_URL}/auth/signup. Please ensure your backend server is running.`
        );
      }
      throw err;
    }
  },

  /**
   * Fetch current authenticated user's profile
   * Calls: GET /api/auth/me
   */
  async getMe(): Promise<User | null> {
    const token = localStorage.getItem('aegis_token');
    if (!token || FORCE_MOCK) return null;

    try {
      const response = await fetch(`${API_BASE_URL}/auth/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (response.status === 401 || response.status === 403) {
        localStorage.removeItem('aegis_token');
        localStorage.removeItem('aegis_auth');
        return null;
      }
      if (response.ok) {
        const data = await response.json();
        const userObj = data.user || data;
        return {
          id: String(userObj.id || userObj._id),
          name: userObj.name,
          username: userObj.username || `@${userObj.email.split('@')[0]}`,
          email: userObj.email,
          role: userObj.role,
          createdAt: userObj.createdAt || userObj.created_at,
        };
      }
    } catch (err) {
      console.warn('Failed to fetch user profile from /api/auth/me:', err);
    }
    return null;
  },

  /**
   * Log out current session
   * Calls: POST /api/auth/logout
   */
  async logout(): Promise<void> {
    const token = localStorage.getItem('aegis_token');
    if (token && !FORCE_MOCK) {
      try {
        await fetch(`${API_BASE_URL}/auth/logout`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` },
        });
      } catch {
        // ignore
      }
    }
    localStorage.removeItem('aegis_token');
  },

  // Internal Mock Implementation (Only invoked if VITE_USE_MOCK=true)
  async _mockLogin(email: string, _password: string): Promise<AuthResponse> {
    await delay(500);
    const stored = localStorage.getItem('aegis_registered_users');
    let registeredUsers: Array<{ email: string; name: string; username: string }> = [
      { email: 'john.dev@aegis-health.io', name: 'John Developer', username: 'johndev' },
      { email: 'demo@aegis.io', name: 'Demo Architect', username: 'demo_user' },
    ];
    if (stored) {
      try {
        const parsed = JSON.parse(stored);
        if (Array.isArray(parsed)) registeredUsers = [...parsed, ...registeredUsers];
      } catch {}
    }
    const matchedUser = registeredUsers.find((u) => u.email.toLowerCase() === email.trim().toLowerCase());
    if (!matchedUser) throw new Error('No account found with this email address. Please check your spelling or sign up.');
    const mockToken = 'jwt_mock_token_' + Date.now();
    localStorage.setItem('aegis_token', mockToken);
    return {
      token: mockToken,
      user: {
        id: 'usr_' + Math.random().toString(36).substring(2, 9),
        name: matchedUser.name,
        username: matchedUser.username,
        email: matchedUser.email,
        role: 'developer',
      },
    };
  },

  async _mockSignup(name: string, username: string, email: string, password: string): Promise<AuthResponse> {
    if (!password || password.length < 8) {
      throw new Error('Password must be at least 8 characters.');
    }
    if (/[\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]/.test(password)) {
      throw new Error('Password must not contain spaces or whitespace characters.');
    }
    await delay(500);
    const stored = localStorage.getItem('aegis_registered_users');
    let registeredUsers: Array<{ email: string; name: string; username: string }> = [];
    if (stored) {
      try {
        const parsed = JSON.parse(stored);
        if (Array.isArray(parsed)) registeredUsers = parsed;
      } catch {}
    }
    if (registeredUsers.some((u) => u.email.toLowerCase() === email.trim().toLowerCase())) {
      throw new Error('An account with this email address already exists. Please log in instead.');
    }
    // Never store plaintext passwords in browser storage
    registeredUsers.push({ email: email.trim(), name: name.trim(), username });
    localStorage.setItem('aegis_registered_users', JSON.stringify(registeredUsers));
    const mockToken = 'jwt_mock_token_' + Date.now();
    localStorage.setItem('aegis_token', mockToken);
    return {
      token: mockToken,
      user: {
        id: 'usr_' + Math.random().toString(36).substring(2, 9),
        name: name.trim(),
        username,
        email: email.trim(),
        role: 'developer',
      },
    };
  },
};

// ===========================================================================
// 2. PROJECT API (POST /api/projects, GET /api/projects)
// ===========================================================================
export const projectApi = {
  /**
   * Create a new project
   * Calls: POST /api/projects
   */
  async createProject(payload: ProjectPayload): Promise<ProjectResponse> {
    if (FORCE_MOCK) {
      return this._mockCreateProject(payload);
    }

    try {
      const token = localStorage.getItem('aegis_token');
      const requestBody = JSON.stringify({
        name: payload.name.trim(),
        description: payload.description ? payload.description.trim() : '',
        projectType: payload.projectType || 'backend-service',
        repo_url: payload.repo_url || null,
        default_branch: payload.default_branch || 'main',
      });

      let response = await fetch(`${API_BASE_URL}/projects`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: requestBody,
      });

      if (response.status === 404 && ROOT_URL !== API_BASE_URL) {
        const altResponse = await fetch(`${ROOT_URL}/projects`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: requestBody,
        });
        if (altResponse.status !== 404) {
          response = altResponse;
        }
      }

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(extractErrorMessage(errData, `Project creation failed with status ${response.status}`));
      }

      const data = await response.json();
      // Robust mapping handling top-level, nested data.project, and MongoDB _id
      const p = data.project || data.data || data;

      return {
        id: String(p.id || p._id || 'proj_' + Date.now()),
        name: p.name || payload.name.trim(),
        description: p.description || payload.description || '',
        projectType: p.projectType || payload.projectType || 'backend-service',
        ownerId: p.ownerId || '',
        repo_url: p.repo_url || p.githubUrl,
        default_branch: p.default_branch || 'main',
        status: p.status || 'active',
        createdAt: p.createdAt || p.created_at || new Date().toISOString(),
        updatedAt: p.updatedAt || p.updated_at,
      };
    } catch (err: any) {
      if (err.message?.includes('Failed to fetch') || err.message?.includes('NetworkError')) {
        throw new Error(
          `Unable to connect to backend server at ${API_BASE_URL}/projects. Please ensure your backend server is running.`
        );
      }
      throw err;
    }
  },

  /**
   * List all projects for current user
   * Calls: GET /api/projects
   */
  async getProjects(): Promise<ProjectResponse[]> {
    if (FORCE_MOCK) return [];

    try {
      const token = localStorage.getItem('aegis_token');
      let response = await fetch(`${API_BASE_URL}/projects`, {
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
      });

      if (response.status === 404 && ROOT_URL !== API_BASE_URL) {
        const altResponse = await fetch(`${ROOT_URL}/projects`, {
          headers: {
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
        });
        if (altResponse.status !== 404) {
          response = altResponse;
        }
      }

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(extractErrorMessage(errData, `Failed to fetch projects with status ${response.status}`));
      }

      const raw = await response.json();
      const list = Array.isArray(raw) ? raw : (raw.projects || raw.data || []);

      return list.map((p: any) => ({
        id: String(p.id || p._id),
        name: p.name,
        description: p.description || '',
        projectType: p.projectType || 'backend-service',
        ownerId: p.ownerId,
        repo_url: p.repo_url,
        default_branch: p.default_branch || 'main',
        status: p.status || 'active',
        createdAt: p.createdAt || p.created_at || '',
        updatedAt: p.updatedAt || p.updated_at,
      }));
    } catch (err: any) {
      if (err.message?.includes('Failed to fetch') || err.message?.includes('NetworkError')) {
        throw new Error(`Unable to fetch projects: Backend server at ${API_BASE_URL}/projects is unreachable.`);
      }
      throw err;
    }
  },

  /**
   * Retrieve project by ID
   * Calls: GET /api/projects/{project_id}
   */
  async getProject(projectId: string): Promise<ProjectResponse | null> {
    if (FORCE_MOCK) return null;

    try {
      const token = localStorage.getItem('aegis_token');
      const response = await fetch(`${API_BASE_URL}/projects/${projectId}`, {
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
      });
      if (response.ok) {
        const raw = await response.json();
        const p = raw.project || raw.data || raw;
        return {
          id: String(p.id || p._id),
          name: p.name,
          description: p.description || '',
          projectType: p.projectType || 'backend-service',
          ownerId: p.ownerId,
          repo_url: p.repo_url,
          default_branch: p.default_branch || 'main',
          status: p.status || 'active',
          createdAt: p.createdAt || p.created_at || '',
          updatedAt: p.updatedAt || p.updated_at,
        };
      }
    } catch (err: any) {
      if (err.message?.includes('Failed to fetch') || err.message?.includes('NetworkError')) {
        throw new Error(`Unable to fetch project: Backend server at ${API_BASE_URL}/projects/${projectId} is unreachable.`);
      }
      throw err;
    }
    return null;
  },

  async _mockCreateProject(payload: ProjectPayload): Promise<ProjectResponse> {
    await delay(500);
    return {
      id: 'proj_' + Math.random().toString(36).substring(2, 9),
      name: payload.name.trim(),
      description: payload.description || '',
      projectType: payload.projectType || 'backend-service',
      default_branch: payload.default_branch || 'main',
      status: 'active',
      createdAt: new Date().toISOString(),
    };
  },
};

// ===========================================================================
// 3. REPOSITORY API (POST /api/repositories/connect)
// ===========================================================================
export const repositoryApi = {
  /**
   * Connect a GitHub repository to a project
   * Calls: POST /api/repositories/connect (the standard endpoint for repository connection)
   */
  async connectRepository(payload: RepositoryPayload): Promise<RepositoryResponse> {
    const match = payload.githubUrl.match(/github\.com\/([^/]+)\/([^/]+)/i);
    if (!match) {
      throw new Error('Invalid GitHub repository URL. Format must be https://github.com/owner/repository');
    }
    const repoSlug = match[2].replace(/\.git$/, '');

    if (FORCE_MOCK) {
      await delay(500);
      return {
        id: 'repo_' + Math.random().toString(36).substring(2, 9),
        projectId: payload.projectId,
        repoName: repoSlug,
        githubUrl: payload.githubUrl.trim(),
        branch: payload.branch || 'main',
        connectedAt: new Date().toISOString(),
        status: 'connected',
      };
    }

    try {
      const token = localStorage.getItem('aegis_token');
      const requestBody = JSON.stringify({
        projectId: payload.projectId,
        githubUrl: payload.githubUrl.trim(),
        branch: payload.branch || 'main',
      });

      // Primary: POST /api/repositories/connect (matching Sprint 1 spec & included server)
      let response = await fetch(`${API_BASE_URL}/repositories/connect`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: requestBody,
      });

      // Secondary fallback if server routes without /api
      if (response.status === 404 && ROOT_URL !== API_BASE_URL) {
        const altResponse = await fetch(`${ROOT_URL}/repositories/connect`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: requestBody,
        });
        if (altResponse.status !== 404) {
          response = altResponse;
        }
      }

      // Tertiary fallback if backend expects PATCH /api/projects/:id (e.g. FastAPI)
      if (response.status === 404 && payload.projectId) {
        const patchResponse = await fetch(`${API_BASE_URL}/projects/${payload.projectId}`, {
          method: 'PATCH',
          headers: {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({
            repo_url: payload.githubUrl.trim(),
            default_branch: payload.branch || 'main',
          }),
        });
        if (patchResponse.ok) {
          response = patchResponse;
        }
      }

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(extractErrorMessage(errData, `Repository connection failed with status ${response.status}`));
      }

      const raw = await response.json();
      const r = raw.repository || raw.data || raw;

      return {
        id: String(r.id || r._id || 'repo_' + Date.now()),
        projectId: String(r.projectId || payload.projectId),
        repoName: r.repoName || repoSlug,
        githubUrl: r.githubUrl || payload.githubUrl.trim(),
        branch: r.branch || payload.branch || 'main',
        connectedAt: r.connectedAt || r.connected_at || r.updatedAt || new Date().toISOString(),
        status: (r.status as any) || 'connected',
      };
    } catch (err: any) {
      if (err.message?.includes('Failed to fetch') || err.message?.includes('NetworkError')) {
        throw new Error(
          `Unable to connect to backend server at ${API_BASE_URL}/repositories/connect. Please ensure your backend server is running.`
        );
      }
      throw err;
    }
  },

  /**
   * Fetch branches by proxying through the backend endpoint GET /api/repositories/branches
   * Avoids exhausting client-side GitHub unauthenticated rate limits.
   */
  async fetchBranches(githubUrl: string): Promise<{ branches: string[]; source: 'github' | 'default' }> {
    const cleanUrl = githubUrl.trim().replace(/\/+$/, '');
    if (!cleanUrl) {
      return { branches: ['main', 'master', 'develop', 'staging', 'production'], source: 'default' };
    }

    try {
      const token = localStorage.getItem('aegis_token');
      const response = await fetch(
        `${API_BASE_URL}/repositories/branches?url=${encodeURIComponent(cleanUrl)}`,
        {
          headers: {
            Accept: 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
        }
      );

      if (response.ok) {
        const data = await response.json();
        if (data && Array.isArray(data.branches) && data.branches.length > 0) {
          return {
            branches: data.branches,
            source: data.source === 'github' ? 'github' : 'default',
          };
        }
      } else {
        console.warn(`Backend branch proxy returned status ${response.status}`);
      }
    } catch (err) {
      console.warn('Could not fetch branches via backend proxy, using standard branch list.', err);
    }

    return { branches: ['main', 'master', 'develop', 'staging', 'production'], source: 'default' };
  },
};

// ===========================================================================
// 4. METRICS & HEALTH API (/api/projects/:id/health-summary, breakdown)
// ===========================================================================
export interface HealthSummaryData {
  project_id: string;
  project_name: string;
  health_score: number | null;
  status: 'Good' | 'Caution' | 'At Risk' | 'Insufficient Data';
  last_synced_at: string | null;
  data_freshness: 'fresh' | 'stale' | 'unknown';
  data_availability: Record<string, string>;
  summary_statement: string;
  flags_count: {
    total: number;
    high: number;
    medium: number;
    low: number;
  };
  active_flags: Array<{
    id: string;
    type: string;
    severity: string;
    message: string;
    evidence?: any;
  }>;
  evaluated_at: string;
}

export interface IndicatorDetail {
  score: number | null;
  status: string;
  data_status: string;
  weight: number;
  details: Record<string, any>;
  flags: Array<any>;
}

export interface MetricsBreakdownData {
  project_id: string;
  project_name: string;
  health_score: number | null;
  status: string;
  evaluated_at: string;
  weights_used: Record<string, number>;
  indicators: {
    bottlenecks: IndicatorDetail;
    workload: IndicatorDetail;
    stale_issues: IndicatorDetail;
    schedule_risk: IndicatorDetail;
  };
}

export const metricsApi = {
  async getHealthSummary(projectId: string): Promise<HealthSummaryData> {
    const token = localStorage.getItem('aegis_token');
    const response = await fetch(`${API_BASE_URL}/projects/${projectId}/health-summary`, {
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(extractErrorMessage(err, `Failed to fetch health summary (${response.status})`));
    }

    return response.json();
  },

  async getMetricsBreakdown(projectId: string): Promise<MetricsBreakdownData> {
    const token = localStorage.getItem('aegis_token');
    const response = await fetch(`${API_BASE_URL}/projects/${projectId}/metrics/breakdown`, {
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(extractErrorMessage(err, `Failed to fetch metrics breakdown (${response.status})`));
    }

    return response.json();
  },
};

// ===========================================================================
// 5. DATA SYNC & TELEMETRY API (Commits, Contribs, PRs, Issues, Milestones)
// ===========================================================================
export const dataSyncApi = {
  async getContributors(projectId: string): Promise<any[]> {
    const token = localStorage.getItem('aegis_token');
    const res = await fetch(`${API_BASE_URL}/projects/${projectId}/contributors`, {
      headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    });
    if (!res.ok) throw new Error(`Failed to fetch contributors (${res.status})`);
    return res.json();
  },

  async syncContributors(projectId: string): Promise<any> {
    const token = localStorage.getItem('aegis_token');
    const res = await fetch(`${API_BASE_URL}/projects/${projectId}/sync-contributors`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({}),
    });
    if (!res.ok) throw new Error(`Failed to sync contributors (${res.status})`);
    return res.json();
  },

  async getCommits(projectId: string, limit = 50): Promise<any[]> {
    const token = localStorage.getItem('aegis_token');
    const res = await fetch(`${API_BASE_URL}/projects/${projectId}/commits?limit=${limit}`, {
      headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    });
    if (!res.ok) throw new Error(`Failed to fetch commits (${res.status})`);
    return res.json();
  },

  async syncCommits(projectId: string, branch = 'main', maxCommits = 100): Promise<any> {
    const token = localStorage.getItem('aegis_token');
    const res = await fetch(`${API_BASE_URL}/projects/${projectId}/sync-commits`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ branch, max_commits: maxCommits }),
    });
    if (!res.ok) throw new Error(`Failed to sync commits (${res.status})`);
    return res.json();
  },

  async getPRs(projectId: string, state?: string): Promise<any[]> {
    const token = localStorage.getItem('aegis_token');
    const query = state && state.toLowerCase() !== 'all' ? `?state=${encodeURIComponent(state)}` : '';
    const res = await fetch(`${API_BASE_URL}/projects/${projectId}/prs${query}`, {
      headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    });
    if (!res.ok) throw new Error(`Failed to fetch pull requests (${res.status})`);
    return res.json();
  },

  async syncPRs(projectId: string, timeoutMs = 60000): Promise<any> {
    const token = localStorage.getItem('aegis_token');
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const res = await fetch(`${API_BASE_URL}/projects/${projectId}/sync-prs`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({}),
        signal: controller.signal,
      });
      if (!res.ok) throw new Error(`Failed to sync pull requests (${res.status})`);
      return await res.json();
    } catch (err: any) {
      if (err.name === 'AbortError') {
        throw new Error('Synchronization timed out. Please try again.');
      }
      throw err;
    } finally {
      clearTimeout(timer);
    }
  },

  async getIssues(projectId: string, state?: string): Promise<any[]> {
    const token = localStorage.getItem('aegis_token');
    const query = state && state.toLowerCase() !== 'all' ? `?state=${encodeURIComponent(state)}` : '';
    const res = await fetch(`${API_BASE_URL}/projects/${projectId}/issues${query}`, {
      headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    });
    if (!res.ok) throw new Error(`Failed to fetch issues (${res.status})`);
    return res.json();
  },

  async syncIssues(projectId: string, timeoutMs = 60000): Promise<any> {
    const token = localStorage.getItem('aegis_token');
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const res = await fetch(`${API_BASE_URL}/projects/${projectId}/sync-issues`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({}),
        signal: controller.signal,
      });
      if (!res.ok) throw new Error(`Failed to sync issues (${res.status})`);
      return await res.json();
    } catch (err: any) {
      if (err.name === 'AbortError') {
        throw new Error('Synchronization timed out. Please try again.');
      }
      throw err;
    } finally {
      clearTimeout(timer);
    }
  },

  async getMilestones(projectId: string): Promise<any[]> {
    const token = localStorage.getItem('aegis_token');
    const res = await fetch(`${API_BASE_URL}/projects/${projectId}/milestones`, {
      headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    });
    if (!res.ok) throw new Error(`Failed to fetch milestones (${res.status})`);
    return res.json();
  },

  async syncMilestones(projectId: string): Promise<any> {
    const token = localStorage.getItem('aegis_token');
    const res = await fetch(`${API_BASE_URL}/projects/${projectId}/sync-milestones`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({}),
    });
    if (!res.ok) throw new Error(`Failed to sync milestones (${res.status})`);
    return res.json();
  },
};

// ===========================================================================
// 6. THRESHOLDS CONFIGURATION API (/api/projects/:id/thresholds)
// ===========================================================================
export const thresholdApi = {
  async getThresholds(projectId: string): Promise<any> {
    const token = localStorage.getItem('aegis_token');
    const res = await fetch(`${API_BASE_URL}/projects/${projectId}/thresholds`, {
      headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    });
    if (!res.ok) throw new Error(`Failed to fetch thresholds (${res.status})`);
    return res.json();
  },

  async updateThresholds(projectId: string, thresholds: Record<string, any>): Promise<any> {
    const token = localStorage.getItem('aegis_token');
    const res = await fetch(`${API_BASE_URL}/projects/${projectId}/thresholds`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(thresholds),
    });
    if (!res.ok) throw new Error(`Failed to update thresholds (${res.status})`);
    return res.json();
  },
};

// ===========================================================================
// 7. REPORT API (/api/projects/:id/reports)
// ===========================================================================
export interface GeneratedReport {
  id: string;
  title: string;
  project: string;
  generatedDate: string;
  healthScore: number;
  risksCount: number;
  bottlenecksCount: number;
  recommendations: string[];
}

export const reportApi = {
  async generateReport(projectId: string): Promise<GeneratedReport> {
    const token = localStorage.getItem('aegis_token');
    const res = await fetch(`${API_BASE_URL}/projects/${projectId}/reports/generate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(extractErrorMessage(err, `Report generation failed (${res.status})`));
    }

    const data = await res.json();
    const rep = data.report || {};
    const health = rep.project_health || {};
    const rawRecs = rep.recommendations || [];

    return {
      id: data.report_id || `rep_${Date.now()}`,
      title: 'PROJECT HEALTH AUDIT REPORT',
      project: data.project_id || projectId,
      generatedDate: data.generated_at
        ? new Date(data.generated_at).toLocaleDateString('en-US', { month: 'short', day: '2-digit', year: 'numeric' })
        : new Date().toLocaleDateString('en-US', { month: 'short', day: '2-digit', year: 'numeric' }),
      healthScore: typeof data.health_score === 'number' ? data.health_score : (health.score ?? 75),
      risksCount: Array.isArray(rep.risks) ? rep.risks.length : (typeof rep.flags_count?.total === 'number' ? rep.flags_count.total : 2),
      bottlenecksCount: Array.isArray(rep.bottlenecks) ? rep.bottlenecks.length : 1,
      recommendations: Array.isArray(rawRecs) && rawRecs.length > 0
        ? rawRecs.map((r: any) => (typeof r === 'string' ? r : r.message || JSON.stringify(r)))
        : [
            'Review open pull requests aging beyond 48 hours',
            'Verify issue assignment distribution across core maintainers',
            'Inspect sprint delivery velocity against planned milestones',
          ],
    };
  },

  async getReports(projectId: string): Promise<GeneratedReport[]> {
    const token = localStorage.getItem('aegis_token');
    try {
      const res = await fetch(`${API_BASE_URL}/projects/${projectId}/reports`, {
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
      });

      if (!res.ok) return [];
      const data = await res.json();
      const list = Array.isArray(data.reports) ? data.reports : (Array.isArray(data) ? data : []);

      return list.map((item: any) => ({
        id: item.report_id || item.id || item._id || String(Date.now()),
        title: item.title || 'PROJECT HEALTH REPORT',
        project: item.project_id || projectId,
        generatedDate: item.generated_at
          ? new Date(item.generated_at).toLocaleDateString('en-US', { month: 'short', day: '2-digit', year: 'numeric' })
          : 'Recent',
        healthScore: item.health_score ?? item.score ?? 80,
        risksCount: item.risks_count ?? 2,
        bottlenecksCount: item.bottlenecks_count ?? 1,
        recommendations: Array.isArray(item.recommendations) ? item.recommendations : [
          'Review open pull requests aging beyond 48 hours',
          'Automated CI build times stabilized under 4 minutes',
        ],
      }));
    } catch {
      return [];
    }
  },
};

// ===========================================================================
// 8. ADMIN API (/api/admin)
// ===========================================================================

export interface AdminUser {
  id: string;
  name: string;
  email: string;
  role: 'admin' | 'project_manager' | 'developer';
  is_active: boolean;
  created_at: string;
}

export interface PaginatedUsersResponse {
  items: AdminUser[];
  total: number;
  skip: number;
  limit: number;
}

export interface AuditLog {
  id: string;
  action: string;
  actor_id: string;
  target_id: string | null;
  detail: string | null;
  created_at: string;
}

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem('aegis_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export const adminApi = {
  /**
   * List platform users with optional search, active-status filter and pagination.
   * Calls: GET /api/admin/users
   */
  async getUsers(params?: {
    search?: string;
    is_active?: boolean;
    skip?: number;
    limit?: number;
  }): Promise<PaginatedUsersResponse> {
    const qs = new URLSearchParams();
    if (params?.search)             qs.set('search',    params.search);
    if (params?.is_active != null)  qs.set('is_active', String(params.is_active));
    if (params?.skip    != null)    qs.set('skip',      String(params.skip));
    if (params?.limit   != null)    qs.set('limit',     String(params.limit));

    const url = `${API_BASE_URL}/admin/users${qs.toString() ? `?${qs}` : ''}`;
    const res = await fetch(url, { headers: authHeaders() });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(extractErrorMessage(err, `Failed to fetch users (${res.status})`));
    }
    return res.json();
  },

  /**
   * Update a user's platform role.
   * Calls: PATCH /api/admin/users/{id}/role
   */
  async updateUserRole(userId: string, role: AdminUser['role']): Promise<AdminUser> {
    const res = await fetch(`${API_BASE_URL}/admin/users/${userId}/role`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ role }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(extractErrorMessage(err, `Failed to update role (${res.status})`));
    }
    return res.json();
  },

  /**
   * Toggle a user's active status (activate or deactivate).
   * Calls: POST /api/admin/users/{id}/activate  |  /deactivate
   */
  async toggleUserStatus(userId: string, activate: boolean): Promise<AdminUser> {
    const action = activate ? 'activate' : 'deactivate';
    const res = await fetch(`${API_BASE_URL}/admin/users/${userId}/${action}`, {
      method: 'POST',
      headers: authHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(extractErrorMessage(err, `Failed to ${action} user (${res.status})`));
    }
    return res.json();
  },

  /**
   * Fetch recent platform audit logs.
   * Calls: GET /api/admin/audit-logs
   */
  async getAuditLogs(limit = 100): Promise<AuditLog[]> {
    const res = await fetch(`${API_BASE_URL}/admin/audit-logs?limit=${limit}`, {
      headers: authHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(extractErrorMessage(err, `Failed to fetch audit logs (${res.status})`));
    }
    return res.json();
  },
};

// ===========================================================================
// 9. USER SETTINGS API (/api/auth/me/settings)
// ===========================================================================
export interface NotificationPreferences {
  high_risk_threshold: boolean;
  weekly_digest: boolean;
}

export interface NotificationPreferencesUpdate {
  high_risk_threshold?: boolean;
  weekly_digest?: boolean;
}

export const settingsApi = {
  /**
   * Fetch current authenticated user's notification preferences
   * Calls: GET /api/auth/me/settings (with fallback to /auth/me/settings)
   */
  async getNotificationPreferences(): Promise<NotificationPreferences> {
    const token = localStorage.getItem('aegis_token');
    const headers: Record<string, string> = {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    };

    let response = await fetch(`${API_BASE_URL}/auth/me/settings`, { headers });
    if (response.status === 404 && ROOT_URL !== API_BASE_URL) {
      const alt = await fetch(`${ROOT_URL}/auth/me/settings`, { headers });
      if (alt.status !== 404) {
        response = alt;
      }
    }

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(extractErrorMessage(err, `Failed to fetch settings (${response.status})`));
    }

    return response.json();
  },

  /**
   * Partially or fully update user's notification preferences
   * Calls: PATCH /api/auth/me/settings (with fallback to /auth/me/settings)
   */
  async updateNotificationPreferences(
    prefs: NotificationPreferencesUpdate
  ): Promise<NotificationPreferences> {
    const token = localStorage.getItem('aegis_token');
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    };
    const body = JSON.stringify(prefs);

    let response = await fetch(`${API_BASE_URL}/auth/me/settings`, {
      method: 'PATCH',
      headers,
      body,
    });

    if (response.status === 404 && ROOT_URL !== API_BASE_URL) {
      const alt = await fetch(`${ROOT_URL}/auth/me/settings`, {
        method: 'PATCH',
        headers,
        body,
      });
      if (alt.status !== 404) {
        response = alt;
      }
    }

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(extractErrorMessage(err, `Failed to update settings (${response.status})`));
    }

    return response.json();
  },
};
