import React, { useState, useEffect } from 'react';
import type { PageView } from '../types';
import {
  dataSyncApi,
  type ProjectResponse,
} from '../services/api';
import {
  GitCommit,
  ExternalLink,
  RefreshCw,
  Users,
  ArrowLeft,
} from 'lucide-react';

interface ContributorsProps {
  project: ProjectResponse | null;
  onNavigate: (view: PageView) => void;
}

export const Contributors: React.FC<ContributorsProps> = ({
  project,
  onNavigate,
}) => {
  const [contributors, setContributors] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isSyncing, setIsSyncing] = useState<boolean>(false);
  const [syncFeedback, setSyncFeedback] = useState<string | null>(null);

  const loadContributors = async (projectId: string) => {
    setIsLoading(true);

    try {
      const data = await dataSyncApi.getContributors(projectId);
      setContributors(Array.isArray(data) ? data : []);
    } catch (err: any) {
      console.warn('Could not load contributors:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (project?.id) {
      loadContributors(project.id);
    }
  }, [project?.id]);

  const handleSyncContributors = async () => {
    if (!project?.id) return;

    setIsSyncing(true);
    setSyncFeedback('Synchronizing contributors from GitHub...');

    try {
      await dataSyncApi.syncContributors(project.id);
      setSyncFeedback('Contributors synchronized successfully!');
      await loadContributors(project.id);
      setTimeout(() => setSyncFeedback(null), 3500);
    } catch (err: any) {
      setSyncFeedback(
        `Sync note: ${err.message || 'Contributor sync failed.'}`,
      );
      setTimeout(() => setSyncFeedback(null), 4000);
    } finally {
      setIsSyncing(false);
    }
  };

  if (!project) {
    return (
      <div className="mx-auto max-w-4xl p-8 text-center">
        <div className="rounded-xl border border-[#9ED4C8] bg-white p-8">
          <p className="text-sm text-[#3F5F5C]">
            Please select an active project to view team contributors.
          </p>
          <button
            onClick={() => onNavigate('projects')}
            className="mt-4 rounded-lg bg-[#0B6B63] px-4 py-2 text-sm font-semibold text-white hover:bg-[#084F49] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0B6B63]"
          >
            View Projects
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-5 md:p-8">

      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <button
            onClick={() => onNavigate('overview')}
            className="mb-2 inline-flex items-center gap-1.5 text-sm font-medium text-[#5F7C79] hover:text-[#0B6B63] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0B6B63]"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Project Overview
          </button>

          <h1 className="text-2xl font-bold tracking-tight text-[#0E2A2A] md:text-3xl">
            Team &amp; Contributors
          </h1>

          <p className="mt-1 text-sm text-[#3F5F5C]">
            Active GitHub repository contributors and commit share for{' '}
            <span className="font-semibold text-[#0E2A2A]">
              {project.name}
            </span>
            .
          </p>
        </div>

        <button
          onClick={handleSyncContributors}
          disabled={isSyncing}
          className="inline-flex shrink-0 items-center justify-center gap-2 rounded-lg bg-[#0B6B63] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#084F49] disabled:cursor-not-allowed disabled:opacity-60 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0B6B63]"
        >
          <RefreshCw className="h-4 w-4" />
          {isSyncing ? 'Synchronizing...' : 'Sync Contributors'}
        </button>
      </div>

      {syncFeedback && (
        <div
          role="status"
          className="rounded-lg border border-[#9ED4C8] bg-white px-4 py-3 text-sm text-[#3F5F5C]"
        >
          {syncFeedback}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="flex items-center gap-4 rounded-xl border border-[#9ED4C8] bg-white p-5">
          <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-[#CDEFE6] text-[#0B6B63]">
            <Users className="h-5 w-5" />
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-[#5F7C79]">
              Total Contributors
            </p>
            <p className="mt-1 text-2xl font-bold tabular-nums text-[#0E2A2A]">
              {contributors.length}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-4 rounded-xl border border-[#9ED4C8] bg-white p-5">
          <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-[#CDEFE6] text-[#0B6B63]">
            <GitCommit className="h-5 w-5" />
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-[#5F7C79]">
              Recorded Contributions
            </p>
            <p className="mt-1 text-2xl font-bold tabular-nums text-[#0E2A2A]">
              {contributors.reduce(
                (total, contributor) =>
                  total +
                  Number(
                    contributor.contributions || contributor.commits || 1,
                  ),
                0,
              )}
            </p>
          </div>
        </div>
      </div>

      <section className="overflow-hidden rounded-xl border border-[#9ED4C8] bg-white">
        <div className="flex flex-col justify-between gap-2 border-b border-[#9ED4C8] px-5 py-4 sm:flex-row sm:items-center">
          <div>
            <h2 className="text-base font-semibold text-[#0E2A2A]">
              Repository Contributors
            </h2>
            <p className="mt-1 text-xs text-[#5F7C79]">
              GitHub accounts and their recorded contribution counts.
            </p>
          </div>

          <span className="w-fit rounded-md border border-[#9ED4C8] bg-[#EAF8F3] px-2.5 py-1 text-xs font-semibold tabular-nums text-[#3F5F5C]">
            {contributors.length} members
          </span>
        </div>

        {isLoading ? (
          <div className="px-6 py-14 text-center text-sm text-[#5F7C79]">
            Loading contributor data...
          </div>
        ) : contributors.length === 0 ? (
          <div className="px-6 py-14 text-center">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-[#CDEFE6] text-[#0B6B63]">
              <Users className="h-6 w-6" />
            </div>
            <h3 className="mt-4 text-base font-semibold text-[#0E2A2A]">
              No Contributors Found
            </h3>
            <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-[#5F7C79]">
              Click Sync Contributors to ingest contributor activity from
              GitHub.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[620px] border-collapse text-left">
              <thead>
                <tr className="border-b border-[#9ED4C8] bg-[#EAF8F3] text-xs font-semibold uppercase tracking-wide text-[#3F5F5C]">
                  <th className="px-5 py-4">Contributor</th>
                  <th className="px-5 py-4">GitHub Username</th>
                  <th className="px-5 py-4">Contributions</th>
                  <th className="px-5 py-4 text-right">GitHub Profile</th>
                </tr>
              </thead>

              <tbody className="divide-y divide-[#9ED4C8] text-sm">
                {contributors.map((contrib, index) => {
                  const username =
                    contrib.github_username ||
                    contrib.login ||
                    contrib.username ||
                    'unknown';

                  const count =
                    contrib.contributions || contrib.commits || 1;

                  const initial = username.charAt(0).toUpperCase();

                  return (
                    <tr
                      key={contrib._id || username || index}
                      className="hover:bg-[#EAF8F3]"
                    >
                      <td className="px-5 py-4">
                        <div className="flex items-center gap-3">
                          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-[#9ED4C8] bg-[#CDEFE6] text-sm font-bold text-[#0B6B63]">
                            {initial}
                          </div>

                          <div>
                            <p className="font-semibold text-[#0E2A2A]">
                              {username}
                            </p>
                            <p className="mt-0.5 text-xs text-[#5F7C79]">
                              Repository contributor
                            </p>
                          </div>
                        </div>
                      </td>

                      <td className="px-5 py-4">
                        <span className="rounded-md border border-[#9ED4C8] bg-[#EAF8F3] px-2.5 py-1.5 font-mono text-xs text-[#3F5F5C]">
                          @{username}
                        </span>
                      </td>

                      <td className="px-5 py-4">
                        <div className="inline-flex items-center gap-2">
                          <GitCommit className="h-4 w-4 text-[#0B6B63]" />
                          <span className="font-semibold tabular-nums text-[#0E2A2A]">
                            {count}
                          </span>
                        </div>
                      </td>

                      <td className="px-5 py-4 text-right">
                        <a
                          href={`https://github.com/${username}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1.5 rounded-md px-2 py-1.5 text-xs font-semibold text-[#0B6B63] hover:bg-[#CDEFE6] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0B6B63]"
                        >
                          View Profile
                          <ExternalLink className="h-3.5 w-3.5" />
                        </a>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
};
