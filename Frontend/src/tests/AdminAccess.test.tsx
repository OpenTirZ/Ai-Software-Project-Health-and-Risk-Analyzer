/// <reference types="vitest/jsdom" />
import { act, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { App } from '../App';
import { AdminPanel } from '../pages/AdminPanel';
import { adminApi, authApi, projectApi } from '../services/api';
import type { PageView } from '../types';

// The real sidebar hides the admin link. Supply a second navigation source
// so a non-admin request actually reaches App's navigation guard.
vi.mock('../components/TopBar', () => ({
  TopBar: ({ onNavigate }: { onNavigate: (view: PageView) => void }) => (
    <button onClick={() => onNavigate('admin')}>Request admin view</button>
  ),
}));

beforeEach(() => {
  vi.stubGlobal('localStorage', jsdom.window.localStorage);
});

afterEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

async function openSession(role: string) {
  localStorage.setItem('aegis_token', 'session-token');
  vi.spyOn(authApi, 'getMe').mockResolvedValue({
    id: 'viewer', name: 'Session User', username: 'viewer',
    email: 'viewer@example.com', role, createdAt: '',
  });
  const projects = vi.spyOn(projectApi, 'getProjects').mockResolvedValue([]);
  render(<App />);
  await waitFor(() => expect(projects).toHaveBeenCalled());
}

describe('admin navigation', () => {
  it('withholds cached admin access while the server verifies the session', async () => {
    localStorage.setItem('aegis_token', 'unverified-session');
    localStorage.setItem('aegis_user', JSON.stringify({ fullName: 'Previous Admin', role: 'admin' }));
    vi.spyOn(authApi, 'getMe').mockReturnValue(new Promise(() => {}));
    vi.spyOn(window, 'alert').mockImplementation(() => {});
    const loadUsers = vi.spyOn(adminApi, 'getUsers');
    const user = userEvent.setup();
    render(<App />);

    expect(screen.queryByRole('button', { name: 'Admin Panel' })).toBeNull();
    await user.click(screen.getByRole('button', { name: 'Request admin view' }));
    expect(await screen.findByRole('heading', { name: 'No Project Selected' })).toBeVisible();
    expect(loadUsers).not.toHaveBeenCalled();
  });

  it.each(['developer', 'project_manager'])('redirects a %s session to overview', async (role) => {
    const user = userEvent.setup();
    const loadUsers = vi.spyOn(adminApi, 'getUsers');
    vi.spyOn(window, 'alert').mockImplementation(() => {});
    await openSession(role);

    expect(screen.queryByRole('button', { name: 'Admin Panel' })).toBeNull();
    await user.click(screen.getByRole('button', { name: 'Request admin view' }));
    expect(await screen.findByRole('heading', { name: 'No Project Selected' })).toBeVisible();
    expect(screen.queryByRole('heading', { name: 'Admin Panel' })).toBeNull();
    expect(loadUsers).not.toHaveBeenCalled();
  });

  it('opens the admin directory from the sidebar for an admin session', async () => {
    const user = userEvent.setup();
    const loadUsers = vi.spyOn(adminApi, 'getUsers').mockResolvedValue({
      items: [], total: 0, skip: 0, limit: 50,
    });
    await openSession('admin');

    await user.click(screen.getByRole('button', { name: 'Admin Panel' }));
    expect(await screen.findByRole('heading', { name: 'Admin Panel' })).toBeVisible();
    expect(loadUsers).toHaveBeenCalled();
  });

  it.each(['before logout', 'after login'])('keeps the new session when the old profile arrives %s', async (timing) => {
    const user = userEvent.setup();
    localStorage.setItem('aegis_token', 'old-admin-token');
    let finishProfile!: (response: Response) => void;
    let finishLogout!: (response: Response) => void;
    const profile = new Promise<Response>((resolve) => { finishProfile = resolve; });
    const logout = new Promise<Response>((resolve) => { finishLogout = resolve; });
    const oldProfile = Response.json({ id: 'old', name: 'Previous Admin', email: 'old@example.com', role: 'admin' });
    vi.stubGlobal('fetch', vi.fn()
      .mockResolvedValueOnce(profile)
      .mockResolvedValueOnce(logout)
      .mockResolvedValueOnce(Response.json({
        access_token: 'developer-token',
        user: { id: 'dev', name: 'Next User', email: 'next@example.com', role: 'developer' },
      })));
    vi.spyOn(projectApi, 'getProjects').mockResolvedValue([]);
    vi.spyOn(window, 'alert').mockImplementation(() => {});
    render(<App />);
    if (timing === 'before logout') {
      await act(async () => finishProfile(oldProfile));
      expect(screen.getByRole('button', { name: 'Admin Panel' })).toBeVisible();
    }
    await user.click(screen.getByRole('button', { name: 'Logout' }));
    await user.type(screen.getByPlaceholderText('xyz@gmail.com'), 'next@example.com');
    await user.type(screen.getByPlaceholderText('Enter your password'), 'FixturePassword1!');
    await user.click(screen.getByRole('button', { name: 'Sign In' }));

    expect(await screen.findByRole('heading', { name: 'Projects & Repositories' })).toBeVisible();
    await act(async () => {
      if (timing === 'after login') finishProfile(oldProfile);
      finishLogout(Response.json({ message: 'Logged out' }));
    });
    expect(localStorage.getItem('aegis_token')).toBe('developer-token');
    expect(screen.queryByRole('button', { name: 'Admin Panel' })).toBeNull();
    await user.click(screen.getByRole('button', { name: 'Request admin view' }));
    expect(await screen.findByRole('heading', { name: 'No Project Selected' })).toBeVisible();
  });
});

const denied = 'You do not have permission to perform this action.';

function forbiddenResponse() {
  return Response.json({ detail: denied }, { status: 403 });
}

describe('admin API permission errors', () => {
  it('announces a denied directory request in a dismissible error toast', async () => {
    const user = userEvent.setup();
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(forbiddenResponse()));
    render(<AdminPanel />);

    const toast = await screen.findByRole('alert');
    expect(toast).toHaveTextContent(denied);
    expect(toast).toBeVisible();
    await user.click(within(toast).getByRole('button', { name: 'Dismiss error' }));
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it.each(['role', 'deactivate'] as const)('keeps the row intact after a forbidden %s request', async (action) => {
    const user = userEvent.setup();
    localStorage.setItem('aegis_token', 'session-token');
    const target = {
      id: 'target', name: 'Example Developer', email: 'dev@example.com',
      role: 'developer', is_active: true, created_at: '',
    };
    const request = vi.fn()
      .mockResolvedValueOnce(Response.json({ items: [target], total: 1, skip: 0, limit: 50 }))
      .mockResolvedValueOnce(forbiddenResponse());
    vi.stubGlobal('fetch', request);
    render(<AdminPanel />);

    const row = within(await screen.findByRole('row', { name: /Example Developer/ }));
    const roles = row.getByRole('combobox');
    if (action === 'role') {
      await user.selectOptions(roles, 'admin');
    } else {
      await user.click(row.getByRole('button', { name: 'Deactivate' }));
    }

    expect(await screen.findByRole('alert')).toHaveTextContent(denied);
    expect(request).toHaveBeenLastCalledWith(
      expect.stringContaining(`/admin/users/target/${action}`),
      expect.objectContaining({
        method: action === 'role' ? 'PATCH' : 'POST',
        headers: expect.objectContaining({ Authorization: 'Bearer session-token' }),
      }),
    );
    expect(roles).toHaveValue('developer');
    expect(row.getByText('Active')).toBeVisible();
    expect(row.getByRole('button', { name: 'Deactivate' })).toBeEnabled();
  });
});
