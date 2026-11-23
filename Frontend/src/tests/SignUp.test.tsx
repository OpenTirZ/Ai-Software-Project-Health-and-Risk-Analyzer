import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import { SignUp } from '../pages/SignUp';
import { authApi } from '../services/api';

vi.mock('../services/api', () => {
  return {
    authApi: {
      signup: vi.fn(),
      login: vi.fn(),
    },
    verifyEmailDomain: vi.fn().mockReturnValue({ isValid: true }),
  };
});

describe('SignUp Component — Password Whitespace Validation', () => {
  const mockNavigate = vi.fn();
  const mockSignUpSuccess = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  const fillForm = ({
    name = 'Alice Johnson',
    email = 'alice@example.com',
    password = 'SecurePassword123!',
    confirmPassword = 'SecurePassword123!',
  } = {}) => {
    const nameInput = screen.getByLabelText(/Full name/i);
    const emailInput = screen.getByLabelText(/Email address/i);
    const passwordInput = screen.getByLabelText(/^Password$/i);
    const confirmPasswordInput = screen.getByLabelText(/Confirm password/i);

    fireEvent.change(nameInput, { target: { value: name } });
    fireEvent.change(emailInput, { target: { value: email } });
    fireEvent.change(passwordInput, { target: { value: password } });
    fireEvent.change(confirmPasswordInput, { target: { value: confirmPassword } });
  };

  it('1. rejects a password containing an internal space and displays the expected inline error', async () => {
    render(<SignUp onNavigate={mockNavigate} onSignUpSuccess={mockSignUpSuccess} />);
    fillForm({ password: 'Secure Pass123!', confirmPassword: 'Secure Pass123!' });

    const submitButton = screen.getByRole('button', { name: /create account/i });
    fireEvent.click(submitButton);

    const errorMessage = await screen.findByText('Password must not contain spaces or whitespace characters.');
    expect(errorMessage).toBeInTheDocument();
    expect(authApi.signup).not.toHaveBeenCalled();
  });

  it('2. rejects leading and trailing spaces', async () => {
    render(<SignUp onNavigate={mockNavigate} onSignUpSuccess={mockSignUpSuccess} />);

    // Test trailing space
    fillForm({ password: 'SecurePassword123! ', confirmPassword: 'SecurePassword123! ' });
    const submitButton = screen.getByRole('button', { name: /create account/i });
    fireEvent.click(submitButton);

    expect(await screen.findByText('Password must not contain spaces or whitespace characters.')).toBeInTheDocument();
    expect(authApi.signup).not.toHaveBeenCalled();

    // Test leading space
    fillForm({ password: ' SecurePassword123!', confirmPassword: ' SecurePassword123!' });
    fireEvent.click(submitButton);

    expect(await screen.findByText('Password must not contain spaces or whitespace characters.')).toBeInTheDocument();
    expect(authApi.signup).not.toHaveBeenCalled();
  });

  it('3. rejects tabs and representative Unicode whitespace characters (NBSP, em space, ideographic space)', async () => {
    const testWhitespaceVariants = [
      { pw: 'SecurePass123!\t', desc: 'tab' },
      { pw: 'Secure\u00a0Pass123!', desc: 'non-breaking space' },
      { pw: 'Secure\u2003Pass123!', desc: 'em space' },
      { pw: 'Secure\u3000Pass123!', desc: 'ideographic space' },
    ];

    for (const { pw } of testWhitespaceVariants) {
      const { unmount } = render(<SignUp onNavigate={mockNavigate} onSignUpSuccess={mockSignUpSuccess} />);
      fillForm({ password: pw, confirmPassword: pw });

      const submitButton = screen.getByRole('button', { name: /create account/i });
      fireEvent.click(submitButton);

      expect(await screen.findByText('Password must not contain spaces or whitespace characters.')).toBeInTheDocument();
      expect(authApi.signup).not.toHaveBeenCalled();
      unmount();
    }
  });

  it('4. blocks submission and does not call authApi.signup for an invalid password', async () => {
    render(<SignUp onNavigate={mockNavigate} onSignUpSuccess={mockSignUpSuccess} />);
    fillForm({ password: 'Bad Password 123!', confirmPassword: 'Bad Password 123!' });

    const submitButton = screen.getByRole('button', { name: /create account/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText('Password must not contain spaces or whitespace characters.')).toBeInTheDocument();
    });
    expect(authApi.signup).not.toHaveBeenCalled();
  });

  it('5. exposes correct accessibility error attributes on the password input when invalid', async () => {
    render(<SignUp onNavigate={mockNavigate} onSignUpSuccess={mockSignUpSuccess} />);
    fillForm({ password: 'Space Pass 123!', confirmPassword: 'Space Pass 123!' });

    const passwordInput = screen.getByLabelText(/^Password$/i);
    expect(passwordInput).toHaveAttribute('aria-invalid', 'false');

    const submitButton = screen.getByRole('button', { name: /create account/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(passwordInput).toHaveAttribute('aria-invalid', 'true');
      expect(passwordInput).toHaveAttribute('aria-describedby', 'signup-password-error');
    });

    const errorEl = document.getElementById('signup-password-error');
    expect(errorEl).not.toBeNull();
    expect(errorEl).toHaveTextContent('Password must not contain spaces or whitespace characters.');
  });

  it('6. accepts a valid password of at least 8 characters without whitespace', async () => {
    (authApi.signup as any).mockResolvedValue({
      token: 'mock-jwt-token',
      user: { id: 'usr_123', email: 'alice@example.com', name: 'Alice Johnson' },
    });

    render(<SignUp onNavigate={mockNavigate} onSignUpSuccess={mockSignUpSuccess} />);
    fillForm({ password: 'ValidSecurePass123!', confirmPassword: 'ValidSecurePass123!' });

    const submitButton = screen.getByRole('button', { name: /create account/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(authApi.signup).toHaveBeenCalledWith(
        'Alice Johnson',
        'alice@example.com',
        'ValidSecurePass123!'
      );
      expect(mockSignUpSuccess).toHaveBeenCalled();
    });

    expect(screen.queryByText('Password must not contain spaces or whitespace characters.')).not.toBeInTheDocument();
  });

  it('7. preserves existing confirm-password comparison behavior', async () => {
    render(<SignUp onNavigate={mockNavigate} onSignUpSuccess={mockSignUpSuccess} />);
    fillForm({ password: 'ValidPassword123!', confirmPassword: 'DifferentPassword123!' });

    const submitButton = screen.getByRole('button', { name: /create account/i });
    fireEvent.click(submitButton);

    expect(await screen.findByText('Passwords do not match.')).toBeInTheDocument();
    expect(authApi.signup).not.toHaveBeenCalled();
  });

  it('8. preserves existing minimum password length (< 8) validation behavior', async () => {
    render(<SignUp onNavigate={mockNavigate} onSignUpSuccess={mockSignUpSuccess} />);
    fillForm({ password: 'Short1!', confirmPassword: 'Short1!' });

    const submitButton = screen.getByRole('button', { name: /create account/i });
    fireEvent.click(submitButton);

    expect(await screen.findByText('Password must be at least 8 characters.')).toBeInTheDocument();
    expect(authApi.signup).not.toHaveBeenCalled();
  });

  it('9. rejects whitespace-containing passwords in _mockSignup', async () => {
    const { authApi: realAuthApi } = await vi.importActual<any>('../services/api');
    await expect(
      realAuthApi._mockSignup('Test', 'test', 'test1@example.com', 'Secure Pass123!')
    ).rejects.toThrow('Password must not contain spaces or whitespace characters.');

    await expect(
      realAuthApi._mockSignup('Test', 'test', 'test2@example.com', 'SecurePass123! ')
    ).rejects.toThrow('Password must not contain spaces or whitespace characters.');

    await expect(
      realAuthApi._mockSignup('Test', 'test', 'test3@example.com', 'Secure\u00a0Pass123!')
    ).rejects.toThrow('Password must not contain spaces or whitespace characters.');

    await expect(
      realAuthApi._mockSignup('Test', 'test', 'test4@example.com', 'Short1!')
    ).rejects.toThrow('Password must be at least 8 characters.');
  });

  it('10. treats U+FEFF consistently with Python str.isspace (not rejected as whitespace)', async () => {
    (authApi.signup as any).mockResolvedValue({
      token: 'mock-jwt-token',
      user: { id: 'usr_123', email: 'alice@example.com', name: 'Alice Johnson' },
    });

    render(<SignUp onNavigate={mockNavigate} onSignUpSuccess={mockSignUpSuccess} />);
    fillForm({ password: 'Secure\ufeffPass123!', confirmPassword: 'Secure\ufeffPass123!' });

    const submitButton = screen.getByRole('button', { name: /create account/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(authApi.signup).toHaveBeenCalledWith(
        'Alice Johnson',
        'alice@example.com',
        'Secure\ufeffPass123!'
      );
    });
    expect(screen.queryByText('Password must not contain spaces or whitespace characters.')).not.toBeInTheDocument();
  });
});
