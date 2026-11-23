/// <reference types="vitest/jsdom" />
import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { App } from '../App';
import { adminApi, authApi, projectApi, type User } from '../services/api';
import type { PageView } from '../types';

// The sidebar hides its admin button for non-admins. Send the same navigation
// request from a test page so the app's independent route guard is exercised.
vi.mock('../pages/Projects', () => ({
  Projects: ({ onNavigate }: { onNavigate: (view: PageView) => void }) => (
    <button onClick={() => onNavigate('admin')}>Request admin view</button>
  ),
}));

async function renderSession(role: 'developer' | 'project_manager' | 'admin') {
  vi.spyOn(authApi, 'getMe').mockResolvedValue({
    id: 'viewer',
    name: 'Signed-in user',
    username: 'viewer',
    email: 'viewer@example.com',
    role,
  });
  render(<App />);
  await screen.findByTitle('View profile (Signed-in user)');
  // Wait for the protected route to finish session restoration and render.
  await screen.findByRole('button', { name: 'Request admin view' });
}

beforeEach(() => {
  // BrowserRouter reads the current browser URL when App mounts. Reset it so
  // each test starts from the same protected entry route.
  window.history.replaceState({}, '', '/');
  vi.stubGlobal('localStorage', jsdom.window.localStorage);
  localStorage.setItem('aegis_token', 'test-session');
  vi.spyOn(projectApi, 'getProjects').mockResolvedValue([]);
});

afterEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe('admin access', () => {
  it.each(['developer', 'project_manager'] as const)(
    'redirects a %s requesting the admin view to the projects page',
    async (role) => {
      const user = userEvent.setup();
      vi.spyOn(window, 'alert').mockImplementation(() => {});
      const listUsers = vi.spyOn(adminApi, 'getUsers').mockResolvedValue({
        items: [], total: 0, skip: 0, limit: 50,
      });
      await renderSession(role);
      expect(screen.queryByRole('button', { name: 'Admin Panel' })).toBeNull();

      await user.click(screen.getByRole('button', { name: 'Request admin view' }));

      expect(screen.getByRole('button', { name: 'All Repositories', current: 'page' })).toBeVisible();
      expect(screen.queryByRole('heading', { name: 'Admin Panel' })).toBeNull();
      expect(listUsers).not.toHaveBeenCalled();
    },
  );

  it('keeps a cached admin role unprivileged until the session is verified', async () => {
    const user = userEvent.setup();
    localStorage.setItem('aegis_user', JSON.stringify({ fullName: 'Cached user', role: 'admin' }));
    let finishRestore!: (profile: User) => void;
    vi.spyOn(authApi, 'getMe').mockReturnValue(new Promise(resolve => { finishRestore = resolve; }));
    vi.spyOn(window, 'alert').mockImplementation(() => {});
    const listUsers = vi.spyOn(adminApi, 'getUsers').mockResolvedValue({
      items: [], total: 0, skip: 0, limit: 50,
    });
    render(<App />);

    // Cached role data must not render the protected page while verification
    // is pending, nor should it expose the admin navigation item.
    expect(screen.getByRole('status')).toHaveTextContent('Verifying your session');
    expect(screen.queryByRole('button', { name: 'Admin Panel' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Request admin view' })).toBeNull();
    expect(listUsers).not.toHaveBeenCalled();

    await act(async () => finishRestore({
      id: 'viewer', name: 'Verified admin', username: 'admin', email: 'admin@example.com', role: 'admin',
    }));
    await screen.findByRole('button', { name: 'Request admin view' });
    await user.click(screen.getByRole('button', { name: 'Admin Panel' }));
    expect(screen.getByRole('heading', { name: 'Admin Panel' })).toBeVisible();
    expect(listUsers).toHaveBeenCalled();
  });

  it('uses the new login role after an admin logs out', async () => {
    const user = userEvent.setup();
    vi.spyOn(authApi, 'logout').mockResolvedValue();
    vi.spyOn(window, 'alert').mockImplementation(() => {});
    await renderSession('admin');
    expect(screen.getByRole('button', { name: 'Admin Panel' })).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'Logout' }));

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json({
      access_token: 'new-session',
      user: { id: 'other', name: 'Other User', email: 'other@example.com', role: 'developer' },
    })));
    await user.type(screen.getByLabelText('Email address'), 'other@example.com');
    await user.type(screen.getByLabelText('Password', { exact: true }), 'test-password');
    await user.click(screen.getByRole('button', { name: 'Sign In' }));

    await screen.findByTitle('View profile (Other User)');
    expect(screen.queryByRole('button', { name: 'Admin Panel' })).toBeNull();
    await user.click(screen.getByRole('button', { name: 'Request admin view' }));
    expect(screen.getByRole('button', { name: 'All Repositories', current: 'page' })).toBeVisible();
  });

  it('shows a dismissible error toast and keeps the original role after a 403', async () => {
    const user = userEvent.setup();
    const target = {
      id: 'target', name: 'Team Member', email: 'member@example.com',
      role: 'developer', is_active: true, created_at: '2026-01-01',
    };
    const detail = 'You do not have permission to perform this action.';
    const fetchMock = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(Response.json({ items: [target], total: 1, skip: 0, limit: 50 }))
      .mockResolvedValueOnce(Response.json({ detail }, { status: 403 }));
    vi.stubGlobal('fetch', fetchMock);
    await renderSession('admin');
    await user.click(screen.getByRole('button', { name: 'Admin Panel' }));
    const row = await screen.findByRole('row', { name: /member@example.com/i });
    const role = within(row).getByRole('combobox');

    await user.selectOptions(role, 'admin');

    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/admin/users/target/role'), {
      method: 'PATCH',
      headers: expect.objectContaining({ Authorization: 'Bearer test-session' }),
      body: JSON.stringify({ role: 'admin' }),
    });
    const toast = await screen.findByRole('alert');
    expect(toast).toBeVisible();
    expect(toast).toHaveTextContent(detail);
    expect(role).toHaveValue('developer');

    await user.click(within(toast).getByRole('button', { name: 'Dismiss' }));
    expect(screen.queryByRole('alert')).toBeNull();
  });
});
