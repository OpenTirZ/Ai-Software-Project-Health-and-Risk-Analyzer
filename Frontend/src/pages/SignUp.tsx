import React, { useState } from 'react';
import type { PageView } from '../types';
import {
  User,
  Mail,
  Lock,
  AlertCircle,
  Loader2,
  CheckCircle2,
  Eye,
  EyeOff,
  ShieldCheck,
} from 'lucide-react';
import { authApi, verifyEmailDomain } from '../services/api';

interface SignUpProps {
  onNavigate: (view: PageView) => void;
  onSignUpSuccess: (user: { email: string; name: string; username?: string }) => void;
}

export const SignUp: React.FC<SignUpProps> = ({
  onNavigate,
  onSignUpSuccess,
}) => {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const [errors, setErrors] = useState<{
    name?: string;
    email?: string;
    password?: string;
    confirmPassword?: string;
  }>({});

  const [apiError, setApiError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isCheckingDomain, setIsCheckingDomain] = useState(false);
  const [domainVerified, setDomainVerified] = useState<boolean | null>(null);

  const checkEmailDomainLive = async (
    emailToCheck: string
  ): Promise<boolean> => {
    const trimmed = emailToCheck.trim();
    setIsCheckingDomain(false);

    try {
      const result = verifyEmailDomain(trimmed);

      if (!result.isValid) {
        setDomainVerified(false);
        setErrors((previous) => ({
          ...previous,
          email: result.reason,
        }));
        return false;
      }

      setDomainVerified(true);
      setErrors((previous) => ({
        ...previous,
        email: undefined,
      }));
      return true;
    } catch {
      setDomainVerified(null);
      return true;
    }
  };

  const validate = (): boolean => {
    const newErrors: {
      name?: string;
      email?: string;
      password?: string;
      confirmPassword?: string;
    } = {};

    if (!name.trim()) {
      newErrors.name = 'Full name is required.';
    } else if (name.trim().length < 2) {
      newErrors.name = 'Name must be at least 2 characters.';
    }

    const emailRegex = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;

    if (!email.trim()) {
      newErrors.email = 'Email address is required.';
    } else if (!email.includes('@')) {
      newErrors.email = 'Email must include an "@" symbol.';
    } else if (!emailRegex.test(email.trim())) {
      newErrors.email = 'Please enter a valid email address with a valid domain.';
    }

    if (!password) {
      newErrors.password = 'Password is required.';
    } else if (password.length < 8) {
      newErrors.password = 'Password must be at least 8 characters.';
    }

    if (!confirmPassword) {
      newErrors.confirmPassword = 'Please confirm your password.';
    } else if (confirmPassword !== password) {
      newErrors.confirmPassword = 'Passwords do not match.';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setApiError(null);

    if (!validate()) return;

    const isDomainValid = await checkEmailDomainLive(email);
    if (!isDomainValid) return;

    setIsLoading(true);

    try {
      const response = await authApi.signup(name, email, password);
      onSignUpSuccess(response.user);
    } catch (err: any) {
      setApiError(err.message || 'Signup failed. Please try again.');
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
            Build with clarity.
            <span className="mt-1 block text-[#CDEFE6]">
              Deliver with confidence.
            </span>
          </h1>
          <p className="mt-5 max-w-md text-sm leading-7 text-white/80 sm:text-base">
            Create an account to monitor software project health, understand
            repository activity, and identify delivery risks.
          </p>
        </div>

        <p className="text-xs text-white/60">
          Software Project Health & Risk Analyzer
        </p>
      </section>

      <section className="flex flex-1 items-center justify-center p-5 sm:p-8 lg:p-10">
        <div className="my-4 w-full max-w-md rounded-xl border border-[#9ED4C8] bg-white p-6 sm:p-8">
          <div className="mb-6">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-[#0B6B63]">
              Get started
            </p>
            <h2 className="text-2xl font-bold tracking-tight text-[#0E2A2A] sm:text-3xl">
              Create your account
            </h2>
            <p className="mt-2 text-sm text-slate-600">
              Enter your details to register.
            </p>
          </div>

          {apiError && (
            <div
              role="alert"
              className="mb-5 flex items-start gap-3 rounded-lg border border-[#CC1F2E]/20 bg-[#CC1F2E]/5 p-3.5 text-sm text-[#CC1F2E]"
            >
              <AlertCircle className="mt-0.5 h-5 w-5 shrink-0" />
              <span>{apiError}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4" noValidate>

            <div>
              <label
                htmlFor="signup-name"
                className="mb-2 block text-sm font-semibold text-slate-900"
              >
                Full name
              </label>
              <div
                className={`flex items-center rounded-lg border bg-white focus-within:ring-2 focus-within:ring-[#0B6B63]/15 ${
                  errors.name
                    ? 'border-[#CC1F2E]'
                    : 'border-[#9ED4C8] focus-within:border-[#0B6B63]'
                }`}
              >
                <User className="ml-4 h-5 w-5 shrink-0 text-slate-400" />
                <input
                  id="signup-name"
                  type="text"
                  autoComplete="name"
                  disabled={isLoading}
                  value={name}
                  onChange={(event) => {
                    setName(event.target.value);
                    if (errors.name) {
                      setErrors((previous) => ({
                        ...previous,
                        name: undefined,
                      }));
                    }
                  }}
                  placeholder="Enter your name"
                  aria-invalid={Boolean(errors.name)}
                  aria-describedby={errors.name ? 'signup-name-error' : undefined}
                  className="w-full rounded-lg bg-transparent px-4 py-3 text-sm text-slate-900 outline-none placeholder:text-slate-400 disabled:opacity-60"
                />
              </div>
              {errors.name && (
                <p
                  id="signup-name-error"
                  className="mt-2 flex items-center gap-1.5 text-xs font-medium text-[#CC1F2E]"
                >
                  <AlertCircle className="h-3.5 w-3.5" />
                  {errors.name}
                </p>
              )}
            </div>

            <div>
              <label
                htmlFor="signup-email"
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
                  id="signup-email"
                  type="email"
                  autoComplete="email"
                  disabled={isLoading}
                  value={email}
                  onChange={(event) => {
                    setEmail(event.target.value);
                    setDomainVerified(null);

                    if (errors.email) {
                      setErrors((previous) => ({
                        ...previous,
                        email: undefined,
                      }));
                    }
                  }}
                  onBlur={() => {
                    if (email.trim()) {
                      checkEmailDomainLive(email);
                    }
                  }}
                  placeholder="name@example.com"
                  aria-invalid={Boolean(errors.email)}
                  aria-describedby={
                    errors.email ? 'signup-email-error' : undefined
                  }
                  className="w-full min-w-0 rounded-lg bg-transparent px-4 py-3 text-sm text-slate-900 outline-none placeholder:text-slate-400 disabled:opacity-60"
                />

                {isCheckingDomain ? (
                  <div className="mr-3 text-slate-500">
                    <Loader2 className="h-4 w-4" />
                  </div>
                ) : domainVerified === true && !errors.email ? (
                  <div
                    className="mr-3 text-[#0B6B63]"
                    title="Email format verified"
                    aria-label="Email format verified"
                  >
                    <CheckCircle2 className="h-4 w-4" />
                  </div>
                ) : null}
              </div>
              {errors.email && (
                <p
                  id="signup-email-error"
                  className="mt-2 flex items-center gap-1.5 text-xs font-medium text-[#CC1F2E]"
                >
                  <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                  {errors.email}
                </p>
              )}
            </div>

            <div>
              <label
                htmlFor="signup-password"
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
                  id="signup-password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="new-password"
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
                  placeholder="At least 8 characters"
                  aria-invalid={Boolean(errors.password)}
                  aria-describedby={
                    errors.password ? 'signup-password-error' : undefined
                  }
                  className="w-full min-w-0 bg-transparent px-4 py-3 text-sm text-slate-900 outline-none placeholder:text-slate-400 disabled:opacity-60"
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
                  id="signup-password-error"
                  className="mt-2 flex items-center gap-1.5 text-xs font-medium text-[#CC1F2E]"
                >
                  <AlertCircle className="h-3.5 w-3.5" />
                  {errors.password}
                </p>
              )}
            </div>

            <div>
              <label
                htmlFor="signup-confirm-password"
                className="mb-2 block text-sm font-semibold text-slate-900"
              >
                Confirm password
              </label>
              <div
                className={`flex items-center rounded-lg border bg-white focus-within:ring-2 focus-within:ring-[#0B6B63]/15 ${
                  errors.confirmPassword
                    ? 'border-[#CC1F2E]'
                    : 'border-[#9ED4C8] focus-within:border-[#0B6B63]'
                }`}
              >
                <Lock className="ml-4 h-5 w-5 shrink-0 text-slate-400" />
                <input
                  id="signup-confirm-password"
                  type={showConfirmPassword ? 'text' : 'password'}
                  autoComplete="new-password"
                  disabled={isLoading}
                  value={confirmPassword}
                  onChange={(event) => {
                    setConfirmPassword(event.target.value);
                    if (errors.confirmPassword) {
                      setErrors((previous) => ({
                        ...previous,
                        confirmPassword: undefined,
                      }));
                    }
                  }}
                  placeholder="Repeat your password"
                  aria-invalid={Boolean(errors.confirmPassword)}
                  aria-describedby={
                    errors.confirmPassword
                      ? 'signup-confirm-password-error'
                      : undefined
                  }
                  className="w-full min-w-0 bg-transparent px-4 py-3 text-sm text-slate-900 outline-none placeholder:text-slate-400 disabled:opacity-60"
                />
                <button
                  type="button"
                  onClick={() =>
                    setShowConfirmPassword((visible) => !visible)
                  }
                  className="mr-3 rounded-md p-1.5 text-slate-500 hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-[#0B6B63]"
                  title={
                    showConfirmPassword ? 'Hide password' : 'Show password'
                  }
                  aria-label={
                    showConfirmPassword ? 'Hide password' : 'Show password'
                  }
                >
                  {showConfirmPassword ? (
                    <EyeOff className="h-5 w-5" />
                  ) : (
                    <Eye className="h-5 w-5" />
                  )}
                </button>
              </div>
              {errors.confirmPassword && (
                <p
                  id="signup-confirm-password-error"
                  className="mt-2 flex items-center gap-1.5 text-xs font-medium text-[#CC1F2E]"
                >
                  <AlertCircle className="h-3.5 w-3.5" />
                  {errors.confirmPassword}
                </p>
              )}
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="mt-2 flex min-h-12 w-full items-center justify-center gap-2 rounded-lg bg-[#0B6B63] px-5 py-3 text-sm font-semibold text-white hover:bg-[#084F49] focus:outline-none focus:ring-2 focus:ring-[#0B6B63] focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isLoading ? (
                <>
                  <Loader2 className="h-4 w-4" />
                  Creating account...
                </>
              ) : (
                'Create Account'
              )}
            </button>
          </form>

          <div className="mt-6 border-t border-[#9ED4C8] pt-5 text-center text-sm text-slate-600">
            Already have an account?
            <button
              type="button"
              onClick={() => onNavigate('login')}
              className="ml-1 font-semibold text-[#0B6B63] hover:underline focus:outline-none focus:ring-2 focus:ring-[#0B6B63] focus:ring-offset-2"
            >
              Login
            </button>
          </div>
        </div>
      </section>
    </main>
  );
};
