// ===========================================================================
// Metric Service — Unified data layer for the Dashboard
// Wraps metricsApi / dataSyncApi from api.ts and reshapes responses into
// view-model types consumed by dashboard components.
// ===========================================================================

import {
  metricsApi,
  dataSyncApi,
  type HealthSummaryData,
  type MetricsBreakdownData,
} from './api';

// ---------------------------------------------------------------------------
// View-model types
// ---------------------------------------------------------------------------

/** Overall health gauge data */
export interface HealthGaugeData {
  score: number | null;
  status: 'Good' | 'Caution' | 'At Risk' | 'Insufficient Data';
  summaryStatement: string;
  lastSyncedAt: string | null;
  dataFreshness: 'fresh' | 'stale' | 'unknown';
  factors: {
    label: string;
    score: number | null;
    weight: number;
    status: string;
  }[];
  flags: {
    total: number;
    high: number;
    medium: number;
    low: number;
  };
}

/** Delivery bottleneck item */
export interface BottleneckItem {
  id: string;
  type: 'stale_pr' | 'review_latency' | 'other';
  severity: 'high' | 'medium' | 'low';
  title: string;
  detail: string;
  ageHours?: number;
  author?: string;
  prNumber?: number;
}

/** Workload data per contributor */
export interface WorkloadEntry {
  contributor: string;
  commits: number;
  pullRequests: number;
}

/** Stale issue row */
export interface StaleIssueRow {
  id: string;
  issueNumber: number;
  title: string;
  author: string;
  labels: string[];
  inactiveDays: number;
  lastUpdated: string;
  url?: string;
}

/** Sprint velocity / burndown indicator */
export interface SprintVelocity {
  milestoneName: string;
  totalIssues: number;
  closedIssues: number;
  openIssues: number;
  completionPct: number;
  dueDate: string | null;
  daysRemaining: number | null;
}

// ---------------------------------------------------------------------------
// Service object
// ---------------------------------------------------------------------------

