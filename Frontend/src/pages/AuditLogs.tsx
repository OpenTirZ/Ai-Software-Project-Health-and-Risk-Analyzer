import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { adminApi, type AuditLog } from '../services/api';
import {
  ScrollText,
  Search,
  Filter,
  ChevronUp,
  ChevronDown,
  Loader2,
  AlertTriangle,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';

type SortField = 'action' | 'actor_id' | 'target_id' | 'detail' | 'created_at';
type SortDir = 'asc' | 'desc';

const PAGE_SIZE = 20;

const ACTION_TYPES = [
  'All Actions',
  'user.login',
  'user.signup',
  'user.role_change',
  'user.activate',
  'user.deactivate',
  'project.create',
  'project.archive',
  'project.delete',
  'report.generate',
  'appeal.submit',
  'appeal.review',
  'sync.commits',
  'sync.prs',
  'sync.issues',
];

export const AuditLogs: React.FC = () => {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [searchTerm, setSearchTerm] = useState('');
  const [actionFilter, setActionFilter] = useState('All Actions');

  // Sort
  const [sortField, setSortField] = useState<SortField>('created_at');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  // Pagination
  const [page, setPage] = useState(1);

  const loadLogs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await adminApi.getAuditLogs(500);
      setLogs(Array.isArray(data) ? data : []);
    } catch (err: any) {
      setError(err.message || 'Failed to load audit logs');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadLogs();
  }, [loadLogs]);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortField(field);
      setSortDir('asc');
    }
    setPage(1);
  };

  const filtered = useMemo(() => {
    let result = [...logs];

    // Action filter
    if (actionFilter !== 'All Actions') {
      result = result.filter((l) => l.action === actionFilter);
    }

    // Search
    if (searchTerm.trim()) {
      const q = searchTerm.trim().toLowerCase();
      result = result.filter(
        (l) =>
          l.action?.toLowerCase().includes(q) ||
          l.actor_id?.toLowerCase().includes(q) ||
          l.target_id?.toLowerCase().includes(q) ||
          l.detail?.toLowerCase().includes(q)
      );
    }

    // Sort
    result.sort((a, b) => {
      const valA = (a[sortField] ?? '') as string;
      const valB = (b[sortField] ?? '') as string;
      const cmp = valA.localeCompare(valB);
      return sortDir === 'asc' ? cmp : -cmp;
    });

    return result;
  }, [logs, actionFilter, searchTerm, sortField, sortDir]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const paginated = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  const SortHeader: React.FC<{ field: SortField; label: string }> = ({ field, label }) => (
    <button
      onClick={() => handleSort(field)}
      className="inline-flex items-center gap-1 text-xs font-semibold text-slate-500 uppercase tracking-wider hover:text-slate-700"
    >
      {label}
      {sortField === field &&
        (sortDir === 'asc' ? (
          <ChevronUp className="h-3 w-3" />
        ) : (
          <ChevronDown className="h-3 w-3" />
        ))}
    </button>
  );

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#EAF8F3]">
            <ScrollText className="h-5 w-5 text-[#0B6B63]" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Audit Trail</h1>
            <p className="text-sm text-slate-500">
              Platform-wide activity log · {filtered.length} entries
            </p>
          </div>
        </div>
        <button
          onClick={loadLogs}
          disabled={loading}
          className="flex items-center gap-1.5 rounded-lg border border-[#9ED4C8] bg-[#EAF8F3] px-4 py-2 text-sm font-medium text-[#0B6B63] hover:bg-[#CDEFE6] disabled:opacity-50 transition-colors"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          <AlertTriangle className="mr-2 inline-block h-4 w-4" />
          {error}
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-col gap-3 sm:flex-row">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => {
              setSearchTerm(e.target.value);
              setPage(1);
            }}
            placeholder="Search by actor, target, or detail..."
            className="w-full rounded-lg border border-slate-200 bg-white py-2 pl-10 pr-4 text-sm text-slate-700 placeholder:text-slate-400 focus:border-[#0B6B63] focus:outline-none focus:ring-1 focus:ring-[#0B6B63]"
          />
        </div>
        <div className="relative">
          <Filter className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <select
            value={actionFilter}
            onChange={(e) => {
              setActionFilter(e.target.value);
              setPage(1);
            }}
            className="appearance-none rounded-lg border border-slate-200 bg-white py-2 pl-10 pr-8 text-sm text-slate-700 focus:border-[#0B6B63] focus:outline-none focus:ring-1 focus:ring-[#0B6B63]"
          >
            {ACTION_TYPES.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Table */}
      {loading && logs.length === 0 ? (
        <div className="flex h-48 items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-[#0B6B63]" />
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-slate-100 bg-slate-50">
                  <th className="px-4 py-3">
                    <SortHeader field="action" label="Action" />
                  </th>
                  <th className="px-4 py-3">
                    <SortHeader field="actor_id" label="Actor" />
                  </th>
                  <th className="px-4 py-3">
                    <SortHeader field="target_id" label="Target" />
                  </th>
                  <th className="px-4 py-3 hidden lg:table-cell">
                    <SortHeader field="detail" label="Detail" />
                  </th>
                  <th className="px-4 py-3 text-right">
                    <SortHeader field="created_at" label="Timestamp" />
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {paginated.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="p-8 text-center text-sm text-slate-400">
                      No audit log entries match your filters.
                    </td>
                  </tr>
                ) : (
                  paginated.map((log) => (
                    <tr key={log.id} className="hover:bg-slate-50/60 transition-colors">
                      <td className="px-4 py-3">
                        <span className="inline-block rounded bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
                          {log.action}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-sm text-slate-600 font-mono text-xs">
                        {log.actor_id ? log.actor_id.slice(0, 12) + '…' : '—'}
                      </td>
                      <td className="px-4 py-3 text-sm text-slate-600 font-mono text-xs">
                        {log.target_id ? log.target_id.slice(0, 12) + '…' : '—'}
                      </td>
                      <td className="px-4 py-3 text-sm text-slate-500 max-w-xs truncate hidden lg:table-cell">
                        {log.detail || '—'}
                      </td>
                      <td className="px-4 py-3 text-right text-xs text-slate-400 whitespace-nowrap">
                        {log.created_at
                          ? new Date(log.created_at).toLocaleString('en-US', {
                              month: 'short',
                              day: 'numeric',
                              hour: '2-digit',
                              minute: '2-digit',
                            })
                          : '—'}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between border-t border-slate-100 px-4 py-3">
              <p className="text-xs text-slate-400">
                Showing {(page - 1) * PAGE_SIZE + 1}–
                {Math.min(page * PAGE_SIZE, filtered.length)} of {filtered.length}
              </p>
              <div className="flex gap-1">
                <button
                  disabled={page === 1}
                  onClick={() => setPage((p) => p - 1)}
                  className="rounded-md border border-slate-200 p-1.5 text-slate-500 hover:bg-slate-50 disabled:opacity-40"
                >
                  <ChevronLeft className="h-4 w-4" />
                </button>
                <span className="flex items-center px-3 text-xs font-medium text-slate-600">
                  {page} / {totalPages}
                </span>
                <button
                  disabled={page === totalPages}
                  onClick={() => setPage((p) => p + 1)}
                  className="rounded-md border border-slate-200 p-1.5 text-slate-500 hover:bg-slate-50 disabled:opacity-40"
                >
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default AuditLogs;
