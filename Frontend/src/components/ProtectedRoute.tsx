import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';

interface ProtectedRouteProps {
  isLoading: boolean;
  isAuthenticated: boolean;
  userRole?: string;
  requiredRole?: string;
  children: ReactNode;
}

/** Waits for session restoration before deciding whether a route is accessible. */
export function ProtectedRoute({
  isLoading,
  isAuthenticated,
  userRole,
  requiredRole,
  children,
}: ProtectedRouteProps) {
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center app-canvas">
        <p className="text-sm font-medium text-slate-600" role="status">
          Verifying your session...
        </p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  if (requiredRole && userRole !== requiredRole) {
    return <Navigate to="/projects" replace />;
  }

  return <>{children}</>;
}