export const metricService = {
  /**
   * Fetch the health gauge + contributing factors for a project.
   */
  async fetchHealthGauge(projectId: string): Promise<HealthGaugeData> {
    const [summary, breakdown] = await Promise.all([
      metricsApi.getHealthSummary(projectId),
      metricsApi.getMetricsBreakdown(projectId).catch(() => null),
    ]);

    const factors = breakdown
      ? Object.entries(breakdown.indicators).map(([key, ind]) => ({
          label: formatIndicatorLabel(key),
          score: ind.score,
          weight: ind.weight,
          status: ind.status,
        }))
      : [];

    return {
      score: summary.health_score,
      status: summary.status,
      summaryStatement: summary.summary_statement,
      lastSyncedAt: summary.last_synced_at,
      dataFreshness: summary.data_freshness,
      factors,
      flags: summary.flags_count,
    };
  },

  /**
   * Derive delivery bottleneck items from open PRs.
   * PRs older than 48 h are flagged; calculates age from creation date.
   */
  async fetchBottlenecks(projectId: string): Promise<BottleneckItem[]> {
    const prs = await dataSyncApi.getPRs(projectId, 'open');

    const now = Date.now();
    const bottlenecks: BottleneckItem[] = [];

    for (const pr of prs) {
      const createdAt = pr.created_at || pr.createdAt;
      if (!createdAt) continue;

      const ageMs = now - new Date(createdAt).getTime();
      const ageHours = Math.round(ageMs / (1000 * 60 * 60));

      if (ageHours >= 48) {
        bottlenecks.push({
          id: String(pr.id || pr.number || pr.pr_number),
          type: 'stale_pr',
          severity: ageHours >= 168 ? 'high' : ageHours >= 96 ? 'medium' : 'low',
          title: pr.title || `PR #${pr.number || pr.pr_number}`,
          detail: `Open for ${formatAge(ageHours)} — no merge / close action`,
          ageHours,
          author: pr.user?.login || pr.author || 'unknown',
          prNumber: pr.number || pr.pr_number,
        });
      }
    }

    // Sort most stale first
    bottlenecks.sort((a, b) => (b.ageHours ?? 0) - (a.ageHours ?? 0));
    return bottlenecks;
  },

  /**
   * Build workload distribution data (commits + PRs per contributor).
   */
  async fetchWorkload(projectId: string): Promise<WorkloadEntry[]> {
    const [commits, prs] = await Promise.all([
      dataSyncApi.getCommits(projectId, 200).catch(() => []),
      dataSyncApi.getPRs(projectId).catch(() => []),
    ]);

    const map = new Map<string, { commits: number; pullRequests: number }>();

    for (const c of commits) {
      const name = c.author?.login || c.author_name || c.author || 'unknown';
      const entry = map.get(name) || { commits: 0, pullRequests: 0 };
      entry.commits += 1;
      map.set(name, entry);
    }

    for (const pr of prs) {
      const name = pr.user?.login || pr.author || 'unknown';
      const entry = map.get(name) || { commits: 0, pullRequests: 0 };
      entry.pullRequests += 1;
      map.set(name, entry);
    }

    return Array.from(map.entries())
      .map(([contributor, data]) => ({ contributor, ...data }))
      .sort((a, b) => b.commits + b.pullRequests - (a.commits + a.pullRequests));
  },

  /**
   * Fetch open issues and compute inactivity days to surface stale ones.
   */
  async fetchStaleIssues(projectId: string): Promise<StaleIssueRow[]> {
    const issues = await dataSyncApi.getIssues(projectId, 'open');

    const now = Date.now();
    return issues
      .map((issue: any) => {
        const updatedAt = issue.updated_at || issue.updatedAt || issue.created_at || issue.createdAt;
        const inactiveDays = updatedAt
          ? Math.floor((now - new Date(updatedAt).getTime()) / (1000 * 60 * 60 * 24))
          : 0;

        return {
          id: String(issue.id || issue.number || issue.issue_number),
          issueNumber: issue.number || issue.issue_number || 0,
          title: issue.title || 'Untitled Issue',
          author: issue.user?.login || issue.author || 'unknown',
          labels: Array.isArray(issue.labels)
            ? issue.labels.map((l: any) => (typeof l === 'string' ? l : l.name || ''))
            : [],
          inactiveDays,
          lastUpdated: updatedAt || '',
          url: issue.html_url || issue.url,
        } as StaleIssueRow;
      })
      .sort((a, b) => b.inactiveDays - a.inactiveDays);
  },

  /**
   * Sprint velocity derived from milestones.
   */
  async fetchSprintVelocity(projectId: string): Promise<SprintVelocity[]> {
    const milestones = await dataSyncApi.getMilestones(projectId).catch(() => []);

    const now = Date.now();
    return milestones
      .filter((m: any) => m.state === 'open' || !m.state)
      .map((m: any) => {
        const total = (m.open_issues ?? 0) + (m.closed_issues ?? 0);
        const closed = m.closed_issues ?? 0;
        const dueDate = m.due_on || m.due_date || null;
        let daysRemaining: number | null = null;
        if (dueDate) {
          daysRemaining = Math.ceil((new Date(dueDate).getTime() - now) / (1000 * 60 * 60 * 24));
        }

        return {
          milestoneName: m.title || 'Untitled Sprint',
          totalIssues: total,
          closedIssues: closed,
          openIssues: m.open_issues ?? 0,
          completionPct: total > 0 ? Math.round((closed / total) * 100) : 0,
          dueDate,
          daysRemaining,
        } as SprintVelocity;
      });
  },
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatIndicatorLabel(key: string): string {
  const labels: Record<string, string> = {
    bottlenecks: 'Delivery Bottlenecks',
    workload: 'Workload Distribution',
    stale_issues: 'Stale Issues',
    schedule_risk: 'Schedule Risk',
  };
  return labels[key] || key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatAge(hours: number): string {
  if (hours < 24) return `${hours}h`;
  const days = Math.floor(hours / 24);
  return days === 1 ? '1 day' : `${days} days`;
}
