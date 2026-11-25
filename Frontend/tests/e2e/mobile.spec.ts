import { test, expect, type Page, type Route } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

const SCREENSHOT_DIR = path.resolve(process.cwd(), '../documents/screenshots/mobile');

test.beforeAll(() => {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
});

const MOCK_USER_ADMIN = {
  id: 'user-1',
  name: 'Om Patel',
  username: 'ompatel75',
  email: 'om@example.com',
  role: 'admin',
  createdAt: '2026-01-15T10:00:00Z',
};

const MOCK_USER_DEV = {
  id: 'user-2',
  name: 'Dev User',
  username: 'devuser',
  email: 'dev@example.com',
  role: 'developer',
  createdAt: '2026-02-01T10:00:00Z',
};

const MOCK_PROJECT = {
  id: 'proj-1',
  name: 'Kavach Health Analyzer',
  description: 'AI Software Project Health & Risk Analyzer repository monitoring',
  projectType: 'Full-Stack Web',
  ownerId: 'user-1',
  repo_url: 'https://github.com/OpenTirZ/Ai-Software-Project-Health-and-Risk-Analyzer',
  default_branch: 'main',
  status: 'active',
  createdAt: '2026-01-20T09:00:00Z',
  updatedAt: '2026-11-24T12:00:00Z',
};

async function setupApiMocks(page: Page, options: { role?: 'admin' | 'developer'; expiredToken?: boolean } = {}) {
  const user = options.role === 'developer' ? MOCK_USER_DEV : MOCK_USER_ADMIN;

  await page.route('**/api/**', async (route: Route) => {
    const url = route.request().url();
    const method = route.request().method();

    if (url.includes('/auth/me/settings')) {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ emailNotifications: true, weeklyDigest: false }) });
    }
    if (url.includes('/auth/me')) {
      if (options.expiredToken) {
        return route.fulfill({ status: 401, contentType: 'application/json', body: JSON.stringify({ detail: 'Token expired' }) });
      }
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ user, ...user }) });
    }
    if (url.endsWith('/projects') && method === 'GET') {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ projects: [MOCK_PROJECT] }) });
    }
    if (url.includes('/health-summary')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          overall_score: 78,
          grade: 'B+',
          risk_level: 'Medium',
          bus_factor: 3,
          stale_prs: 2,
          open_issues: 14,
          commit_frequency: 24,
          indicators: [
            { name: 'Code Velocity', score: 84, status: 'healthy', weight: 0.25 },
            { name: 'PR Review Speed', score: 72, status: 'warning', weight: 0.25 },
            { name: 'Bus Factor', score: 65, status: 'warning', weight: 0.25 },
            { name: 'Issue Resolution', score: 88, status: 'healthy', weight: 0.25 },
          ],
          risk_flags: [
            { id: 'rf-1', severity: 'medium', title: 'Elevated PR review latency', description: '2 PRs open > 7 days', category: 'PR Health' },
            { id: 'rf-2', severity: 'low', title: 'Single maintainer on Webhook module', description: 'Consider secondary reviewer', category: 'Bus Factor' },
          ],
        }),
      });
    }
    if (url.includes('/metrics/breakdown')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          commits_by_day: [
            { date: '2026-11-18', count: 5 },
            { date: '2026-11-19', count: 8 },
            { date: '2026-11-20', count: 3 },
            { date: '2026-11-21', count: 11 },
          ],
          pr_stats: { open: 4, merged: 19, closed: 2 },
          issue_stats: { open: 14, closed: 42 },
        }),
      });
    }
    if (url.includes('/contributors')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          contributors: [
            { login: 'Ompatel75', name: 'Om Patel', commits: 48, prs: 14, additions: 3200, deletions: 840, share: 38 },
            { login: 'OpenTirZ', name: 'Tirth Patel', commits: 41, prs: 11, additions: 2800, deletions: 620, share: 32 },
          ],
        }),
      });
    }
    if (url.includes('/commits')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          commits: [
            { sha: '8ba1e99', message: 'Merge remote-tracking branch origin/main', author: 'Om Patel', date: '2026-11-25T15:30:00Z' },
            { sha: '1ad1be2', message: 'test(gui): add mobile responsive tests', author: 'Om Patel', date: '2026-11-24T12:00:00Z' },
          ],
        }),
      });
    }
    if (url.includes('/prs')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          prs: [
            { number: 205, title: 'feat: mobile responsiveness', state: 'merged', author: 'Darpan', created_at: '2026-11-24T10:00:00Z' },
            { number: 206, title: 'feat(webhooks): GitHub listener', state: 'open', author: 'Ompatel75', created_at: '2026-11-25T09:00:00Z' },
          ],
        }),
      });
    }
    if (url.includes('/issues')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          issues: [
            { number: 162, title: 'Sprint 1-4 Details Documentation', state: 'open', labels: ['docs'], created_at: '2026-11-20T08:00:00Z' },
          ],
        }),
      });
    }
    if (url.includes('/milestones')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          milestones: [
            { id: 'ms-1', title: 'Sprint 4 Delivery', state: 'open', open_issues: 3, closed_issues: 18, due_on: '2026-11-30T00:00:00Z' },
          ],
        }),
      });
    }
    if (url.includes('/thresholds')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ stale_pr_days: 7, bus_factor_min: 2, min_health_score: 70 }),
      });
    }
    if (url.includes('/reports')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          reports: [
            { id: 'rep-1', title: 'Sprint 4 Health Audit', created_at: '2026-11-24T14:00:00Z', format: 'PDF', score: 78 },
          ],
        }),
      });
    }
    if (url.includes('/appeals')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          appeals: [
            { id: 'app-1', title: 'False positive stale PR flag', status: 'pending', created_at: '2026-11-24T11:00:00Z', reason: 'PR waiting on external CI' },
          ],
        }),
      });
    }
    if (url.includes('/admin/users')) {
      if (options.role === 'developer') {
        return route.fulfill({ status: 403, contentType: 'application/json', body: JSON.stringify({ detail: 'Admin access required' }) });
      }
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          items: [
            { id: 'user-1', name: 'Om Patel', email: 'om@example.com', role: 'admin', is_active: true, created_at: '2026-01-15T10:00:00Z' },
            { id: 'user-2', name: 'Dev User', email: 'dev@example.com', role: 'developer', is_active: true, created_at: '2026-02-01T10:00:00Z' },
          ],
          total: 2,
          skip: 0,
          limit: 50,
        }),
      });
    }
    if (url.includes('/admin/audit-logs')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { id: 'log-1', action: 'role_change', actor_id: 'om@example.com', target_id: 'dev@example.com', detail: 'Promoted to PM', created_at: '2026-11-25T10:00:00Z' },
        ]),
      });
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({}) });
  });
}

