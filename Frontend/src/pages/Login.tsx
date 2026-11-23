import React, { useState } from 'react';
import type { PageView } from '../types';
import {
  Mail,
  Lock,
  AlertCircle,
  CheckCircle2,
  Loader2,
  Eye,
  EyeOff,
  ShieldCheck,
} from 'lucide-react';
import { authApi, type User } from '../services/api';

interface LoginProps {
  onNavigate: (view: PageView) => void;
  onLoginSuccess: (user: User) => void;
  initialEmail?: string;
  successMessage?: string;
}

export const Login: React.FC<LoginProps> = ({
  onNavigate,
  onLoginSuccess,
  initialEmail,
  successMessage,
}) => {
  const [email, setEmail] = useState(initialEmail || '');
  const [prevInitialEmail, setPrevInitialEmail] = useState(initialEmail);

  if (initialEmail !== prevInitialEmail) {
    setPrevInitialEmail(initialEmail);
    setEmail(initialEmail || '');
  }

  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [errors, setErrors] = useState<{ email?: string; password?: string }>({});
  const [apiError, setApiError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const validate = (): boolean => {
    const newErrors: { email?: string; password?: string } = {};
    const emailRegex = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;

    if (!email.trim()) {
      newErrors.email = 'Email address is required.';
    } else if (!email.includes('@')) {
      newErrors.email = 'Email must include an "@" symbol (e.g. name@domain.com).';
    } else if (!emailRegex.test(email.trim())) {
      newErrors.email = 'Please enter a valid email address with a valid domain.';
    }

    if (!password) {
      newErrors.password = 'Password is required.';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setApiError(null);

    if (!validate()) return;

    setIsLoading(true);
    try {
      const response = await authApi.login(email, password);
      onLoginSuccess(response.user);
    } catch (err: any) {
      setApiError(
        err.message || 'An error occurred during sign in. Please try again.'
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main className="flex min-h-screen w-full flex-col app-canvas md:flex-row">

      <section className="hero-vibrant flex w-full flex-col justify-between p-6 text-white sm:p-10 md:min-h-screen md:w-[43%] md:p-12 lg:p-16">
        <div className="flex items-center gap-3.5">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl overflow-hidden bg-white/10 backdrop-blur-md border border-white/20 p-1.5 shadow-md">
            <img 
              src="/assets/kavach-logo.png" 
              alt="कVaच Logo" 
              className="w-full h-full object-contain"
            />
          </div>
          <div>
            <div className="text-2xl sm:text-3xl font-black text-white leading-none tracking-tight flex items-center gap-0.5 mb-1 drop-shadow-[0_2px_4px_rgba(0,0,0,0.9)]">
              <span>क</span><span className="text-[#FF8A95]">Va</span><span>च</span>
            </div>
            <p className="text-xs sm:text-sm font-medium text-[#9ED4C8] leading-tight">
              See the Risks. Strengthen the Project.
            </p>
          </div>
        </div>

        <div className="my-10 max-w-lg md:my-0">
          <p className="mb-3 text-xs font-semibold uppercase tracking-[0.18em] text-[#9ED4C8]">
            Engineering visibility
          </p>
          <h1 className="!text-white text-3xl font-bold leading-tight tracking-tight sm:text-4xl lg:text-5xl">
            Understand your project.
            <span className="mt-1 block text-[#FF8A95]">
              Reduce delivery risk.
            </span>
          </h1>
          <p className="mt-5 max-w-md text-sm leading-7 text-white/80 sm:text-base">
            Monitor software project health, identify delivery bottlenecks,
            and make informed engineering decisions from your repository data.
          </p>
        </div>

        <p className="text-xs text-white/60">
          Software Project Health & Risk Analyzer
        </p>
      </section>

      <section className="flex flex-1 items-center justify-center p-5 sm:p-8 lg:p-12">
        <div className="w-full max-w-md rounded-xl border border-[#9ED4C8] bg-white p-6 sm:p-9">
          <div className="mb-7">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-[#0B6B63]">
              Account access
            </p>
            <h2 className="text-2xl font-bold tracking-tight text-[#0E2A2A] sm:text-3xl">
              Welcome back
            </h2>
            <p className="mt-2 text-sm text-slate-600">
              Sign in with your registered email and password.
            </p>
          </div>

          {successMessage && !apiError && (
            <div
              role="status"
              className="mb-5 flex items-start gap-3 rounded-lg border border-[#0B6B63]/20 bg-[#CDEFE6] p-3.5 text-sm text-[#0B6B63]"
            >
              <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0" />
              <span>{successMessage}</span>
            </div>
          )}

          {apiError && (
            <div
              role="alert"
              className="mb-5 flex items-start gap-3 rounded-lg border border-[#CC1F2E]/20 bg-[#CC1F2E]/5 p-3.5 text-sm text-[#CC1F2E]"
            >
              <AlertCircle className="mt-0.5 h-5 w-5 shrink-0" />
              <span>{apiError}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5" noValidate>
            <div>
              <label
                htmlFor="login-email"
                className="mb-2 block text-sm font-semibold text-slate-900"
              >
                Email address
              </label>
              <div
                className={`flex items-center rounded-lg border bg-white focus-within:ring-2 focus-within:ring-[#0B6B63]/15 ${
                  errors.email
                    ? 'border-[#CC1F2E]'
                    : 'border-[#9ED4C8] focus-within:border-[#0B6B63]'
                }`}
              >
                <Mail className="ml-4 h-5 w-5 shrink-0 text-slate-400" />
                <input
                  id="login-email"
                  type="email"
                  autoComplete="email"
                  disabled={isLoading}
                  value={email}
                  onChange={(event) => {
                    setEmail(event.target.value);
                    if (errors.email) {
                      setErrors((previous) => ({
                        ...previous,
                        email: undefined,
                      }));
                    }
                  }}
                  placeholder="name@example.com"
                  aria-invalid={Boolean(errors.email)}
                  aria-describedby={errors.email ? 'login-email-error' : undefined}
                  className="w-full rounded-lg bg-transparent px-4 py-3.5 text-sm text-slate-900 outline-none placeholder:text-slate-400 disabled:opacity-60"
                />
              </div>
              {errors.email && (
                <p
                  id="login-email-error"
                  className="mt-2 flex items-center gap-1.5 text-xs font-medium text-[#CC1F2E]"
                >
                  <AlertCircle className="h-3.5 w-3.5" />
                  {errors.email}
                </p>
              )}
            </div>

            <div>
              <label
                htmlFor="login-password"
                className="mb-2 block text-sm font-semibold text-slate-900"
              >
                Password
              </label>
              <div
                className={`flex items-center rounded-lg border bg-white focus-within:ring-2 focus-within:ring-[#0B6B63]/15 ${
                  errors.password
                    ? 'border-[#CC1F2E]'
                    : 'border-[#9ED4C8] focus-within:border-[#0B6B63]'
                }`}
              >
                <Lock className="ml-4 h-5 w-5 shrink-0 text-slate-400" />
                <input
                  id="login-password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  disabled={isLoading}
                  value={password}
                  onChange={(event) => {
                    setPassword(event.target.value);
                    if (errors.password) {
                      setErrors((previous) => ({
                        ...previous,
                        password: undefined,
                      }));
                    }
                  }}
                  placeholder="Enter your password"
                  aria-invalid={Boolean(errors.password)}
                  aria-describedby={
                    errors.password ? 'login-password-error' : undefined
                  }
                  className="w-full min-w-0 bg-transparent px-4 py-3.5 text-sm text-slate-900 outline-none placeholder:text-slate-400 disabled:opacity-60"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((visible) => !visible)}
                  className="mr-3 rounded-md p-1.5 text-slate-500 hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-[#0B6B63]"
                  title={showPassword ? 'Hide password' : 'Show password'}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? (
                    <EyeOff className="h-5 w-5" />
                  ) : (
                    <Eye className="h-5 w-5" />
                  )}
                </button>
              </div>
              {errors.password && (
                <p
                  id="login-password-error"
                  className="mt-2 flex items-center gap-1.5 text-xs font-medium text-[#CC1F2E]"
                >
                  <AlertCircle className="h-3.5 w-3.5" />
                  {errors.password}
                </p>
              )}
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="flex min-h-12 w-full items-center justify-center gap-2 rounded-lg bg-[#0B6B63] px-5 py-3 text-sm font-semibold text-white hover:bg-[#084F49] focus:outline-none focus:ring-2 focus:ring-[#0B6B63] focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isLoading ? (
                <>
                  <Loader2 className="h-4 w-4" />
                  Signing in...
                </>
              ) : (
                'Sign In'
              )}
            </button>
          </form>

          <div className="mt-7 border-t border-[#9ED4C8] pt-5 text-center text-sm text-slate-600">
            Don't have an account?
            <button
              type="button"
              onClick={() => onNavigate('signup')}
              className="ml-1 font-semibold text-[#0B6B63] hover:underline focus:outline-none focus:ring-2 focus:ring-[#0B6B63] focus:ring-offset-2"
            >
              Sign up
            </button>
          </div>
        </div>
      </section>
    </main>
  );
};
