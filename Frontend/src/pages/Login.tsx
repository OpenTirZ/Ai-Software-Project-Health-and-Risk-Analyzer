import React, { useState, useEffect } from 'react';
import type { PageView } from '../types';
import { Mail, Lock, AlertCircle, CheckCircle2, Loader2, Eye, EyeOff } from 'lucide-react';
import { authApi } from '../services/api';

interface LoginProps {
  onNavigate: (view: PageView) => void;
  onLoginSuccess: (user: { email: string; name: string; username?: string }) => void;
  initialEmail?: string;
  successMessage?: string;
}

export const Login: React.FC<LoginProps> = ({ onNavigate, onLoginSuccess, initialEmail, successMessage }) => {
  const [email, setEmail] = useState(initialEmail || '');

  useEffect(() => {
    if (initialEmail !== undefined) {
      setEmail(initialEmail);
    }
  }, [initialEmail]);

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
      newErrors.email = 'Please enter a valid email address with a valid domain (e.g. user@company.com).';
    }

    if (!password) {
      newErrors.password = 'Password is required.';
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

    setIsLoading(true);
    try {
      const response = await authApi.login(email, password);
      onLoginSuccess(response.user);
    } catch (err: any) {
      setApiError(err.message || 'An error occurred during sign in. Please try again.');
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
          src="/assets/login-bg.png" 
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
            Welcome back !
          </h2>
          <p className="text-xs sm:text-[13px] md:text-sm text-white/90 font-['Saira_Semi_Condensed',sans-serif] leading-relaxed drop-shadow-[0_2px_4px_rgba(0,0,0,0.9)] max-w-xs">
            Sign in to your account to continue analyzing your software project
          </p>
        </div>
      </div>

      {/* Right Login Form */}
      <div className="flex-1 flex items-center justify-center p-6 md:p-14 lg:p-20 bg-white">
        <div className="w-full max-w-[460px]">
          <div className="mb-6">
            <h2 className="text-3xl md:text-4xl font-semibold text-slate-900 tracking-tight font-['Playpen_Sans',cursive,sans-serif]">
              Login
            </h2>
            <p className="text-base text-slate-500 mt-1 font-['Playpen_Sans',cursive,sans-serif]">
              Enter your email and password
            </p>
          </div>

          {/* Account Created Success Alert */}
          {successMessage && !apiError && (
            <div className="mb-5 p-3.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-sm flex items-start gap-2.5 animate-fadeIn">
              <CheckCircle2 className="w-5 h-5 shrink-0 mt-0.5 text-emerald-600" />
              <span>{successMessage}</span>
            </div>
          )}

          {/* Backend Error Alert */}
          {apiError && (
            <div className="mb-5 p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-sm flex items-start gap-2.5 animate-fadeIn">
              <AlertCircle className="w-5 h-5 shrink-0 mt-0.5 text-rose-500" />
              <span>{apiError}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5" noValidate>
            {/* Email Field */}
            <div>
              <label htmlFor="login-email" className="block text-sm font-medium text-slate-900 mb-1.5 font-['Playpen_Sans',cursive,sans-serif]">
                Email address
              </label>
              <div className={`relative rounded-[12px] border shadow-sm transition-all overflow-hidden flex items-center ${
                errors.email ? 'border-rose-400 focus-within:ring-2 focus-within:ring-rose-100' : 'border-slate-300 focus-within:border-indigo-600 focus-within:ring-2 focus-within:ring-indigo-100'
              }`}>
                <div className="pl-4 text-slate-400">
                  <Mail className={`w-5 h-5 ${errors.email ? 'text-rose-500' : 'text-indigo-500'}`} />
                </div>
                <input
                  id="login-email"
                  type="email"
                  disabled={isLoading}
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    if (errors.email) setErrors((prev) => ({ ...prev, email: undefined }));
                  }}
                  placeholder="xyz@gmail.com"
                  className="w-full px-4 py-3.5 text-base text-slate-900 placeholder:text-slate-400 focus:outline-none bg-transparent disabled:opacity-60"
                />
              </div>
              {errors.email && (
                <p className="text-xs text-rose-600 mt-1.5 font-medium flex items-center gap-1">
                  <AlertCircle className="w-3.5 h-3.5" />
                  {errors.email}
                </p>
              )}
            </div>

            {/* Password Field */}
            <div>
              <label htmlFor="login-password" className="block text-sm font-medium text-slate-900 mb-1.5 font-['Playpen_Sans',cursive,sans-serif]">
                Password
              </label>
              <div className={`relative rounded-[12px] border shadow-sm transition-all overflow-hidden flex items-center ${
                errors.password ? 'border-rose-400 focus-within:ring-2 focus-within:ring-rose-100' : 'border-slate-300 focus-within:border-indigo-600 focus-within:ring-2 focus-within:ring-indigo-100'
              }`}>
                <div className="pl-4 text-slate-400">
                  <Lock className={`w-5 h-5 ${errors.password ? 'text-rose-500' : 'text-indigo-500'}`} />
                </div>
                <input
                  id="login-password"
                  type={showPassword ? 'text' : 'password'}
                  disabled={isLoading}
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value);
                    if (errors.password) setErrors((prev) => ({ ...prev, password: undefined }));
                  }}
                  placeholder="Enter your password"
                  className="w-full px-4 py-3.5 text-base text-slate-900 placeholder:text-slate-400 focus:outline-none bg-transparent disabled:opacity-60"
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
                <p className="text-xs text-rose-600 mt-1.5 font-medium flex items-center gap-1">
                  <AlertCircle className="w-3.5 h-3.5" />
                  {errors.password}
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
                    <span className="font-['Playpen_Sans',cursive,sans-serif] text-base">Signing in...</span>
                  </>
                ) : (
                  <span className="font-['Playpen_Sans',cursive,sans-serif] text-xl">Sign In</span>
                )}
              </button>
            </div>
          </form>

          {/* Footer Signup Link */}
          <div className="mt-6 text-center text-base text-slate-600 font-['Sahitya',serif]">
            <span>Don't have an account? </span>
            <button
              onClick={() => onNavigate('signup')}
              className="text-[#174994] font-bold hover:underline ml-1 cursor-pointer"
            >
              Sign up
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
