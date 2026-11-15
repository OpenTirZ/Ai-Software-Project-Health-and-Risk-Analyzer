import React, { useState } from 'react';
import type { PageView, ActivityTab } from '../types';
import { commitsData, pullRequestsData, issuesData } from '../data/mockData';
import { 
  GitCommit, 
  GitPullRequest, 
  AlertCircle, 
  Search, 
  FileCode2 
} from 'lucide-react';

interface ActivityProps {
  selectedRepo: string;
  onNavigate: (view: PageView) => void;
}

export const Activity: React.FC<ActivityProps> = ({ selectedRepo }) => {
  const [activeTab, setActiveTab] = useState<ActivityTab>('commits');
  const [searchQuery, setSearchQuery] = useState('');

  return (
    <div className="p-6 md:p-8 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl md:text-3xl font-bold text-slate-900 tracking-tight">
          Project Activity
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          Commits, pull requests and issues telemetry for <span className="font-semibold text-slate-700">{selectedRepo}</span>.
        </p>
      </div>

      {/* Tabs Control */}
      <div className="flex items-center gap-2 p-1 bg-slate-100 rounded-xl max-w-md">
        <button
          onClick={() => {
            setActiveTab('commits');
            setSearchQuery('');
          }}
          className={`flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-bold transition-all cursor-pointer ${
            activeTab === 'commits'
              ? 'bg-white text-blue-600 shadow-sm'
              : 'text-slate-600 hover:text-slate-900'
          }`}
        >
          <GitCommit className="w-3.5 h-3.5" />
          <span>Commits</span>
        </button>

        <button
          onClick={() => {
            setActiveTab('pull-requests');
            setSearchQuery('');
          }}
          className={`flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-bold transition-all cursor-pointer ${
            activeTab === 'pull-requests'
              ? 'bg-white text-blue-600 shadow-sm'
              : 'text-slate-600 hover:text-slate-900'
          }`}
        >
          <GitPullRequest className="w-3.5 h-3.5" />
          <span>Pull Requests</span>
        </button>

        <button
          onClick={() => {
            setActiveTab('issues');
            setSearchQuery('');
          }}
          className={`flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-bold transition-all cursor-pointer ${
            activeTab === 'issues'
              ? 'bg-white text-blue-600 shadow-sm'
              : 'text-slate-600 hover:text-slate-900'
          }`}
        >
          <AlertCircle className="w-3.5 h-3.5" />
          <span>Issues</span>
        </button>
      </div>

      {/* COMMITS VIEW */}
      {activeTab === 'commits' && (
        <div className="space-y-4">
          {/* Controls */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 bg-white p-3 rounded-xl border border-slate-200/90 shadow-sm">
            <div className="flex items-center gap-2 flex-1">
              <Search className="w-4 h-4 text-slate-400 ml-1" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search commits by message, hash, author..."
                className="w-full text-xs text-slate-800 placeholder:text-slate-400 focus:outline-none bg-transparent"
              />
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-500 font-medium px-2 py-1 rounded bg-slate-100 border border-slate-200">
                Author: All
              </span>
              <span className="text-xs text-slate-500 font-medium px-2 py-1 rounded bg-slate-100 border border-slate-200">
                Branch: main
              </span>
            </div>
          </div>

          {/* Commits Table */}
          <div className="bg-white rounded-2xl border border-slate-200/90 shadow-sm overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50/70 text-slate-600 text-xs font-bold uppercase tracking-wider">
                    <th className="py-4 px-6">Commit</th>
                    <th className="py-4 px-6">Message</th>
                    <th className="py-4 px-6">Author</th>
                    <th className="py-4 px-6">Date</th>
                    <th className="py-4 px-6 text-right">Files</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-sm">
                  {commitsData
                    .filter((c) =>
                      c.message.toLowerCase().includes(searchQuery.toLowerCase()) ||
                      c.hash.toLowerCase().includes(searchQuery.toLowerCase()) ||
                      c.author.toLowerCase().includes(searchQuery.toLowerCase())
                    )
                    .map((commit) => (
                      <tr key={commit.id} className="hover:bg-slate-50/80 transition-colors">
                        <td className="py-4 px-6 font-mono text-xs font-bold text-indigo-600">
                          <span className="px-2 py-0.5 rounded bg-indigo-50 border border-indigo-200">
                            {commit.hash}
                          </span>
                        </td>
                        <td className="py-4 px-6 font-medium text-slate-900">
                          {commit.message}
                        </td>
                        <td className="py-4 px-6 text-xs text-slate-600">
                          {commit.author}
                        </td>
                        <td className="py-4 px-6 text-xs text-slate-400">
                          {commit.date}
                        </td>
                        <td className="py-4 px-6 text-right text-xs font-bold text-slate-700">
                          <span className="inline-flex items-center gap-1">
                            <FileCode2 className="w-3.5 h-3.5 text-slate-400" />
                            {commit.files} files
                          </span>
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* PULL REQUESTS VIEW */}
      {activeTab === 'pull-requests' && (
        <div className="space-y-4">
          {/* Summary status pill bar */}
          <div className="flex items-center justify-between bg-white p-4 rounded-xl border border-slate-200/90 shadow-sm">
            <div>
              <h2 className="text-base font-bold text-slate-900">
                Pull Requests Overview
              </h2>
              <p className="text-xs text-slate-500">
                Open review queue and turnaround velocities
              </p>
            </div>
            <div className="flex items-center gap-2 text-xs font-bold">
              <span className="px-3 py-1 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
                12 Open
              </span>
              <span className="px-3 py-1 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200">
                7 Merged
              </span>
              <span className="px-3 py-1 rounded-full bg-slate-100 text-slate-600 border border-slate-200">
                2 Closed
              </span>
            </div>
          </div>

          {/* PR Table */}
          <div className="bg-white rounded-2xl border border-slate-200/90 shadow-sm overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50/70 text-slate-600 text-xs font-bold uppercase tracking-wider">
                    <th className="py-4 px-6">PR #</th>
                    <th className="py-4 px-6">Title</th>
                    <th className="py-4 px-6">Author</th>
                    <th className="py-4 px-6">Age</th>
                    <th className="py-4 px-6 text-right">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-sm">
                  {pullRequestsData.map((pr) => (
                    <tr key={pr.id} className="hover:bg-slate-50/80 transition-colors">
                      <td className="py-4 px-6 font-mono text-xs font-bold text-indigo-600">
                        #{pr.prNumber}
                      </td>
                      <td className="py-4 px-6 font-medium text-slate-900">
                        {pr.title}
                      </td>
                      <td className="py-4 px-6 text-xs text-slate-600">
                        {pr.author}
                      </td>
                      <td className="py-4 px-6 text-xs font-mono">
                        <span className={`px-2 py-0.5 rounded ${
                          parseInt(pr.age) >= 48 ? 'bg-rose-50 text-rose-700 font-bold' : 'text-slate-600'
                        }`}>
                          {pr.age}
                        </span>
                      </td>
                      <td className="py-4 px-6 text-right">
                        <span
                          className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-bold ${
                            pr.status === 'Open'
                              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                              : pr.status === 'Merged'
                              ? 'bg-indigo-50 text-indigo-700 border border-indigo-200'
                              : 'bg-slate-100 text-slate-600 border border-slate-200'
                          }`}
                        >
                          {pr.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ISSUES VIEW */}
      {activeTab === 'issues' && (
        <div className="space-y-4">
          {/* Controls */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 bg-white p-3 rounded-xl border border-slate-200/90 shadow-sm">
            <div className="flex items-center gap-2 flex-1">
              <Search className="w-4 h-4 text-slate-400 ml-1" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search issues by title or author..."
                className="w-full text-xs text-slate-800 placeholder:text-slate-400 focus:outline-none bg-transparent"
              />
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-500 font-medium px-2 py-1 rounded bg-slate-100 border border-slate-200">
                Status: All ▼
              </span>
              <span className="text-xs text-slate-500 font-medium px-2 py-1 rounded bg-slate-100 border border-slate-200">
                Priority: All ▼
              </span>
            </div>
          </div>

          {/* Issues Table */}
          <div className="bg-white rounded-2xl border border-slate-200/90 shadow-sm overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50/70 text-slate-600 text-xs font-bold uppercase tracking-wider">
                    <th className="py-4 px-6">Issue</th>
                    <th className="py-4 px-6">Title</th>
                    <th className="py-4 px-6">Author</th>
                    <th className="py-4 px-6">Priority</th>
                    <th className="py-4 px-6">Status</th>
                    <th className="py-4 px-6 text-right">Updated</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-sm">
                  {issuesData
                    .filter((is) =>
                      is.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
                      is.author.toLowerCase().includes(searchQuery.toLowerCase())
                    )
                    .map((issue) => (
                      <tr key={issue.id} className="hover:bg-slate-50/80 transition-colors">
                        <td className="py-4 px-6 font-mono text-xs font-bold text-indigo-600">
                          #{issue.issueNumber}
                        </td>
                        <td className="py-4 px-6 font-medium text-slate-900">
                          {issue.title}
                        </td>
                        <td className="py-4 px-6 text-xs text-slate-600">
                          {issue.author}
                        </td>
                        <td className="py-4 px-6">
                          <span
                            className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-bold ${
                              issue.priority === 'High'
                                ? 'bg-rose-50 text-rose-700 border border-rose-200'
                                : issue.priority === 'Medium'
                                ? 'bg-amber-50 text-amber-700 border border-amber-200'
                                : 'bg-slate-100 text-slate-700 border border-slate-200'
                            }`}
                          >
                            {issue.priority}
                          </span>
                        </td>
                        <td className="py-4 px-6">
                          <span
                            className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-bold ${
                              issue.status === 'Open'
                                ? 'bg-rose-50 text-rose-700 border border-rose-200'
                                : 'bg-slate-100 text-slate-600 border border-slate-200'
                            }`}
                          >
                            {issue.status}
                          </span>
                        </td>
                        <td className="py-4 px-6 text-right text-xs text-slate-400">
                          {issue.updated}
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
