import axios from 'axios';

// Configure Axios client with base URL (Supports any host, domain, container, or port)
const RAW_URL =
  import.meta.env.VITE_API_BASE_URL ||
  (typeof window !== 'undefined' && window.location.port === '5173'
    ? 'http://localhost:5000/api'
    : typeof window !== 'undefined' && window.location.origin
    ? `${window.location.origin}/api`
    : 'http://localhost:5000/api');
const CLEAN_URL = RAW_URL.replace(/\/+$/, '');
export const API_BASE_URL = CLEAN_URL.endsWith('/api') ? CLEAN_URL : `${CLEAN_URL}/api`;
export const ROOT_URL = API_BASE_URL.replace(/\/api$/, '');

// Set VITE_USE_MOCK=true only if you explicitly want to test in isolated mock mode
const FORCE_MOCK = import.meta.env.VITE_USE_MOCK === 'true';

// Helper to extract detailed error messages from server responses
function extractErrorMessage(err, fallback) {
  if (err?.response?.data) {
    const data = err.response.data;
    if (typeof data.message === 'string') return data.message;
    if (typeof data.detail === 'string') return data.detail;
    if (Array.isArray(data.detail)) {
      return data.detail
        .map((item) => (item.msg ? `${item.loc?.slice(-1)[0] || 'field'}: ${item.msg}` : String(item)))
        .join('; ');
    }
    if (typeof data.error === 'string') return data.error;
  }
  if (err?.message) return err.message;
  return fallback;
}

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Attach authorization token dynamically if available in localStorage
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('aegis_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

/**
 * Default fallback data structure conforming to the Sprint 2 Health Summary contract
 */
export const getMockHealthSummary = (projectId = 'proj_core_platform') => {
  return {
    projectId,
    projectName: 'Core Platform Engine',
    repoUrl: 'https://github.com/aegis-ai/core-api-service',
    branch: 'main',
    lastSyncedAt: new Date().toISOString(),
    overallHealth: {
      score: 84, // 0 - 100
      status: 'Healthy', // 'Healthy' (>=80), 'Caution' (60-79), 'At Risk' (<60)
      color: '#10b981',
      trend: '+4.2% from last sprint',
      factors: [
        {
          name: 'PR Review Latency',
          score: 76,
          weight: 30,
          status: 'Caution',
          description: 'Average time from pull request open to first peer review',
        },
        {
          name: 'Workload Balance',
          score: 72,
          weight: 25,
          status: 'Caution',
          description: 'Commit and PR distribution among active contributors (bus factor)',
        },
        {
          name: 'Issue Hygiene',
          score: 94,
          weight: 25,
          status: 'Healthy',
          description: 'Resolution rate and ratio of active vs. stale issues (>14 days)',
        },
        {
          name: 'Sprint Velocity',
          score: 92,
          weight: 20,
          status: 'Healthy',
          description: 'Completion rate of story points against planned burndown curve',
        },
      ],
      breakdownSummary:
        'Overall delivery velocity remains strong. Review latency on large PRs and workload concentration on top contributors represent key areas for attention.',
    },
    bottlenecks: {
      radarData: [
        { metric: 'Pending PRs (>48h)', score: 68, benchmark: 85, fullMark: 100, display: '4 PRs', threshold: '≤ 2' },
        { metric: 'Review Latency', score: 62, benchmark: 80, fullMark: 100, display: '34h avg', threshold: '≤ 24h' },
        { metric: 'CI/CD Pipeline', score: 94, benchmark: 90, fullMark: 100, display: '8.4m', threshold: '≤ 15m' },
        { metric: 'Merge Conflicts', score: 88, benchmark: 85, fullMark: 100, display: '4.2%', threshold: '≤ 8%' },
        { metric: 'Stale Branches', score: 71, benchmark: 80, fullMark: 100, display: '6 branches', threshold: '≤ 3' },
        { metric: 'PR Churn Size', score: 74, benchmark: 75, fullMark: 100, display: '+310 lines', threshold: '≤ 250' },
      ],
      pendingPrsOver48hCount: 4,
      avgReviewLatencyHours: 34.2,
      criticalBottlenecks: [
        {
          id: 'PR-104',
          title: 'refactor(auth): migrate token rotation to asymmetric keypairs',
          author: 'sarah-connor',
          reviewer: 'alex-chen',
          hoursPending: 74,
          status: 'Waiting for Reviewer',
          severity: 'High',
          additions: 420,
          deletions: 110,
        },
        {
          id: 'PR-99',
          title: 'feat(ingest): batch pipeline streaming ingestion',
          author: 'dev-marcus',
          reviewer: 'sarah-connor',
          hoursPending: 61,
          status: 'Changes Requested',
          severity: 'High',
          additions: 780,
          deletions: 45,
        },
        {
          id: 'PR-112',
          title: 'fix(db): connection pool starvation during spike query',
          author: 'elena-rostova',
          reviewer: 'dev-marcus',
          hoursPending: 52,
          status: 'CI Failing',
          severity: 'Medium',
          additions: 65,
          deletions: 18,
        },
        {
          id: 'PR-115',
          title: 'chore: bump dependencies and security patches for vite',
          author: 'alex-chen',
          reviewer: 'elena-rostova',
          hoursPending: 49,
          status: 'Waiting for Reviewer',
          severity: 'Low',
          additions: 120,
          deletions: 95,
        },
      ],
    },
    workload: {
      contributors: [
        { name: 'Sarah Connor', commits: 48, prs: 14, totalActivity: 62, percentage: 38.3, isBusFactorRisk: true },
        { name: 'Alex Chen', commits: 32, prs: 9, totalActivity: 41, percentage: 25.3, isBusFactorRisk: false },
        { name: 'Marcus Dev', commits: 22, prs: 6, totalActivity: 28, percentage: 17.3, isBusFactorRisk: false },
        { name: 'Elena Rostova', commits: 16, prs: 4, totalActivity: 20, percentage: 12.3, isBusFactorRisk: false },
        { name: 'David Kim', commits: 9, prs: 2, totalActivity: 11, percentage: 6.8, isBusFactorRisk: false },
      ],
      busFactorScore: 2,
      busFactorRisk: 'Moderate Risk',
      busFactorDescription:
        'Top contributor (Sarah Connor) accounts for 38.3% of all code activity, and the top 2 contributors represent 63.6% of team throughput. Knowledge transfer is recommended.',
    },
    staleIssues: [
      {
        id: 'ISSUE-342',
        title: 'Memory leak in streaming metrics websocket connection',
        author: 'alex-chen',
        assignee: 'elena-rostova',
        daysInactive: 42,
        severity: 'Critical',
        status: 'Open',
        labels: ['bug', 'memory', 'backend'],
        createdAt: '2026-10-10',
        lastUpdated: '2026-10-10',
      },
      {
        id: 'ISSUE-318',
        title: 'Implement exponential backoff retry on GitHub sync timeouts',
        author: 'dev-marcus',
        assignee: 'Unassigned',
        daysInactive: 28,
        severity: 'High',
        status: 'Open',
        labels: ['feature', 'reliability'],
        createdAt: '2026-10-24',
        lastUpdated: '2026-10-24',
      },
      {
        id: 'ISSUE-295',
        title: 'Update Docker base image to Alpine 3.20 for CVE mitigation',
        author: 'sarah-connor',
        assignee: 'david-kim',
        daysInactive: 19,
        severity: 'Medium',
        status: 'In Progress',
        labels: ['security', 'docker'],
        createdAt: '2026-11-02',
        lastUpdated: '2026-11-02',
      },
      {
        id: 'ISSUE-280',
        title: 'Flaky integration test in commit_service mock suite',
        author: 'elena-rostova',
        assignee: 'Unassigned',
        daysInactive: 15,
        severity: 'Low',
        status: 'Open',
        labels: ['tests', 'ci'],
        createdAt: '2026-11-06',
        lastUpdated: '2026-11-06',
      },
      {
        id: 'ISSUE-264',
        title: 'Missing swagger documentation for repository branch endpoint',
        author: 'david-kim',
        assignee: 'alex-chen',
        daysInactive: 8,
        severity: 'Low',
        status: 'Open',
        labels: ['docs'],
        createdAt: '2026-11-13',
        lastUpdated: '2026-11-13',
      },
      {
        id: 'ISSUE-251',
        title: 'Cache redis session TTL expiration edge cases during failover',
        author: 'sarah-connor',
        assignee: 'Unassigned',
        daysInactive: 35,
        severity: 'High',
        status: 'Open',
        labels: ['redis', 'backend'],
        createdAt: '2026-10-17',
        lastUpdated: '2026-10-17',
      },
    ],
    sprint: {
      sprintName: 'Sprint 2: Health & Risk Analytics',
      totalStoryPoints: 50,
      completedStoryPoints: 38,
      remainingStoryPoints: 12,
      velocity: 18.5,
      velocityTarget: 16.0,
      velocityStatus: 'Ahead of Schedule (+15%)',
      daysRemaining: 4,
      totalSprintDays: 14,
      burndown: [
        { day: 'Day 1', ideal: 50, actual: 50 },
        { day: 'Day 3', ideal: 43, actual: 45 },
        { day: 'Day 5', ideal: 36, actual: 37 },
        { day: 'Day 7', ideal: 29, actual: 28 },
        { day: 'Day 9', ideal: 22, actual: 19 },
        { day: 'Day 11', ideal: 14, actual: 12 },
        { day: 'Day 14 (End)', ideal: 0, actual: null },
      ],
    },
  };
};

/**
 * Metric Service for communicating with backend health summary APIs
 */
export const metricService = {
  /**
   * Fetch complete health summary for a given project ID and selected repository
   * Endpoint: GET /api/projects/{id}/health-summary?repo={repoName}
   */
  async getHealthSummary(projectId, repoName) {
    const id = projectId || 'proj_core_platform';
    const query = repoName ? `?repo=${encodeURIComponent(repoName)}` : '';

    if (FORCE_MOCK) {
      return getMockHealthSummary(id, repoName);
    }

    try {
      const response = await apiClient.get(`/projects/${id}/health-summary${query}`);
      if (response && response.data) {
        return response.data;
      }
      throw new Error(`Empty response received from /api/projects/${id}/health-summary`);
    } catch (err) {
      const msg = extractErrorMessage(err, `Could not connect to health summary endpoint for project '${id}'.`);
      const error = new Error(msg);
      error.status = err.response?.status;
      error.response = err.response;
      throw error;
    }
  },

  /**
   * Trigger manual data sync and recalculation for project metrics
   * Endpoint: POST /api/projects/{id}/sync?repo={repoName}
   */
  async syncProjectData(projectId, repoName) {
    const id = projectId || 'proj_core_platform';
    const query = repoName ? `?repo=${encodeURIComponent(repoName)}` : '';

    if (FORCE_MOCK) {
      return {
        status: 'success',
        message: 'Project metrics synchronized successfully.',
        syncedAt: new Date().toISOString(),
      };
    }

    try {
      const response = await apiClient.post(`/projects/${id}/sync${query}`);
      if (response && response.data) {
        return response.data;
      }
      throw new Error(`Empty response received from /api/projects/${id}/sync`);
    } catch (err) {
      const msg = extractErrorMessage(err, `Failed to synchronize project metrics for '${id}'.`);
      const error = new Error(msg);
      error.status = err.response?.status;
      error.response = err.response;
      throw error;
    }
  },
};

export default metricService;