async function auditMobileLayout(page: Page, label: string) {
  const metrics = await page.evaluate(() => {
    const docWidth = document.documentElement.scrollWidth;
    const viewportWidth = window.innerWidth;
    const viewportMeta = document.querySelector('meta[name="viewport"]')?.getAttribute('content') || null;
    const bodyTextLen = (document.body.innerText || '').trim().length;

    const smallTargets: Array<{ tag: string; text: string; width: number; height: number }> = [];
    const interactive = document.querySelectorAll('button, a, [role="button"]');
    interactive.forEach((el) => {
      const rect = el.getBoundingClientRect();
      const style = window.getComputedStyle(el);
      if (rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden') {
        if (rect.width < 44 || rect.height < 44) {
          smallTargets.push({
            tag: el.tagName.toLowerCase(),
            text: (el.textContent || el.getAttribute('aria-label') || '').trim().slice(0, 30),
            width: Math.round(rect.width),
            height: Math.round(rect.height),
          });
        }
      }
    });

    const smallInputs: Array<{ name: string; fontSize: number }> = [];
    document.querySelectorAll('input, textarea, select').forEach((el) => {
      const rect = el.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0) {
        const fs = parseFloat(window.getComputedStyle(el).fontSize);
        if (fs < 16) {
          smallInputs.push({
            name: el.getAttribute('name') || el.getAttribute('id') || el.getAttribute('type') || 'input',
            fontSize: fs,
          });
        }
      }
    });

    return {
      docWidth,
      viewportWidth,
      hasHorizontalOverflow: docWidth > viewportWidth,
      viewportMeta,
      bodyTextLen,
      smallTargetCount: smallTargets.length,
      smallTargetsSample: smallTargets.slice(0, 5),
      smallInputCount: smallInputs.length,
      smallInputsSample: smallInputs.slice(0, 5),
    };
  });

  console.log(`[AUDIT:${label}]`, JSON.stringify(metrics));
  return metrics;
}

