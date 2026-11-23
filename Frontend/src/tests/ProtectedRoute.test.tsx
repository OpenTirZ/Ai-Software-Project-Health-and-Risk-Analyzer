import React from 'react';
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { ProtectedRoute } from '../components/ProtectedRoute';

function renderProtectedRoute({
  isLoading = false,
  isAuthenticated = true,
  userRole,
  requiredRole,
  initialEntry = '/private',
}: {
  isLoading?: boolean;
  isAuthenticated?: boolean;
  userRole?: string;
  requiredRole?: string;
  initialEntry?: string;
} = {}) {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/login" element={<h1>Login page</h1>} />
        <Route path="/projects" element={<h1>Projects page</h1>} />
        <Route
          path="/private"
          element={
            <ProtectedRoute
              isLoading={isLoading}
              isAuthenticated={isAuthenticated}
              userRole={userRole}
              requiredRole={requiredRole}
            >
              <h1>Protected content</h1>
            </ProtectedRoute>
          }
        />
      </Routes>
    </MemoryRouter>,
  );
}

describe('ProtectedRoute', () => {
  it('waits for session verification before rendering protected content', () => {
    renderProtectedRoute({ isLoading: true });

    expect(screen.getByRole('status')).toHaveTextContent('Verifying your session');
    expect(screen.queryByRole('heading', { name: 'Protected content' })).not.toBeInTheDocument();
  });

  it('redirects unauthenticated users to login', () => {
    renderProtectedRoute({ isAuthenticated: false });

    expect(screen.getByRole('heading', { name: 'Login page' })).toBeInTheDocument();
  });

  it('redirects users without the required role to projects', () => {
    renderProtectedRoute({ userRole: 'developer', requiredRole: 'admin' });

    expect(screen.getByRole('heading', { name: 'Projects page' })).toBeInTheDocument();
  });

  it('allows an authenticated user with the required role', () => {
    renderProtectedRoute({ userRole: 'admin', requiredRole: 'admin' });

    expect(screen.getByRole('heading', { name: 'Protected content' })).toBeInTheDocument();
  });
});
