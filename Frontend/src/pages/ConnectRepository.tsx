import React, { useState } from 'react';
import type { PageView, Repository } from '../types';
import { 
  GitBranch, 
  ArrowLeft, 
  AlertCircle, 
  Loader2, 
  CheckCircle2, 
  ShieldCheck, 
  ExternalLink,
  RefreshCw
} from 'lucide-react';
import { repositoryApi, type ProjectResponse } from '../services/api';

interface ConnectRepositoryProps {
  project: ProjectResponse | null;
  onRepoConnected: (repo: Repository) => void;
  onNavigate: (view: PageView) => void;
}

export const ConnectRepository: React.FC<ConnectRepositoryProps> = ({
  project,
  onRepoConnected,
  onNavigate,
}) => {
  const [githubUrl, setGithubUrl] = useState('');
  const [branch, setBranch] = useState('main');
  const [branches, setBranches] = useState<string[]>(['main', 'master', 'develop']);
  const [isFetchingBranches, setIsFetchingBranches] = useState(false);
  const [branchSource, setBranchSource] = useState<'github' | 'default' | null>(null);
  const [isCustomBranch, setIsCustomBranch] = useState(false);
  const [customBranchInput, setCustomBranchInput] = useState('');

  const [errors, setErrors] = useState<{ githubUrl?: string; branch?: string }>({});
  const [apiError, setApiError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  const projectName = project?.name || 'New Project';
  const projectId = project?.id || 'proj_default';

  const fetchBranchesForRepo = async (urlToFetch?: string) => {
    const url = (urlToFetch || githubUrl).trim();
    if (!url) return;

    const githubRegex = /^https:\/\/github\.com\/[a-zA-Z0-9_.-]+\/[a-zA-Z0-9_.-]+\/?$/;
    if (!githubRegex.test(url)) return;

    setIsFetchingBranches(true);
    setApiError(null);
    try {
      const res = await repositoryApi.fetchBranches(url);
      if (res.branches && res.branches.length > 0) {
        setBranches(res.branches);
        setBranchSource(res.source);
        // Default to main or master if available, otherwise first branch
        if (res.branches.includes('main')) {
          setBranch('main');
        } else if (res.branches.includes('master')) {
          setBranch('master');
        } else {
          setBranch(res.branches[0]);
        }
        setIsCustomBranch(false);
      }
    } catch {
      // Fallback already handled
    } finally {
      setIsFetchingBranches(false);
    }
  };

  const validate = (): boolean => {
    const newErrors: { githubUrl?: string; branch?: string } = {};

    if (!githubUrl.trim()) {
      newErrors.githubUrl = 'GitHub repository URL is required.';
    } else {
      const githubRegex = /^https:\/\/github\.com\/[a-zA-Z0-9_.-]+\/[a-zA-Z0-9_.-]+\/?$/;
      if (!githubRegex.test(githubUrl.trim())) {
        newErrors.githubUrl = 'Invalid URL. Please enter a valid GitHub repository URL (e.g. https://github.com/owner/repository).';
      }
    }

    const selectedBranch = isCustomBranch ? customBranchInput.trim() : branch.trim();
    if (!selectedBranch) {
      newErrors.branch = 'Please select or enter a branch name.';
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

    const targetBranch = isCustomBranch ? customBranchInput.trim() : branch.trim() || 'main';

    setIsLoading(true);
    try {
      const repoResponse = await repositoryApi.connectRepository({
        projectId,
        githubUrl: githubUrl.trim(),
        branch: targetBranch,
      });

      // Construct Repository object for application state
      const newRepo: Repository = {
        id: repoResponse.id,
        name: repoResponse.repoName,
        branch: repoResponse.branch,
        healthScore: 88,
        riskClassification: 'LOW RISK',
        lastAudit: 'Just now',
        description: `Connected to project "${projectName}". Real-time telemetry enabled.`,
        monitored: true,
      };

      setSuccess(true);
      setTimeout(() => {
        onRepoConnected(newRepo);
        onNavigate('overview');
      }, 900);
    } catch (err: any) {
      setApiError(err.message || 'Failed to connect repository. Please verify URL and credentials.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="p-4 md:p-8 max-w-4xl mx-auto space-y-6">
      {/* Top Navigation */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => onNavigate('create-project')}
          className="inline-flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-800 font-medium transition-colors cursor-pointer"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Project Details</span>
        </button>

        <span className="text-xs bg-indigo-50 text-indigo-700 px-3 py-1 rounded-full font-semibold border border-indigo-200">
          Project: {projectName}
        </span>
      </div>

      {/* Stepper Wizard Indicator */}
      <div className="bg-white rounded-2xl border border-slate-200/80 p-4 md:p-6 shadow-sm">
        <div className="flex items-center justify-between max-w-lg mx-auto">
          {/* Step 1 */}
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-emerald-600 text-white font-bold flex items-center justify-center text-sm shadow-md shadow-emerald-200">
              ✓
            </div>
            <div>
              <p className="text-xs font-bold text-emerald-600 uppercase tracking-wider">Step 1</p>
              <p className="text-sm font-semibold text-slate-900">Project Details</p>
            </div>
          </div>

          {/* Divider */}
          <div className="flex-1 h-0.5 bg-emerald-500 mx-4" />

          {/* Step 2 */}
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-indigo-600 text-white font-bold flex items-center justify-center text-sm shadow-md shadow-indigo-200">
              2
            </div>
            <div>
              <p className="text-xs font-bold text-indigo-600 uppercase tracking-wider">Step 2</p>
              <p className="text-sm font-semibold text-slate-900">Connect GitHub</p>
            </div>
          </div>
        </div>
      </div>

      {/* Form Card */}
      <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm p-6 md:p-8">
        <div className="mb-6">
          <h1 className="text-2xl md:text-3xl font-bold text-slate-900 tracking-tight">
            Connect GitHub Repository
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Provide the GitHub repository URL to initiate commit telemetry, PR risk classification, and code churn analysis.
          </p>
        </div>

        {/* Backend Error Alert */}
        {apiError && (
          <div className="mb-6 p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-sm flex items-start gap-2.5">
            <AlertCircle className="w-5 h-5 shrink-0 mt-0.5 text-rose-500" />
            <div>
              <p className="font-semibold">Connection Error</p>
              <p className="text-xs mt-0.5">{apiError}</p>
            </div>
          </div>
        )}

        {/* Success Alert */}
        {success && (
          <div className="mb-6 p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-sm flex items-center gap-2.5">
            <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
            <div>
              <p className="font-semibold">Repository Connected Successfully!</p>
              <p className="text-xs text-emerald-700 mt-0.5">Redirecting to Project Overview dashboard...</p>
            </div>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-6" noValidate>
          {/* Provider Selection */}
          <div>
            <label className="text-sm font-bold text-slate-900 mb-2 block">
              Git Provider
            </label>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2.5 px-4 py-2.5 rounded-xl border-2 border-indigo-600 bg-indigo-50/50 text-indigo-900 font-semibold text-sm">
                <svg className="w-5 h-5 fill-current text-slate-900" viewBox="0 0 24 24">
                  <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
                </svg>
                <span>GitHub</span>
                <span className="text-[10px] bg-indigo-200 text-indigo-800 px-1.5 py-0.5 rounded font-bold uppercase ml-1">Default</span>
              </div>
            </div>
          </div>

          {/* GitHub Repository URL */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <ExternalLink className="w-4 h-4 text-indigo-500" />
                <span>GitHub Repository URL <span className="text-rose-500">*</span></span>
              </label>

              {/* Fetch branches action button */}
              <button
                type="button"
                disabled={isFetchingBranches || !githubUrl.trim()}
                onClick={() => fetchBranchesForRepo()}
                className="text-xs font-semibold text-indigo-600 hover:text-indigo-800 disabled:opacity-40 transition-colors flex items-center gap-1 cursor-pointer"
                title="Fetch all branches from GitHub"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isFetchingBranches ? 'animate-spin' : ''}`} />
                <span>Fetch Branches</span>
              </button>
            </div>

            <div className={`relative rounded-xl border shadow-sm transition-all overflow-hidden bg-slate-50/50 flex items-center ${
              errors.githubUrl ? 'border-rose-400 focus-within:ring-2 focus-within:ring-rose-100' : 'border-slate-300 focus-within:border-indigo-600 focus-within:ring-2 focus-within:ring-indigo-100'
            }`}>
              <input
                type="url"
                disabled={isLoading}
                value={githubUrl}
                onChange={(e) => {
                  const val = e.target.value;
                  setGithubUrl(val);
                  if (errors.githubUrl) setErrors((prev) => ({ ...prev, githubUrl: undefined }));
                }}
                onBlur={() => {
                  if (githubUrl.trim() && branchSource !== 'github') {
                    fetchBranchesForRepo(githubUrl);
                  }
                }}
                placeholder="Enter your GitHub repository link (e.g. https://github.com/owner/repository)"
                className="w-full px-4 py-3 text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none bg-transparent disabled:opacity-60"
              />
            </div>
            {errors.githubUrl && (
              <p className="text-xs text-rose-600 mt-1.5 font-medium flex items-center gap-1">
                <AlertCircle className="w-3.5 h-3.5" />
                {errors.githubUrl}
              </p>
            )}
          </div>

          {/* Default Branch Dropdown */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <GitBranch className="w-4 h-4 text-indigo-500" />
                <span>Default Branch <span className="text-rose-500">*</span></span>
              </label>

              {isFetchingBranches ? (
                <span className="text-xs text-indigo-600 font-medium flex items-center gap-1.5 animate-pulse">
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  Fetching remote branches...
                </span>
              ) : branchSource === 'github' ? (
                <span className="text-[11px] font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200 flex items-center gap-1">
                  <CheckCircle2 className="w-3 h-3 text-emerald-500" />
                  {branches.length} branches loaded from GitHub
                </span>
              ) : null}
            </div>

            {/* Dropdown Menu */}
            <div className={`relative rounded-xl border shadow-sm transition-all overflow-hidden bg-slate-50/50 ${
              errors.branch ? 'border-rose-400 focus-within:ring-2 focus-within:ring-rose-100' : 'border-slate-300 focus-within:border-indigo-600 focus-within:ring-2 focus-within:ring-indigo-100'
            }`}>
              <select
                disabled={isLoading || isFetchingBranches}
                value={isCustomBranch ? '__custom__' : branch}
                onChange={(e) => {
                  const val = e.target.value;
                  if (val === '__custom__') {
                    setIsCustomBranch(true);
                  } else {
                    setIsCustomBranch(false);
                    setBranch(val);
                  }
                  if (errors.branch) setErrors((prev) => ({ ...prev, branch: undefined }));
                }}
                className="w-full px-4 py-3 text-sm text-slate-800 bg-transparent focus:outline-none cursor-pointer disabled:opacity-60"
              >
                {branches.map((b) => (
                  <option key={b} value={b} className="py-1">
                    {b} {b === 'main' || b === 'master' ? '(default)' : ''}
                  </option>
                ))}
                <option value="__custom__" className="font-semibold text-indigo-600">
                  + Enter custom branch name...
                </option>
              </select>
            </div>

            {/* If custom branch selected */}
            {isCustomBranch && (
              <div className="mt-2.5">
                <input
                  type="text"
                  autoFocus
                  placeholder="Type custom branch name (e.g. staging or release/v1.0)"
                  value={customBranchInput}
                  onChange={(e) => {
                    setCustomBranchInput(e.target.value);
                    if (errors.branch) setErrors((prev) => ({ ...prev, branch: undefined }));
                  }}
                  className="w-full px-4 py-2.5 rounded-xl border border-indigo-300 text-sm text-slate-900 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-100"
                />
              </div>
            )}

            {errors.branch ? (
              <p className="text-xs text-rose-600 mt-1.5 font-medium flex items-center gap-1">
                <AlertCircle className="w-3.5 h-3.5" />
                {errors.branch}
              </p>
            ) : (
              <p className="text-xs text-slate-400 mt-1.5">
                Target production branch analyzed for merge health, PR velocity, and security vulnerabilities.
              </p>
            )}
          </div>

          {/* Actions */}
          <div className="pt-4 border-t border-slate-100 flex items-center justify-between">
            <button
              type="button"
              onClick={() => onNavigate('create-project')}
              className="px-5 py-2.5 rounded-xl border border-slate-300 text-sm font-semibold text-slate-700 hover:bg-slate-50 transition-colors cursor-pointer"
            >
              Back
            </button>

            <button
              type="submit"
              disabled={isLoading || success}
              className="px-6 py-2.5 rounded-xl text-white text-sm font-semibold shadow-md shadow-indigo-600/25 transition-all hover:opacity-95 active:scale-95 flex items-center gap-2 cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed"
              style={{
                background: 'linear-gradient(90deg, rgba(0, 0, 0, 0.2) 0%, rgba(0, 0, 0, 0.2) 100%), linear-gradient(90deg, rgb(99, 102, 241) 0%, rgb(168, 85, 247) 100%)',
              }}
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Connecting & Verifying...</span>
                </>
              ) : success ? (
                <>
                  <ShieldCheck className="w-4 h-4" />
                  <span>Connected! Redirecting...</span>
                </>
              ) : (
                <>
                  <span>Connect Repository</span>
                  <ExternalLink className="w-4 h-4" />
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