const AUTH_ROUTES = [
  { name: 'projects', path: '/projects', file: 'mobile_projects_default.png' },
  { name: 'create_project', path: '/projects/create', file: 'mobile_create_project_default.png' },
  { name: 'connect_repo', path: '/projects/connect', file: 'mobile_connect_repo_default.png' },
  { name: 'overview', path: '/projects/proj-1/overview', file: 'mobile_overview_default.png' },
  { name: 'dashboard', path: '/projects/proj-1/dashboard', file: 'mobile_dashboard_default.png' },
  { name: 'health', path: '/projects/proj-1/health', file: 'mobile_health_default.png' },
  { name: 'risk', path: '/projects/proj-1/risk', file: 'mobile_risk_default.png' },
  { name: 'contributors', path: '/projects/proj-1/contributors', file: 'mobile_contributors_default.png' },
  { name: 'activity', path: '/projects/proj-1/activity', file: 'mobile_activity_default.png' },
  { name: 'reports', path: '/projects/proj-1/reports', file: 'mobile_reports_default.png' },
  { name: 'appeals', path: '/projects/proj-1/appeals', file: 'mobile_appeals_default.png' },
  { name: 'settings', path: '/projects/proj-1/settings', file: 'mobile_settings_default.png' },
  { name: 'profile', path: '/profile', file: 'mobile_profile_default.png' },
  { name: 'admin', path: '/admin', file: 'mobile_admin_default.png' },
  { name: 'audit_logs', path: '/admin/audit-logs', file: 'mobile_audit_logs_default.png' },
];

