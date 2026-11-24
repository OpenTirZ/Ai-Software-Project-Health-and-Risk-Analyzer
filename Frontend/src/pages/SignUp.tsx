import React, { useState } from 'react';
import type { PageView } from '../types';
import { User, Mail, Lock, AlertCircle, Loader2, CheckCircle2, Eye, EyeOff } from 'lucide-react';
import { authApi, verifyEmailDomain } from '../services/api';

interface SignUpProps {
  onNavigate: (view: PageView) => void;
  onSignUpSuccess: (user: { email: string; name: string; username?: string }) => void;
}

export const SignUp: React.FC<SignUpProps> = ({ onNavigate, onSignUpSuccess }) => {
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

  const checkEmailDomainLive = async (emailToCheck: string): Promise<boolean> => {
    const trimmed = emailToCheck.trim();
    const emailRegex = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
    if (!emailRegex.test(trimmed)) {
      setDomainVerified(null);
      return false;
    }

    setIsCheckingDomain(true);
    try {
      const result = await verifyEmailDomain(trimmed);
      if (!result.isValid) {
        setDomainVerified(false);
        setErrors((prev) => ({ ...prev, email: result.reason }));
        return false;
      } else {
        setDomainVerified(true);
        setErrors((prev) => ({ ...prev, email: undefined }));
        return true;
      }
    } catch {
      setDomainVerified(null);
      return true;
    } finally {
      setIsCheckingDomain(false);
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
      newErrors.email = 'Email must include an "@" symbol (e.g. name@domain.com).';
    } else if (!emailRegex.test(email.trim())) {
      newErrors.email = 'Please enter a valid email address with a valid domain (e.g. user@company.com).';
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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setApiError(null);

    if (!validate()) {
      return;
    }

    // Live verification: verify that the email domain actually exists and has mail servers
    const isDomainValid = await checkEmailDomainLive(email);
    if (!isDomainValid) {
      return;
    }

    setIsLoading(true);
    try {
      const response = await authApi.signup(name, email, password);
      // Route to login page with newly registered user details
      onSignUpSuccess(response.user);
    } catch (err: any) {
      setApiError(err.message || 'Signup failed. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen w-full flex flex-col md:flex-row bg-white text-slate-800">
      {/* Left Hero Banner */}
      <div className="relative w-full md:w-1/2 min-h-[380px] md:min-h-screen overflow-hidden flex flex-col p-6 sm:p-8 md:p-12 lg:p-14 shrink-0 bg-[#070b19]">
        {/* Fully visible background artwork */}
        <img 
          src="/assets/signup-bg.png" 
          alt="" 
          className="absolute inset-0 w-full h-full object-cover object-center pointer-events-none select-none" 
        />
        {/* Minimal soft tint so the artwork is fully vivid and clearly visible */}
        <div className="absolute inset-0 bg-black/15 pointer-events-none" />

        {/* Top Branding (Logo + Bigger Title) */}
        <div className="relative z-10 flex items-center gap-3.5">
          <div className="w-11 h-11 md:w-12 md:h-12 rounded-[12px] overflow-hidden bg-white/10 backdrop-blur-md border border-white/20 shrink-0 shadow-md p-1.5 flex items-center justify-center">
            <img 
              src="/assets/website-logo.png" 
              alt="Website Logo" 
              className="w-full h-full object-contain"
            />
          </div>
          <div>
            <h1 className="text-xl sm:text-2xl md:text-[26px] lg:text-[28px] font-extrabold font-['Saira_Semi_Condensed',sans-serif] text-white leading-[1.1] drop-shadow-[0_2px_4px_rgba(0,0,0,0.9)]">
              AI Software Project Health and<br className="hidden sm:inline" /> Risk Analyzer
            </h1>
          </div>
        </div>

        {/* Welcome Statement - Smaller, elegant sizing */}
        <div className="relative z-10 mt-6 sm:mt-8 md:mt-10 lg:mt-12 max-w-md">
          <h2 className="text-xl sm:text-[22px] md:text-2xl font-semibold text-white mb-1.5 font-['Playpen_Sans',cursive,sans-serif] tracking-normal drop-shadow-[0_2px_6px_rgba(0,0,0,0.95)]">
            Create Your Account
          </h2>
          <p className="text-xs sm:text-[13px] md:text-sm text-white/90 font-['Saira_Semi_Condensed',sans-serif] leading-relaxed drop-shadow-[0_2px_4px_rgba(0,0,0,0.9)] max-w-xs">
            Gain immediate visibility into your engineering velocity, code churn anomalies, and software project risk factors.
          </p>
        </div>
      </div>

      {/* Right Signup Form */}
      <div className="flex-1 flex items-center justify-center p-6 md:p-10 lg:p-14 bg-white">
        <div className="w-full max-w-[460px]">
          <div className="mb-5">
            <h2 className="text-3xl md:text-4xl font-semibold text-slate-900 tracking-tight font-['Playpen_Sans',cursive,sans-serif]">
              Sign up
            </h2>
            <p className="text-base text-slate-500 mt-1 font-['Playpen_Sans',cursive,sans-serif]">
              Create your account to get started
            </p>
          </div>

          {/* Backend Error Alert */}
          {apiError && (
            <div className="mb-4 p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-sm flex items-start gap-2.5 animate-fadeIn">
              <AlertCircle className="w-5 h-5 shrink-0 mt-0.5 text-rose-500" />
              <span>{apiError}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-3.5" noValidate>
            {/* Full Name */}
            <div>
              <label className="block text-sm font-medium text-slate-900 mb-1 font-['Playpen_Sans',cursive,sans-serif]">
                Full name
              </label>
              <div className={`relative rounded-[12px] border shadow-sm transition-all overflow-hidden flex items-center ${
                errors.name ? 'border-rose-400 focus-within:ring-2 focus-within:ring-rose-100' : 'border-slate-300 focus-within:border-indigo-600 focus-within:ring-2 focus-within:ring-indigo-100'
              }`}>
                <div className="pl-4 text-slate-400">
                  <User className={`w-5 h-5 ${errors.name ? 'text-rose-500' : 'text-indigo-500'}`} />
                </div>
                <input
                  type="text"
                  disabled={isLoading}
                  value={name}
                  onChange={(e) => {
                    setName(e.target.value);
                    if (errors.name) setErrors((prev) => ({ ...prev, name: undefined }));
                  }}
                  placeholder="Enter your name"
                  className="w-full px-4 py-2.5 text-sm md:text-base text-slate-900 placeholder:text-slate-400 focus:outline-none bg-transparent disabled:opacity-60"
                />
              </div>
              {errors.name && (
                <p className="text-xs text-rose-600 mt-1 font-medium flex items-center gap-1">
                  <AlertCircle className="w-3.5 h-3.5" />
                  {errors.name}
                </p>
              )}
            </div>

            {/* Email Address */}
            <div>
              <label className="block text-sm font-medium text-slate-900 mb-1 font-['Playpen_Sans',cursive,sans-serif]">
                Email address
              </label>
              <div className={`relative rounded-[12px] border shadow-sm transition-all overflow-hidden flex items-center ${
                errors.email ? 'border-rose-400 focus-within:ring-2 focus-within:ring-rose-100' : 'border-slate-300 focus-within:border-indigo-600 focus-within:ring-2 focus-within:ring-indigo-100'
              }`}>
                <div className="pl-4 text-slate-400">
                  <Mail className={`w-5 h-5 ${errors.email ? 'text-rose-500' : 'text-indigo-500'}`} />
                </div>
                <input
                  type="email"
                  disabled={isLoading}
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    setDomainVerified(null);
                    if (errors.email) setErrors((prev) => ({ ...prev, email: undefined }));
                  }}
                  onBlur={() => {
                    if (email.trim()) {
                      checkEmailDomainLive(email);
                    }
                  }}
                  placeholder="xyz@gmail.com"
                  className="w-full px-4 py-2.5 text-sm md:text-base text-slate-900 placeholder:text-slate-400 focus:outline-none bg-transparent disabled:opacity-60"
                />
                {isCheckingDomain ? (
                  <div className="pr-3 text-indigo-500 shrink-0 flex items-center">
                    <Loader2 className="w-4 h-4 animate-spin" />
                  </div>
                ) : domainVerified === true && !errors.email ? (
                  <div className="pr-3 text-emerald-500 shrink-0 flex items-center" title="Email verified">
                    <CheckCircle2 className="w-4 h-4" />
                  </div>
                ) : null}
              </div>
              {errors.email && (
                <p className="text-xs text-rose-600 mt-1 font-medium flex items-center gap-1">
                  <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                  {errors.email}
                </p>
              )}
            </div>

            {/* Password */}
            <div>
              <label className="block text-sm font-medium text-slate-900 mb-1 font-['Playpen_Sans',cursive,sans-serif]">
                Password
              </label>
              <div className={`relative rounded-[12px] border shadow-sm transition-all overflow-hidden flex items-center ${
                errors.password ? 'border-rose-400 focus-within:ring-2 focus-within:ring-rose-100' : 'border-slate-300 focus-within:border-indigo-600 focus-within:ring-2 focus-within:ring-indigo-100'
              }`}>
                <div className="pl-4 text-slate-400">
                  <Lock className={`w-5 h-5 ${errors.password ? 'text-rose-500' : 'text-indigo-500'}`} />
                </div>
                <input
                  type={showPassword ? 'text' : 'password'}
                  disabled={isLoading}
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value);
                    if (errors.password) setErrors((prev) => ({ ...prev, password: undefined }));
                  }}
                  placeholder="At least 8 characters"
                  className="w-full px-4 py-2.5 text-sm md:text-base text-slate-900 placeholder:text-slate-400 focus:outline-none bg-transparent disabled:opacity-60"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="pr-4 text-slate-400 hover:text-slate-600 transition-colors focus:outline-none cursor-pointer"
                  title={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? (
                    <EyeOff className="w-5 h-5 text-slate-500" />
                  ) : (
                    <Eye className="w-5 h-5 text-slate-400" />
                  )}
                </button>
              </div>
              {errors.password && (
                <p className="text-xs text-rose-600 mt-1 font-medium flex items-center gap-1">
                  <AlertCircle className="w-3.5 h-3.5" />
                  {errors.password}
                </p>
              )}
            </div>

            {/* Confirm Password */}
            <div>
              <label className="block text-sm font-medium text-slate-900 mb-1 font-['Playpen_Sans',cursive,sans-serif]">
                Confirm Password
              </label>
              <div className={`relative rounded-[12px] border shadow-sm transition-all overflow-hidden flex items-center ${
                errors.confirmPassword ? 'border-rose-400 focus-within:ring-2 focus-within:ring-rose-100' : 'border-slate-300 focus-within:border-indigo-600 focus-within:ring-2 focus-within:ring-indigo-100'
              }`}>
                <div className="pl-4 text-slate-400">
                  <Lock className={`w-5 h-5 ${errors.confirmPassword ? 'text-rose-500' : 'text-indigo-500'}`} />
                </div>
                <input
                  type={showConfirmPassword ? 'text' : 'password'}
                  disabled={isLoading}
                  value={confirmPassword}
                  onChange={(e) => {
                    setConfirmPassword(e.target.value);
                    if (errors.confirmPassword) setErrors((prev) => ({ ...prev, confirmPassword: undefined }));
                  }}
                  placeholder="Repeat your password"
                  className="w-full px-4 py-2.5 text-sm md:text-base text-slate-900 placeholder:text-slate-400 focus:outline-none bg-transparent disabled:opacity-60"
                />
                <button
                  type="button"
                  onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  className="pr-4 text-slate-400 hover:text-slate-600 transition-colors focus:outline-none cursor-pointer"
                  title={showConfirmPassword ? 'Hide password' : 'Show password'}
                >
                  {showConfirmPassword ? (
                    <EyeOff className="w-5 h-5 text-slate-500" />
                  ) : (
                    <Eye className="w-5 h-5 text-slate-400" />
                  )}
                </button>
              </div>
              {errors.confirmPassword && (
                <p className="text-xs text-rose-600 mt-1 font-medium flex items-center gap-1">
                  <AlertCircle className="w-3.5 h-3.5" />
                  {errors.confirmPassword}
                </p>
              )}
            </div>

            {/* Submit Button */}
            <div className="pt-2">
              <button
                type="submit"
                disabled={isLoading}
                className="w-full py-3.5 px-6 rounded-[14px] text-white font-medium text-lg shadow-xl shadow-indigo-500/20 transition-all duration-300 transform active:scale-[0.99] flex items-center justify-center gap-2 group cursor-pointer disabled:opacity-75 disabled:cursor-not-allowed"
                style={{
                  background: 'linear-gradient(135deg, #1b1795 0%, #2e3b63 50%, #18ebe4 100%)',
                }}
              >
                {isLoading ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    <span className="font-['Playpen_Sans',cursive,sans-serif] text-base">Creating account...</span>
                  </>
                ) : (
                  <span className="font-['Playpen_Sans',cursive,sans-serif] text-xl">Sign up</span>
                )}
              </button>
            </div>
          </form>

          {/* Footer Login Link */}
          <div className="mt-5 text-center text-base text-slate-600 font-['Sahitya',serif]">
            <span>Already have an account? </span>
            <button
              onClick={() => onNavigate('login')}
              className="text-[#174994] font-bold hover:underline ml-1 cursor-pointer"
            >
              Login
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
