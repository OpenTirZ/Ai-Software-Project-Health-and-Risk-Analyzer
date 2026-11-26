import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { Layout } from '../components/Layout';
import { Sidebar } from '../components/Sidebar';
import { TopBar } from '../components/TopBar';
import { Login } from '../pages/Login';
import { SignUp } from '../pages/SignUp';
import { authApi } from '../services/api';

vi.mock('../services/api', () => ({
  authApi: {
    login: vi.fn(),
    signup: vi.fn(),
    getMe: vi.fn(),
  },
  verifyEmailDomain: vi.fn().mockReturnValue({ isValid: true }),
}));

describe('Mobile (375px) Responsive Layout & Drawer Navigation Tests', () => {
  const mockNavigate = vi.fn();
  const mockLogout = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('1. Mobile Sidebar defaults to desktop-only (hidden md:flex) with no mobile drawer when isOpen is false', () => {
    const { container } = render(
      <Sidebar
        currentView="overview"
        onNavigate={mockNavigate}
        onLogout={mockLogout}
        isOpen={false}
      />
    );
    const aside = container.querySelector('aside');
    expect(aside).toHaveClass('hidden');
    expect(aside).toHaveClass('md:flex');
    expect(screen.queryByRole('dialog', { name: /navigation drawer/i })).not.toBeInTheDocument();
  });

  it('2. Mobile Sidebar renders accessible navigation drawer dialog when isOpen is true', () => {
    render(
      <Sidebar
        currentView="overview"
        onNavigate={mockNavigate}
        onLogout={mockLogout}
        isOpen={true}
      />
    );
    const drawer = screen.getByRole('dialog', { name: /navigation drawer/i });
    expect(drawer).toBeInTheDocument();
    expect(drawer).toHaveClass('transition-transform');
  });

  it('3. TopBar renders mobile hamburger button (md:hidden) with accessible aria-label', () => {
    const mockOpenMenu = vi.fn();
    render(
      <TopBar
        currentView="overview"
        onNavigate={mockNavigate}
        onOpenMenu={mockOpenMenu}
      />
    );

    const hamburgerBtn = screen.getByRole('button', { name: /open navigation menu/i });
    expect(hamburgerBtn).toBeInTheDocument();
    expect(hamburgerBtn).toHaveClass('md:hidden');

    fireEvent.click(hamburgerBtn);
    expect(mockOpenMenu).toHaveBeenCalledTimes(1);
  });

  it('4. Layout renders backdrop overlay on mobile when menu is opened and clicking it closes the drawer', () => {
    render(
      <Layout currentView="overview" onNavigate={mockNavigate} onLogout={mockLogout}>
        <div>Main Dashboard Content</div>
      </Layout>
    );

    // Initial state: drawer & backdrop are not in the DOM
    expect(screen.queryByLabelText(/close navigation menu/i)).not.toBeInTheDocument();

    // Click mobile hamburger menu in TopBar
    const hamburgerBtn = screen.getByRole('button', { name: /open navigation menu/i });
    fireEvent.click(hamburgerBtn);

    // Backdrop overlay and close button are now visible
    const closeButtons = screen.getAllByLabelText(/close navigation menu/i);
    const backdropBtn = closeButtons[0];
    expect(backdropBtn).toBeInTheDocument();
    expect(backdropBtn).toHaveClass('md:hidden');

    // Clicking backdrop closes drawer
    fireEvent.click(backdropBtn);
    expect(screen.queryByLabelText(/close navigation menu/i)).not.toBeInTheDocument();
  });
});

describe('Form & Error State Validation (Mobile & Negative Scenarios)', () => {
  const mockNavigate = vi.fn();
  const mockLoginSuccess = vi.fn();
  const mockSignUpSuccess = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('5. Login: displays error on invalid email format', async () => {
    render(<Login onNavigate={mockNavigate} onLoginSuccess={mockLoginSuccess} />);

    const emailInput = screen.getByLabelText(/email/i);
    const passwordInput = screen.getByLabelText(/^password$/i);
    const submitBtn = screen.getByRole('button', { name: /sign in/i });

    fireEvent.change(emailInput, { target: { value: 'not-an-email' } });
    fireEvent.change(passwordInput, { target: { value: 'Password123!' } });
    fireEvent.click(submitBtn);

    expect(emailInput).toBeInvalid();
    expect(authApi.login).not.toHaveBeenCalled();
  });

  it('6. Login: displays negative alert on 401 Unauthorized / Bad Credentials', async () => {
    vi.mocked(authApi.login).mockRejectedValueOnce(new Error('Invalid email or password'));

    render(<Login onNavigate={mockNavigate} onLoginSuccess={mockLoginSuccess} />);

    const emailInput = screen.getByLabelText(/email/i);
    const passwordInput = screen.getByLabelText(/^password$/i);
    const submitBtn = screen.getByRole('button', { name: /sign in/i });

    fireEvent.change(emailInput, { target: { value: 'user@example.com' } });
    fireEvent.change(passwordInput, { target: { value: 'WrongPassword!' } });
    fireEvent.click(submitBtn);

    const errorAlert = await screen.findByText(/invalid email or password/i);
    expect(errorAlert).toBeInTheDocument();
    expect(mockLoginSuccess).not.toHaveBeenCalled();
  });

  it('7. Login: handles network timeout / server unavailable gracefully', async () => {
    vi.mocked(authApi.login).mockRejectedValueOnce(new Error('Network Error: Failed to fetch'));

    render(<Login onNavigate={mockNavigate} onLoginSuccess={mockLoginSuccess} />);

    const emailInput = screen.getByLabelText(/email/i);
    const passwordInput = screen.getByLabelText(/^password$/i);
    const submitBtn = screen.getByRole('button', { name: /sign in/i });

    fireEvent.change(emailInput, { target: { value: 'user@example.com' } });
    fireEvent.change(passwordInput, { target: { value: 'Password123!' } });
    fireEvent.click(submitBtn);

    const errorAlert = await screen.findByText(/network error|failed to fetch|error/i);
    expect(errorAlert).toBeInTheDocument();
  });

  it('8. SignUp: rejects password confirmation mismatch with inline error', async () => {
    render(<SignUp onNavigate={mockNavigate} onSignUpSuccess={mockSignUpSuccess} />);

    fireEvent.change(screen.getByLabelText(/full name/i), { target: { value: 'Test User' } });
    fireEvent.change(screen.getByLabelText(/email address/i), { target: { value: 'test@example.com' } });
    fireEvent.change(screen.getByLabelText(/^password$/i), { target: { value: 'SecurePassword123!' } });
    fireEvent.change(screen.getByLabelText(/confirm password/i), { target: { value: 'DifferentPassword123!' } });

    fireEvent.click(screen.getByRole('button', { name: /create account/i }));

    const errorMsg = await screen.findByText(/passwords do not match/i);
    expect(errorMsg).toBeInTheDocument();
    expect(authApi.signup).not.toHaveBeenCalled();
  });
});
