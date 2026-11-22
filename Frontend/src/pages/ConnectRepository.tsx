
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
  RefreshCw,
} from 'lucide-react';
import { repositoryApi, type ProjectResponse } from '../services/api';

interface ConnectRepositoryProps {
  project: ProjectResponse | null;
  onRepoConnected: (repo: Repository) => void;
  onNavigate: (view: PageView) => void;
}

const githubRegex =
  /^https:\/\/github\.com\/[a-zA-Z0-9_.-]+\/[a-zA-Z0-9_.-]+\/?$/;

export const ConnectRepository: React.FC<ConnectRepositoryProps> = ({
  project,
  onRepoConnected,
  onNavigate,
}) => {
  const [githubUrl, setGithubUrl] = useState('');
  const [branch, setBranch] = useState('main');
  const [branches, setBranches] = useState<string[]>([
    'main',
    'master',
    'develop',
  ]);
  const [isFetchingBranches, setIsFetchingBranches] = useState(false);
  const [branchSource, setBranchSource] = useState<
    'github' | 'default' | null
  >(null);
  const [isCustomBranch, setIsCustomBranch] = useState(false);
  const [customBranchInput, setCustomBranchInput] = useState('');

  const [errors, setErrors] = useState<{
    githubUrl?: string;
    branch?: string;
  }>({});
  const [apiError, setApiError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  const projectName = project?.name || 'New Project';
  const projectId = project?.id || 'proj_default';

  const fetchBranchesForRepo = async (urlToFetch?: string) => {
    const url = (urlToFetch || githubUrl).trim();

    if (!url || !githubRegex.test(url)) return;

    setIsFetchingBranches(true);
    setApiError(null);

    try {
      const response = await repositoryApi.fetchBranches(url);

      if (response.branches && response.branches.length > 0) {
        setBranches(response.branches);
        setBranchSource(response.source);

        if (response.branches.includes('main')) {
          setBranch('main');
        } else if (response.branches.includes('master')) {
          setBranch('master');
        } else {
          setBranch(response.branches[0]);
        }

        setIsCustomBranch(false);
        setCustomBranchInput('');
      }
    } catch {
      // Keep the fallback branch options if fetching is unavailable.
    } finally {
      setIsFetchingBranches(false);
    }
  };

  const validate = (): boolean => {
    const newErrors: { githubUrl?: string; branch?: string } = {};

    if (!githubUrl.trim()) {
      newErrors.githubUrl = 'GitHub repository URL is required.';
    } else if (!githubRegex.test(githubUrl.trim())) {
      newErrors.githubUrl =
        'Invalid URL. Enter a valid GitHub repository URL (e.g. https://github.com/owner/repository).';
    }

    const selectedBranch = isCustomBranch
      ? customBranchInput.trim()
      : branch.trim();

    if (!selectedBranch) {
      newErrors.branch = 'Please select or enter a branch name.';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setApiError(null);

    if (!validate()) return;

    const targetBranch = isCustomBranch
      ? customBranchInput.trim()
      : branch.trim() || 'main';

    setIsLoading(true);

    try {
      const repoResponse = await repositoryApi.connectRepository({
        projectId,
        githubUrl: githubUrl.trim(),
        branch: targetBranch,
      });

      const newRepo: Repository = {
        id: repoResponse.id,
        name: repoResponse.repoName,
        branch: repoResponse.branch,
        description: `Connected to project "${projectName}". Real-time telemetry enabled.`,
        monitored: true,
      };

      setSuccess(true);

      setTimeout(() => {
        onRepoConnected(newRepo);
        onNavigate('overview');
      }, 900);
    } catch (err: any) {
      setApiError(
        err.message ||
          'Failed to connect repository. Please verify URL and credentials.'
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main className="mx-auto w-full max-w-4xl space-y-6 p-4 sm:p-6 lg:p-8">
      {/* Navigation and project context */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <button
          type="button"
          onClick={() => onNavigate('create-project')}
          className="inline-flex items-center gap-2 self-start text-sm font-medium text-slate-600 hover:text-[#0B6B63] focus:outline-none focus:ring-2 focus:ring-teal-700 focus:ring-offset-2"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Project Details
        </button>

        <span className="inline-flex w-fit items-center rounded-lg border border-[#9ED4C8] bg-white px-3 py-2 text-xs font-medium text-slate-700">
          Project:
          <span className="ml-1 font-semibold text-[#0B6B63]">
            {projectName}
          </span>
        </span>
      </div>

      {/* Setup progress */}
      <section className="rounded-xl border border-[#9ED4C8] bg-white p-5 sm:p-6">
        <div className="mx-auto flex max-w-lg items-center">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#0B6B63] text-white">
              <CheckCircle2 className="h-5 w-5" />
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-[#0B6B63]">
                Step 1
              </p>
              <p className="text-sm font-semibold text-slate-900">
                Project Details
              </p>
            </div>
          </div>

          <div className="mx-4 h-px flex-1 bg-[#0B6B63]" />

          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#0B6B63] text-sm font-bold text-white">
              2
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-[#0B6B63]">
                Step 2
              </p>
              <p className="text-sm font-semibold text-slate-900">
                Connect GitHub
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Connection form */}
      <section className="rounded-xl border border-[#9ED4C8] bg-white p-5 sm:p-8">
        <div className="mb-7">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-[#0B6B63]">
            Repository integration
          </p>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
            Connect GitHub Repository
          </h1>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            Provide the GitHub repository URL to initiate commit telemetry,
            pull request risk classification, and code churn analysis.
          </p>
        </div>

        {apiError && (
          <div
            role="alert"
            className="mb-6 flex items-start gap-3 rounded-lg border border-[#CC1F2E]/20 bg-[#CC1F2E]/5 p-4 text-sm text-[#CC1F2E]"
          >
            <AlertCircle className="mt-0.5 h-5 w-5 shrink-0" />
            <div>
              <p className="font-semibold">Connection Error</p>
              <p className="mt-1 text-xs">{apiError}</p>
            </div>
          </div>
        )}

        {success && (
          <div
            role="status"
            className="mb-6 flex items-center gap-3 rounded-lg border border-[#0B6B63]/20 bg-[#CDEFE6] p-4 text-sm text-[#0B6B63]"
          >
            <CheckCircle2 className="h-5 w-5 shrink-0" />
            <div>
              <p className="font-semibold">
                Repository Connected Successfully!
              </p>
              <p className="mt-1 text-xs">
                Redirecting to Project Overview...
              </p>
            </div>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-7" noValidate>
          {/* Provider */}
          <div>
            <p className="mb-3 text-sm font-semibold text-slate-900">
              Git Provider
            </p>

            <div className="inline-flex items-center gap-3 rounded-lg border border-[#0B6B63] bg-[#CDEFE6] px-4 py-3 text-sm font-semibold text-[#0B6B63]">
              <svg
                className="h-5 w-5 fill-current"
                viewBox="0 0 24 24"
                aria-hidden="true"
              >
                <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
              </svg>
              GitHub
              <span className="rounded bg-white px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-[#0B6B63]">
                Default
              </span>
            </div>
          </div>

          {/* Repository URL */}
          <div>
            <div className="mb-2 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <label
                htmlFor="github-url"
                className="flex items-center gap-2 text-sm font-semibold text-slate-900"
              >
                <ExternalLink className="h-4 w-4 text-[#0B6B63]" />
                GitHub Repository URL
                <span className="text-[#CC1F2E]">*</span>
              </label>

              <button
                type="button"
                disabled={isFetchingBranches || !githubUrl.trim()}
                onClick={() => fetchBranchesForRepo()}
                title="Fetch all branches from GitHub"
                className="inline-flex items-center gap-2 self-start text-xs font-semibold text-[#0B6B63] hover:underline focus:outline-none focus:ring-2 focus:ring-teal-700 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-40 sm:self-auto"
              >
                <RefreshCw className="h-3.5 w-3.5" />
                {isFetchingBranches ? 'Fetching branches...' : 'Fetch Branches'}
              </button>
            </div>

            <input
              id="github-url"
              type="url"
              disabled={isLoading}
              value={githubUrl}
              onChange={(event) => {
                const value = event.target.value;
                setGithubUrl(value);

                if (errors.githubUrl) {
                  setErrors((previous) => ({
                    ...previous,
                    githubUrl: undefined,
                  }));
                }

                if (branchSource === 'github') {
                  setBranchSource(null);
                }
              }}
              onBlur={() => {
                if (githubUrl.trim() && branchSource !== 'github') {
                  fetchBranchesForRepo(githubUrl);
                }
              }}
              placeholder="https://github.com/owner/repository"
              aria-invalid={Boolean(errors.githubUrl)}
              aria-describedby={
                errors.githubUrl ? 'github-url-error' : 'github-url-help'
              }
              className={`w-full rounded-lg border bg-white px-4 py-3 text-sm text-slate-900 outline-none placeholder:text-slate-400 focus:ring-2 focus:ring-[#0B6B63]/15 disabled:opacity-60 ${
                errors.githubUrl
                  ? 'border-[#CC1F2E] focus:border-[#CC1F2E]'
                  : 'border-[#9ED4C8] focus:border-[#0B6B63]'
              }`}
            />

            {errors.githubUrl ? (
              <p
                id="github-url-error"
                className="mt-2 flex items-center gap-1.5 text-xs font-medium text-[#CC1F2E]"
              >
                <AlertCircle className="h-3.5 w-3.5" />
                {errors.githubUrl}
              </p>
            ) : (
              <p id="github-url-help" className="mt-2 text-xs text-slate-500">
                Enter the HTTPS URL of the GitHub repository you want to monitor.
              </p>
            )}
          </div>

          {/* Branch selection */}
          <div>
            <div className="mb-2 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <label
                htmlFor="default-branch"
                className="flex items-center gap-2 text-sm font-semibold text-slate-900"
              >
                <GitBranch className="h-4 w-4 text-[#0B6B63]" />
                Default Branch
                <span className="text-[#CC1F2E]">*</span>
              </label>

              {isFetchingBranches ? (
                <span className="inline-flex items-center gap-2 text-xs font-medium text-[#B45309]">
                  <Loader2 className="h-3.5 w-3.5" />
                  Fetching remote branches...
                </span>
              ) : branchSource === 'github' ? (
                <span className="inline-flex items-center gap-1.5 text-xs font-medium text-[#0B6B63]">
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  {branches.length} branches loaded from GitHub
                </span>
              ) : null}
            </div>

            <select
              id="default-branch"
              disabled={isLoading || isFetchingBranches}
              value={isCustomBranch ? '__custom__' : branch}
              onChange={(event) => {
                const value = event.target.value;

                if (value === '__custom__') {
                  setIsCustomBranch(true);
                } else {
                  setIsCustomBranch(false);
                  setBranch(value);
                }

                if (errors.branch) {
                  setErrors((previous) => ({
                    ...previous,
                    branch: undefined,
                  }));
                }
              }}
              aria-invalid={Boolean(errors.branch)}
              className={`w-full rounded-lg border bg-white px-4 py-3 text-sm text-slate-900 outline-none focus:border-[#0B6B63] focus:ring-2 focus:ring-[#0B6B63]/15 disabled:opacity-60 ${
                errors.branch ? 'border-[#CC1F2E]' : 'border-[#9ED4C8]'
              }`}
            >
              {branches.map((item) => (
                <option key={item} value={item}>
                  {item} {item === 'main' || item === 'master' ? '(default)' : ''}
                </option>
              ))}
              <option value="__custom__">+ Enter custom branch name...</option>
            </select>

            {isCustomBranch && (
              <input
                type="text"
                autoFocus
                disabled={isLoading}
                placeholder="e.g. staging or release/v1.0"
                value={customBranchInput}
                onChange={(event) => {
                  setCustomBranchInput(event.target.value);

                  if (errors.branch) {
                    setErrors((previous) => ({
                      ...previous,
                      branch: undefined,
                    }));
                  }
                }}
                className="mt-3 w-full rounded-lg border border-[#9ED4C8] bg-white px-4 py-3 text-sm text-slate-900 outline-none placeholder:text-slate-400 focus:border-[#0B6B63] focus:ring-2 focus:ring-[#0B6B63]/15"
              />
            )}

            {errors.branch ? (
              <p className="mt-2 flex items-center gap-1.5 text-xs font-medium text-[#CC1F2E]">
                <AlertCircle className="h-3.5 w-3.5" />
                {errors.branch}
              </p>
            ) : (
              <p className="mt-2 text-xs leading-5 text-slate-500">
                Target branch analyzed for merge health, pull request velocity,
                and repository health indicators.
              </p>
            )}
          </div>

          {/* Actions */}
          <div className="flex flex-col-reverse gap-3 border-t border-[#9ED4C8] pt-5 sm:flex-row sm:items-center sm:justify-between">
            <button
              type="button"
              onClick={() => onNavigate('create-project')}
              disabled={isLoading}
              className="inline-flex min-h-11 items-center justify-center rounded-lg border border-[#9ED4C8] px-5 text-sm font-semibold text-slate-700 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-teal-700 focus:ring-offset-2 disabled:opacity-60"
            >
              Back
            </button>

            <button
              type="submit"
              disabled={isLoading || success}
              className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-[#0B6B63] px-6 text-sm font-semibold text-white hover:bg-[#084F49] focus:outline-none focus:ring-2 focus:ring-teal-700 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isLoading ? (
                <>
                  <Loader2 className="h-4 w-4" />
                  Connecting & Verifying...
                </>
              ) : success ? (
                <>
                  <ShieldCheck className="h-4 w-4" />
                  Connected! Redirecting...
                </>
              ) : (
                <>
                  Connect Repository
                  <ExternalLink className="h-4 w-4" />
                </>
              )}
            </button>
          </div>
        </form>
      </section>
    </main>
  );
};