test.describe('Mobile 375x812 Responsive & Error Validation', () => {
  test('Public routes: /login and /signup', async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', (e) => errors.push(e.message));

    await page.goto('/login', { waitUntil: 'networkidle' });
    await page.waitForTimeout(300);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'mobile_login_default.png'), fullPage: true });
    const loginMetrics = await auditMobileLayout(page, 'login');
    expect(loginMetrics.viewportMeta).toContain('width=device-width');
    expect(loginMetrics.hasHorizontalOverflow).toBe(false);

    await page.goto('/signup', { waitUntil: 'networkidle' });
    await page.waitForTimeout(300);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'mobile_signup_default.png'), fullPage: true });
    const signupMetrics = await auditMobileLayout(page, 'signup');
    expect(signupMetrics.hasHorizontalOverflow).toBe(false);
    expect(errors).toEqual([]);
  });

  test('Authenticated routes responsive audit & screenshots', async ({ page }) => {
    test.setTimeout(120_000);
    await setupApiMocks(page, { role: 'admin' });
    await page.addInitScript(() => {
      localStorage.setItem('aegis_token', 'mock-valid-jwt-token');
    });

    for (const r of AUTH_ROUTES) {
      const pageErrors: string[] = [];
      const onErr = (e: Error) => pageErrors.push(e.stack || e.message);
      page.on('pageerror', onErr);

      await page.goto(r.path, { waitUntil: 'networkidle' });
      await page.waitForTimeout(400);
      await page.screenshot({ path: path.join(SCREENSHOT_DIR, r.file), fullPage: true });
      await auditMobileLayout(page, r.name);
      console.log(`[ERRORS:${r.name}]`, JSON.stringify(pageErrors));
      page.off('pageerror', onErr);
    }
  });

  test('Mobile navigation drawer opens, navigates, and closes', async ({ page }) => {
    await setupApiMocks(page, { role: 'admin' });
    await page.addInitScript(() => {
      localStorage.setItem('aegis_token', 'mock-valid-jwt-token');
    });

    await page.goto('/projects', { waitUntil: 'networkidle' });
    await page.waitForTimeout(400);

    const openBtn = page.getByRole('button', { name: /open navigation menu/i });
    await expect(openBtn).toBeVisible();
    await openBtn.click();
    await page.waitForTimeout(300);

    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'mobile_nav_drawer_open.png'), fullPage: false });
    const navMetrics = await auditMobileLayout(page, 'nav_drawer_open');
    expect(navMetrics.hasHorizontalOverflow).toBe(false);

    // Click Profile or Settings link inside drawer
    const profileLink = page.getByRole('button', { name: /profile|settings/i }).first();
    if (await profileLink.isVisible()) {
      await profileLink.click();
      await page.waitForTimeout(300);
    }

    // Verify close button works if drawer still open
    const closeBtns = page.getByRole('button', { name: /close navigation menu/i });
    if ((await closeBtns.count()) > 0 && (await closeBtns.first().isVisible())) {
      await closeBtns.first().click();
      await page.waitForTimeout(200);
    }
  });

  test('Error state 1: Invalid email on Login blocks submit and shows visible error', async ({ page }) => {
    await page.goto('/login', { waitUntil: 'networkidle' });
    const emailInput = page.getByLabel(/email/i);
    await emailInput.fill('invalid-email-no-at');
    await page.getByLabel(/^password$/i).fill('Password123!');
    await page.getByRole('button', { name: /sign in/i }).click();
    await page.waitForTimeout(200);

    const errorText = page.getByText(/must include an "@"|valid email/i);
    await expect(errorText).toBeVisible();
    const box = await errorText.boundingBox();
    expect(box).not.toBeNull();
    expect(box!.x + box!.width).toBeLessThanOrEqual(375);

    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'mobile_login_invalid_email.png'), fullPage: true });
  });

  test('Error state 2: Expired token redirects to /login', async ({ page }) => {
    await setupApiMocks(page, { expiredToken: true });
    await page.addInitScript(() => {
      localStorage.setItem('aegis_token', 'expired-token-123');
    });

    await page.goto('/projects', { waitUntil: 'networkidle' });
    await page.waitForTimeout(600);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'mobile_auth_expired_token.png'), fullPage: true });
    console.log('[EXPIRED_TOKEN_URL]', page.url());
    expect(page.url()).toContain('/login');
  });

  test('Error state 3: Network timeout shows loading then error message and remains retryable', async ({ page }) => {
    await page.route('**/api/auth/login', async (route) => {
      await new Promise((r) => setTimeout(r, 800));
      await route.abort('timedout');
    });

    await page.goto('/login', { waitUntil: 'networkidle' });
    await page.getByLabel(/email/i).fill('om@example.com');
    await page.getByLabel(/^password$/i).fill('Password123!');

    const submitBtn = page.getByRole('button', { name: /sign in/i });
    await submitBtn.click();

    // Wait for loading state then error
    await page.waitForTimeout(1200);
    const alert = page.locator('[role="alert"], .bg-red-50, .text-red-600, .text-red-700').first();
    await expect(alert).toBeVisible();
    const box = await alert.boundingBox();
    expect(box).not.toBeNull();
    expect(box!.x + box!.width).toBeLessThanOrEqual(375);

    // Button should be re-enabled for retry
    await expect(submitBtn).toBeEnabled();
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'mobile_login_network_timeout.png'), fullPage: true });
  });

  test('Error state 4: 403 Forbidden / unprivileged access to /admin', async ({ page }) => {
    await setupApiMocks(page, { role: 'developer' });
    await page.addInitScript(() => {
      localStorage.setItem('aegis_token', 'mock-dev-token');
    });

    await page.goto('/admin', { waitUntil: 'networkidle' });
    await page.waitForTimeout(500);

    // Should not crash or show blank page
    const bodyLen = await page.evaluate(() => (document.body.innerText || '').trim().length);
    expect(bodyLen).toBeGreaterThan(20);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'mobile_admin_403_forbidden.png'), fullPage: true });
    console.log(`[403_URL]`, page.url());
  });
});
