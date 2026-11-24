import React, { useState, useMemo } from 'react';
import { AlertCircle, Search, ChevronDown, ChevronUp, ExternalLink, Clock } from 'lucide-react';
import type { StaleIssueRow } from '../../services/metricService';

// ---------------------------------------------------------------------------
// Stale Issues Data Table
// ---------------------------------------------------------------------------
interface Props {
  data: StaleIssueRow[];
  isLoading: boolean;
  error: string | null;
}

type SortField = 'inactiveDays' | 'issueNumber' | 'title';
type SortDir = 'asc' | 'desc';

export const StaleIssuesTable: React.FC<Props> = ({ data, isLoading, error }) => {
  const [minDays, setMinDays] = useState(7);
  const [search, setSearch] = useState('');
  const [sortField, setSortField] = useState<SortField>('inactiveDays');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const [page, setPage] = useState(0);
  const perPage = 10;

  const filtered = useMemo(() => {
    const q = search.toLowerCase().trim();
    return data
      .filter((r) => r.inactiveDays >= minDays)
      .filter(
        (r) =>
          !q ||
          r.title.toLowerCase().includes(q) ||
          r.author.toLowerCase().includes(q) ||
          String(r.issueNumber).includes(q)
      )
      .sort((a, b) => {
        const m = sortDir === 'asc' ? 1 : -1;
        if (sortField === 'inactiveDays') return (a.inactiveDays - b.inactiveDays) * m;
        if (sortField === 'issueNumber') return (a.issueNumber - b.issueNumber) * m;
        return a.title.localeCompare(b.title) * m;
      });
  }, [data, minDays, search, sortField, sortDir]);

  const totalPages = Math.ceil(filtered.length / perPage);
  const pageItems = filtered.slice(page * perPage, (page + 1) * perPage);

  const toggleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortField(field);
      setSortDir('desc');
    }
    setPage(0);
  };

  const SortIcon = ({ field }: { field: SortField }) => {
    if (sortField !== field) return null;
    return sortDir === 'asc' ? (
      <ChevronUp className="h-3 w-3 inline ml-0.5" />
    ) : (
      <ChevronDown className="h-3 w-3 inline ml-0.5" />
    );
  };

  const daysBadgeColor = (days: number) => {
    if (days >= 30) return { bg: '#FEF2F2', text: '#991B1B' };
    if (days >= 14) return { bg: '#FFFBEB', text: '#92400E' };
    return { bg: '#F0FDF4', text: '#166534' };
  };

  if (isLoading) {
    return (
      <div className="rounded-xl border border-[#9ED4C8] bg-white p-6 shadow-sm animate-pulse">
        <div className="flex items-center gap-2 mb-4">
          <div className="h-5 w-5 rounded bg-slate-200" />
          <div className="h-5 w-36 rounded bg-slate-200" />
        </div>
        {[...Array(5)].map((_, i) => (
          <div key={i} className="mb-2 h-10 rounded bg-slate-100" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-6">
        <div className="flex items-center gap-2 text-red-700">
          <AlertCircle className="h-5 w-5" />
          <span className="text-sm font-medium">Failed to load stale issues</span>
        </div>
        <p className="mt-2 text-xs text-red-600">{error}</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-[#9ED4C8] bg-white p-6 shadow-sm">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-4">
        <div className="flex items-center gap-2">
          <Clock className="h-5 w-5 text-[#0B6B63]" />
          <h3 className="text-sm font-semibold text-slate-800">Stale Issues</h3>
          {filtered.length > 0 && (
            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-600">
              {filtered.length}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {/* Min-days filter */}
          <label className="flex items-center gap-1 text-xs text-slate-500">
            ≥
            <input
              type="number"
              min={0}
              value={minDays}
              onChange={(e) => {
                setMinDays(Number(e.target.value) || 0);
                setPage(0);
              }}
              className="w-14 rounded-md border border-slate-200 px-2 py-1 text-xs focus:border-[#0B6B63] focus:outline-none focus:ring-1 focus:ring-[#0B6B63]/30"
            />
            days inactive
          </label>

          {/* Search */}
          <div className="relative">
            <Search className="absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder="Search…"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(0);
              }}
              className="w-36 rounded-md border border-slate-200 py-1 pl-7 pr-2 text-xs focus:border-[#0B6B63] focus:outline-none focus:ring-1 focus:ring-[#0B6B63]/30"
            />
          </div>
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="flex flex-col items-center gap-2 py-8 text-slate-400">
          <Clock className="h-8 w-8" />
          <p className="text-sm font-medium">No stale issues found</p>
          <p className="text-xs">Try lowering the inactivity threshold</p>
        </div>
      ) : (
        <>
          <div className="w-full overflow-x-auto rounded-lg border border-slate-200 shadow-sm">
            <table className="w-full min-w-[500px] text-left text-xs">
              <thead>
                <tr className="border-b border-slate-100">
                  <th
                    className="cursor-pointer select-none pb-2 pr-4 font-semibold text-slate-500 hover:text-slate-800"
                    onClick={() => toggleSort('issueNumber')}
                  >
                    # <SortIcon field="issueNumber" />
                  </th>
                  <th
                    className="cursor-pointer select-none pb-2 pr-4 font-semibold text-slate-500 hover:text-slate-800"
                    onClick={() => toggleSort('title')}
                  >
                    Title <SortIcon field="title" />
                  </th>
                  <th className="pb-2 pr-4 font-semibold text-slate-500">Author</th>
                  <th className="pb-2 pr-4 font-semibold text-slate-500">Labels</th>
                  <th
                    className="cursor-pointer select-none pb-2 pr-4 font-semibold text-slate-500 hover:text-slate-800 text-right"
                    onClick={() => toggleSort('inactiveDays')}
                  >
                    Inactive <SortIcon field="inactiveDays" />
                  </th>
                </tr>
              </thead>
              <tbody>
                {pageItems.map((row) => {
                  const badge = daysBadgeColor(row.inactiveDays);
                  return (
                    <tr key={row.id} className="border-b border-slate-50 last:border-0 hover:bg-slate-50/50">
                      <td className="py-2.5 pr-4 font-mono text-slate-500">
                        {row.url ? (
                          <a
                            href={row.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 hover:text-[#0B6B63]"
                          >
                            #{row.issueNumber} <ExternalLink className="h-3 w-3" />
                          </a>
                        ) : (
                          `#${row.issueNumber}`
                        )}
                      </td>
                      <td className="py-2.5 pr-4 max-w-[220px] truncate text-slate-700">{row.title}</td>
                      <td className="py-2.5 pr-4 text-slate-500">{row.author}</td>
                      <td className="py-2.5 pr-4">
                        <div className="flex flex-wrap gap-1">
                          {row.labels.slice(0, 3).map((l) => (
                            <span
                              key={l}
                              className="inline-block rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-600"
                            >
                              {l}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="py-2.5 pr-0 text-right">
                        <span
                          className="inline-block rounded-full px-2 py-0.5 text-[11px] font-semibold"
                          style={{ backgroundColor: badge.bg, color: badge.text }}
                        >
                          {row.inactiveDays}d
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="mt-3 flex items-center justify-between">
              <span className="text-[11px] text-slate-400">
                Page {page + 1} of {totalPages}
              </span>
              <div className="flex gap-1">
                <button
                  type="button"
                  disabled={page === 0}
                  onClick={() => setPage((p) => p - 1)}
                  className="rounded-md border border-slate-200 px-2.5 py-1 text-xs text-slate-600 hover:bg-slate-50 disabled:opacity-40"
                >
                  Prev
                </button>
                <button
                  type="button"
                  disabled={page >= totalPages - 1}
                  onClick={() => setPage((p) => p + 1)}
                  className="rounded-md border border-slate-200 px-2.5 py-1 text-xs text-slate-600 hover:bg-slate-50 disabled:opacity-40"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
};
