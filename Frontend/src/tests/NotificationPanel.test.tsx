import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { TopBar } from '../components/TopBar';
import { metricsApi, type HealthSummaryData, type ProjectResponse } from '../services/api';

const projects: ProjectResponse[] = [
  {
    id: 'p1',
    name: 'Alpha',
    description: '',
    repo_url: 'https://github.com/org/alpha',
    createdAt: '2026-01-01T00:00:00Z',
  },
  {
    id: 'p2',
    name: 'Beta',
    description: '',
    createdAt: '2026-01-01T00:00:00Z',
  },
];

const summary: HealthSummaryData = {
  project_id: 'p1',
  project_name: 'Alpha',
  health_score: 60,
  status: 'Caution',
  last_synced_at: '2026-11-22T10:00:00Z',
  data_freshness: 'fresh',
  data_availability: {},
  summary_statement: '',
  flags_count: { total: 2, high: 1, medium: 1, low: 0 },
  active_flags: [
    { id: 'f1', type: 'stale_issues', severity: 'medium', message: 'Twelve issues inactive' },
    { id: 'f2', type: 'workload', severity: 'high', message: 'One contributor dominates' },
  ],
  evaluated_at: new Date().toISOString(),
};

function renderTopBar(overrides: Partial<React.ComponentProps<typeof TopBar>> = {}) {
  const props = {
    currentView: 'overview' as const,
    projects,
    activeProject: projects[0],
    currentUser: { fullName: 'Varshil Shah', username: '@varshil', email: 'v@example.com' },
    onNavigate: vi.fn(),
    onSelectProject: vi.fn(),
    ...overrides,
  };
  render(<TopBar {...props} />);
  return props;
}

beforeEach(() => {
  vi.stubGlobal('localStorage', jsdom.window.localStorage);
  vi.spyOn(metricsApi, 'getHealthSummary').mockResolvedValue(summary);
});

afterEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe('notification panel', () => {
  it('opens a dropdown instead of navigating to the profile page', async () => {
    const user = userEvent.setup();
    const props = renderTopBar();

    await user.click(await screen.findByRole('button', { name: /Notifications, 2 unread/i }));

    expect(await screen.findByRole('dialog', { name: 'Notifications' })).toBeInTheDocument();
    expect(props.onNavigate).not.toHaveBeenCalled();
  });

  it('lists real risk flags with the highest severity first and only queries connected projects', async () => {
    const user = userEvent.setup();
    renderTopBar();

    await user.click(await screen.findByRole('button', { name: /Notifications/i }));
    const dialog = await screen.findByRole('dialog', { name: 'Notifications' });
    const items = await within(dialog).findAllByRole('listitem');

    expect(items[0]).toHaveTextContent('One contributor dominates');
    expect(items[1]).toHaveTextContent('Twelve issues inactive');
    const queried = vi.mocked(metricsApi.getHealthSummary).mock.calls.map(([id]) => id);
    expect(queried.length).toBeGreaterThan(0);
    expect(new Set(queried)).toEqual(new Set(['p1']));
  });

  it('marks a notification as read, updates the unread count and persists it', async () => {
    const user = userEvent.setup();
    const props = renderTopBar();

    await user.click(await screen.findByRole('button', { name: /Notifications, 2 unread/i }));
    await user.click(await screen.findByText('One contributor dominates'));

    expect(props.onSelectProject).toHaveBeenCalledWith('p1');
    expect(props.onNavigate).toHaveBeenCalledWith('risk-analysis');
    expect(localStorage.getItem('aegis_read_notifications:@varshil')).toContain('workload');

    expect(await screen.findByRole('button', { name: /Notifications, 1 unread/i })).toBeInTheDocument();
  });

  it('marks all notifications as read', async () => {
    const user = userEvent.setup();
    renderTopBar();

    await user.click(await screen.findByRole('button', { name: /Notifications, 2 unread/i }));
    await user.click(await screen.findByRole('button', { name: /Mark all read/i }));

    expect(await screen.findByRole('button', { name: 'Notifications' })).toBeInTheDocument();
    expect(screen.getByText('You are all caught up')).toBeInTheDocument();
  });

  it('closes on Escape and on outside click', async () => {
    const user = userEvent.setup();
    renderTopBar();

    await user.click(await screen.findByRole('button', { name: /Notifications/i }));
    expect(await screen.findByRole('dialog')).toBeInTheDocument();

    await user.keyboard('{Escape}');
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());

    await user.click(screen.getByRole('button', { name: /Notifications/i }));
    expect(await screen.findByRole('dialog')).toBeInTheDocument();
    await user.click(document.body);
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  });

  it('shows an empty state when there are no active flags', async () => {
    const user = userEvent.setup();
    vi.spyOn(metricsApi, 'getHealthSummary').mockResolvedValue({ ...summary, active_flags: [] });
    renderTopBar();

    await user.click(await screen.findByRole('button', { name: 'Notifications' }));
    expect(await screen.findByText('No notifications')).toBeInTheDocument();
  });

  it('keeps the profile button working independently', async () => {
    const user = userEvent.setup();
    const props = renderTopBar();

    await user.click(screen.getByRole('button', { name: 'View user profile' }));

    expect(props.onNavigate).toHaveBeenCalledWith('profile');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
});
