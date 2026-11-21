import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import React from 'react';
import { UserProfile } from '../pages/UserProfile';
import { settingsApi, type ProjectResponse, type NotificationPreferences } from '../services/api';

// Mock settingsApi
vi.mock('../services/api', async () => {
  const actual = await vi.importActual('../services/api');
  return {
    ...actual,
    settingsApi: {
      getNotificationPreferences: vi.fn(),
      updateNotificationPreferences: vi.fn(),
    },
  };
});

describe('UserProfile Component', () => {
  const mockLogout = vi.fn();
  const mockNavigate = vi.fn();
  const mockUpdateProfile = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    (settingsApi.getNotificationPreferences as any).mockResolvedValue({
      high_risk_threshold: true,
      weekly_digest: true,
    });
  });

  // -------------------------------------------------------------------------
  // 1. Dynamic Repository Count Tests
  // -------------------------------------------------------------------------
  it('renders repository count as 0 when projects list is empty', async () => {
    render(
      <UserProfile
        onLogout={mockLogout}
        onNavigate={mockNavigate}
        projects={[]}
        loadingProjects={false}
      />
    );

    const kpiText = screen.getByText('REPOSITORIES MONITORED');
    expect(kpiText).toBeInTheDocument();
    // In the banner KPI container, the count should be 0
    const countEl = kpiText.nextElementSibling;
    expect(countEl).toHaveTextContent('0');
  });

  it('renders live count of connected repositories having repo_url', async () => {
    const mockProjects: ProjectResponse[] = [
      {
        id: '1',
        name: 'Project 1',
        description: '',
        repo_url: 'https://github.com/org/repo-1',
        createdAt: '2026-01-01',
      },
      {
        id: '2',
        name: 'Project 2',
        description: '',
        repo_url: undefined, // not connected
        createdAt: '2026-01-01',
      },
      {
        id: '3',
        name: 'Project 3',
        description: '',
        repo_url: 'https://github.com/org/repo-3',
        createdAt: '2026-01-01',
      },
    ];

    render(
      <UserProfile
        onLogout={mockLogout}
        onNavigate={mockNavigate}
        projects={mockProjects}
        loadingProjects={false}
      />
    );

    const kpiText = screen.getByText('REPOSITORIES MONITORED');
    expect(kpiText.nextElementSibling).toHaveTextContent('2');
  });

  it('renders dash placeholder when loadingProjects is true', async () => {
    render(
      <UserProfile
        onLogout={mockLogout}
        onNavigate={mockNavigate}
        projects={[]}
        loadingProjects={true}
      />
    );

    const kpiText = screen.getByText('REPOSITORIES MONITORED');
    expect(kpiText.nextElementSibling).toHaveTextContent('—');
  });

  // -------------------------------------------------------------------------
  // 2. Webhook Security UI Tests
  // -------------------------------------------------------------------------
  it('displays honest "Not configured" state and no fake credentials on Security tab', async () => {
    const user = userEvent.setup();
    render(
      <UserProfile
        onLogout={mockLogout}
        onNavigate={mockNavigate}
        projects={[]}
      />
    );

    // Switch to Security tab
    const securityTab = screen.getByRole('button', { name: /Security & API Keys/i });
    await user.click(securityTab);

    // Verify "Not configured" badge is displayed
    expect(screen.getByText('Not configured')).toBeInTheDocument();

    // Verify no fake key substring appears anywhere
    expect(screen.queryByText(/aegis_sec_/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/391f/i)).not.toBeInTheDocument();

    // Verify Regenerate button is disabled
    const regenBtn = screen.getByRole('button', { name: /Regenerate/i });
    expect(regenBtn).toBeDisabled();
  });

  it('allows navigation to projects from Security tab repository connection row', async () => {
    const user = userEvent.setup();
    render(
      <UserProfile
        onLogout={mockLogout}
        onNavigate={mockNavigate}
        projects={[]}
      />
    );

    const securityTab = screen.getByRole('button', { name: /Security & API Keys/i });
    await user.click(securityTab);

    const viewProjectsBtn = screen.getByRole('button', { name: /View Projects/i });
    await user.click(viewProjectsBtn);

    expect(mockNavigate).toHaveBeenCalledWith('projects');
  });

  // -------------------------------------------------------------------------
  // 3. Notification Persistence & Concurrency Tests
  // -------------------------------------------------------------------------
  it('loads notification preferences on mount and populates checkboxes', async () => {
    const user = userEvent.setup();
    (settingsApi.getNotificationPreferences as any).mockResolvedValue({
      high_risk_threshold: false,
      weekly_digest: true,
    });

    render(
      <UserProfile
        onLogout={mockLogout}
        onNavigate={mockNavigate}
      />
    );

    const notifTab = screen.getByRole('button', { name: /Notifications/i });
    await user.click(notifTab);

    const checkboxes = screen.getAllByRole('checkbox') as HTMLInputElement[];
    expect(checkboxes[0].checked).toBe(false);
    expect(checkboxes[1].checked).toBe(true);
  });

  it('displays load warning banner if initial preferences fetch fails', async () => {
    const user = userEvent.setup();
    (settingsApi.getNotificationPreferences as any).mockRejectedValue(new Error('Network error'));

    render(
      <UserProfile
        onLogout={mockLogout}
        onNavigate={mockNavigate}
      />
    );

    const notifTab = screen.getByRole('button', { name: /Notifications/i });
    await user.click(notifTab);

    await waitFor(() => {
      expect(screen.getByText(/Could not load preferences from server/i)).toBeInTheDocument();
    });
  });

  it('toggles preference and saves with partial update payload', async () => {
    const user = userEvent.setup();
    (settingsApi.getNotificationPreferences as any).mockResolvedValue({
      high_risk_threshold: true,
      weekly_digest: true,
    });
    (settingsApi.updateNotificationPreferences as any).mockResolvedValue({
      high_risk_threshold: false,
      weekly_digest: true,
    });

    render(
      <UserProfile
        onLogout={mockLogout}
        onNavigate={mockNavigate}
      />
    );

    const notifTab = screen.getByRole('button', { name: /Notifications/i });
    await user.click(notifTab);

    const checkboxes = screen.getAllByRole('checkbox') as HTMLInputElement[];
    await user.click(checkboxes[0]);

    expect(settingsApi.updateNotificationPreferences).toHaveBeenCalledWith({
      high_risk_threshold: false,
    });

    await waitFor(() => {
      expect(screen.getByText(/Saved ✓/i)).toBeInTheDocument();
    });
  });

  it('rolls back preference to confirmed server state when save fails', async () => {
    const user = userEvent.setup();
    (settingsApi.getNotificationPreferences as any).mockResolvedValue({
      high_risk_threshold: true,
      weekly_digest: true,
    });
    (settingsApi.updateNotificationPreferences as any).mockRejectedValue(new Error('Server error'));

    render(
      <UserProfile
        onLogout={mockLogout}
        onNavigate={mockNavigate}
      />
    );

    const notifTab = screen.getByRole('button', { name: /Notifications/i });
    await user.click(notifTab);

    const checkboxes = screen.getAllByRole('checkbox') as HTMLInputElement[];
    expect(checkboxes[0].checked).toBe(true);

    await user.click(checkboxes[0]);

    await waitFor(() => {
      expect(screen.getByText(/Unable to save preference/i)).toBeInTheDocument();
    });

    // Rolled back to true
    expect(checkboxes[0].checked).toBe(true);
  });
});
