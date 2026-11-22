import React, { useState, useEffect, useCallback } from 'react';
import {
  Users,
  ClipboardList,
  Search,
  RefreshCw,
  ShieldCheck,
  ShieldOff,
  ChevronDown,
  AlertCircle,
  Loader2,
  CheckCircle2,
} from 'lucide-react';
import { adminApi, type AdminUser, type AuditLog } from '../services/api';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const ROLE_LABELS: Record<string, string> = {
  admin: 'Admin',
  project_manager: 'Project Manager',
  developer: 'Developer',
};

const ROLE_COLORS: Record<string, string> = {
  admin: 'bg-purple-100 text-purple-700 border-purple-200',
  project_manager: 'bg-blue-100 text-blue-700 border-blue-200',
  developer: 'bg-slate-100 text-slate-600 border-slate-200',
};

const ACTION_LABELS: Record<string, string> = {
  role_change: 'Role Changed',
  user_activated: 'User Activated',
  user_deactivated: 'User Deactivated',
};

function formatDate(raw: string): string {
  if (!raw) return '—';
  try {
    return new Date(raw).toLocaleString('en-US', {
      month: 'short',
      day: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return raw;
  }
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

interface StatusBadgeProps { active: boolean }
const StatusBadge: React.FC<StatusBadgeProps> = ({ active }) =>
  active ? (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-100 text-emerald-700 border border-emerald-200">
      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 inline-block" />
      Active
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-rose-100 text-rose-600 border border-rose-200">
      <span className="w-1.5 h-1.5 rounded-full bg-rose-400 inline-block" />
      Deactivated
    </span>
  );

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export const AdminPanel: React.FC = () => {
  const [tab, setTab] = useState<'users' | 'audit'>('users');

  // ── User Directory state ──────────────────────────────────────────────────
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [filterActive, setFilterActive] = useState<boolean | undefined>(undefined);
  const [loadingUsers, setLoadingUsers] = useState(false);
  const [userError, setUserError] = useState<string | null>(null);

  // Per-row action state: { [userId]: 'role' | 'status' | null }
  const [pendingAction, setPendingAction] = useState<Record<string, string | null>>({});
  const [actionFeedback, setActionFeedback] = useState<Record<string, string | null>>({});

  // ── Audit Log state ───────────────────────────────────────────────────────
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [loadingAudit, setLoadingAudit] = useState(false);
  const [auditError, setAuditError] = useState<string | null>(null);

  // ── Debounce search ───────────────────────────────────────────────────────
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 350);
    return () => clearTimeout(t);
  }, [search]);

  // ── Load users ────────────────────────────────────────────────────────────
  const loadUsers = useCallback(async () => {
    setLoadingUsers(true);
    setUserError(null);
    try {
      const res = await adminApi.getUsers({
        search: debouncedSearch || undefined,
        is_active: filterActive,
        limit: 50,
      });
      setUsers(res.items);
      setTotal(res.total);
    } catch (err: any) {
      setUserError(err.message || 'Failed to load users.');
    } finally {
      setLoadingUsers(false);
    }
  }, [debouncedSearch, filterActive]);

  useEffect(() => { loadUsers(); }, [loadUsers]);

  // ── Load audit logs ───────────────────────────────────────────────────────
  const loadAudit = useCallback(async () => {
    setLoadingAudit(true);
    setAuditError(null);
    try {
      const logs = await adminApi.getAuditLogs(200);
      setAuditLogs(logs);
    } catch (err: any) {
      setAuditError(err.message || 'Failed to load audit logs.');
    } finally {
      setLoadingAudit(false);
    }
  }, []);

  useEffect(() => { if (tab === 'audit') loadAudit(); }, [tab, loadAudit]);

  // ── Handlers ──────────────────────────────────────────────────────────────
  const handleRoleChange = async (user: AdminUser, newRole: AdminUser['role']) => {
    if (newRole === user.role) return;
    setPendingAction((p) => ({ ...p, [user.id]: 'role' }));
    setActionFeedback((f) => ({ ...f, [user.id]: null }));
    try {
      const updated = await adminApi.updateUserRole(user.id, newRole);
      setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));
      setActionFeedback((f) => ({ ...f, [user.id]: '✓ Role updated' }));
      setTimeout(() => setActionFeedback((f) => ({ ...f, [user.id]: null })), 2500);
    } catch (err: any) {
      setActionFeedback((f) => ({ ...f, [user.id]: err.message || 'Error updating role' }));
    } finally {
      setPendingAction((p) => ({ ...p, [user.id]: null }));
    }
  };

  const handleToggleStatus = async (user: AdminUser) => {
    setPendingAction((p) => ({ ...p, [user.id]: 'status' }));
    setActionFeedback((f) => ({ ...f, [user.id]: null }));
    try {
      const updated = await adminApi.toggleUserStatus(user.id, !user.is_active);
      setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));
      setActionFeedback((f) => ({
        ...f,
        [user.id]: updated.is_active ? '✓ Activated' : '✓ Deactivated',
      }));
      setTimeout(() => setActionFeedback((f) => ({ ...f, [user.id]: null })), 2500);
    } catch (err: any) {
      setActionFeedback((f) => ({ ...f, [user.id]: err.message || 'Error toggling status' }));
    } finally {
      setPendingAction((p) => ({ ...p, [user.id]: null }));
    }
  };

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="p-6 md:p-8 max-w-6xl mx-auto space-y-6">
      {/* ── Page Header ── */}
      <div className="bg-[#0f172a] rounded-2xl p-6 md:p-8 border border-slate-800 text-white shadow-xl relative overflow-hidden">
        <div className="absolute top-0 right-0 w-96 h-96 bg-purple-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="relative z-10 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-purple-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-purple-500/30">
              <ShieldCheck className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight">Admin Panel</h1>
              <p className="text-xs text-slate-400 mt-0.5">
                Manage platform users, roles, and audit history
              </p>
            </div>
          </div>
          <span className="px-3 py-1 rounded-full text-[11px] font-bold uppercase tracking-wider bg-purple-900/50 text-purple-300 border border-purple-700/60 self-start sm:self-auto">
            Admin Access Only
          </span>
        </div>
      </div>

      {/* ── Tabs ── */}
      <div className="flex items-center gap-2 border-b border-slate-200 pb-2">
        <button
          onClick={() => setTab('users')}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer ${
            tab === 'users' ? 'bg-indigo-600 text-white shadow-sm' : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
          }`}
        >
          <Users className="w-3.5 h-3.5" />
          User Directory
        </button>
        <button
          onClick={() => setTab('audit')}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer ${
            tab === 'audit' ? 'bg-indigo-600 text-white shadow-sm' : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
          }`}
        >
          <ClipboardList className="w-3.5 h-3.5" />
          Audit Logs
        </button>
      </div>

      {/* ══════════════════════ USER DIRECTORY ══════════════════════ */}
      {tab === 'users' && (
        <div className="bg-white rounded-2xl border border-slate-200/90 shadow-sm overflow-hidden">
          {/* Toolbar */}
          <div className="p-4 border-b border-slate-100 flex flex-col sm:flex-row gap-3 items-start sm:items-center justify-between">
            <div className="relative flex-1 max-w-sm">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
              <input
                type="text"
                placeholder="Search by name or email…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full pl-9 pr-3 py-2 rounded-xl border border-slate-200 text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none focus:border-indigo-400 focus:ring-1 focus:ring-indigo-100 transition"
              />
            </div>

            <div className="flex items-center gap-2 shrink-0">
              {/* Active filter */}
              <select
                value={filterActive === undefined ? '' : String(filterActive)}
                onChange={(e) =>
                  setFilterActive(e.target.value === '' ? undefined : e.target.value === 'true')
                }
                className="text-xs font-medium px-3 py-2 rounded-xl border border-slate-200 text-slate-700 bg-white focus:outline-none focus:border-indigo-400 cursor-pointer"
              >
                <option value="">All Status</option>
                <option value="true">Active</option>
                <option value="false">Deactivated</option>
              </select>

              {/* Refresh */}
              <button
                onClick={loadUsers}
                disabled={loadingUsers}
                className="p-2 rounded-xl border border-slate-200 text-slate-500 hover:bg-slate-50 hover:text-slate-700 transition cursor-pointer disabled:opacity-50"
                title="Refresh"
              >
                <RefreshCw className={`w-4 h-4 ${loadingUsers ? 'animate-spin' : ''}`} />
              </button>
            </div>
          </div>

          {/* Summary row */}
          <div className="px-4 py-2 bg-slate-50/60 border-b border-slate-100 text-xs text-slate-500">
            {loadingUsers ? 'Loading…' : `${total} user${total !== 1 ? 's' : ''} found`}
          </div>

          {/* Error */}
          {userError && (
            <div className="m-4 p-3 rounded-xl bg-rose-50 border border-rose-200 flex items-center gap-2 text-xs text-rose-700">
              <AlertCircle className="w-4 h-4 shrink-0" />
              {userError}
            </div>
          )}

          {/* Table */}
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs font-semibold text-slate-500 uppercase tracking-wider border-b border-slate-100">
                  <th className="px-4 py-3">User</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Role</th>
                  <th className="px-4 py-3">Joined</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {loadingUsers && users.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-4 py-10 text-center text-slate-400 text-xs">
                      <Loader2 className="w-5 h-5 animate-spin mx-auto mb-2" />
                      Loading users…
                    </td>
                  </tr>
                ) : users.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-4 py-10 text-center text-slate-400 text-xs">
                      No users match your filter.
                    </td>
                  </tr>
                ) : (
                  users.map((user) => {
                    const busy = Boolean(pendingAction[user.id]);
                    const feedback = actionFeedback[user.id];
                    const initials = user.name
                      .trim()
                      .split(/\s+/)
                      .map((p) => p[0])
                      .slice(0, 2)
                      .join('')
                      .toUpperCase() || '?';

                    return (
                      <tr
                        key={user.id}
                        className={`transition-colors ${!user.is_active ? 'bg-slate-50/60 opacity-80' : 'hover:bg-slate-50/40'}`}
                      >
                        {/* User */}
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-indigo-500 to-purple-600 text-white font-bold text-xs flex items-center justify-center shrink-0">
                              {initials}
                            </div>
                            <div className="min-w-0">
                              <p className="font-semibold text-slate-800 truncate">{user.name}</p>
                              <p className="text-xs text-slate-500 truncate">{user.email}</p>
                            </div>
                          </div>
                        </td>

                        {/* Status */}
                        <td className="px-4 py-3">
                          <StatusBadge active={user.is_active} />
                        </td>

                        {/* Role dropdown */}
                        <td className="px-4 py-3">
                          <div className="relative inline-block">
                            <select
                              value={user.role}
                              onChange={(e) =>
                                handleRoleChange(user, e.target.value as AdminUser['role'])
                              }
                              disabled={busy}
                              className={`appearance-none pr-7 pl-2 py-1.5 rounded-lg border text-xs font-semibold focus:outline-none focus:ring-1 focus:ring-indigo-300 cursor-pointer disabled:cursor-not-allowed transition ${ROLE_COLORS[user.role] || 'bg-slate-100 text-slate-600 border-slate-200'}`}
                            >
                              <option value="admin">Admin</option>
                              <option value="project_manager">Project Manager</option>
                              <option value="developer">Developer</option>
                            </select>
                            <ChevronDown className="pointer-events-none absolute right-1.5 top-1/2 -translate-y-1/2 w-3 h-3 text-current opacity-60" />
                          </div>
                        </td>

                        {/* Joined */}
                        <td className="px-4 py-3 text-xs text-slate-500 whitespace-nowrap">
                          {formatDate(user.created_at)}
                        </td>

                        {/* Actions */}
                        <td className="px-4 py-3 text-right">
                          <div className="flex items-center justify-end gap-2">
                            {feedback && (
                              <span
                                className={`text-[11px] font-semibold flex items-center gap-1 ${
                                  feedback.startsWith('✓') ? 'text-emerald-600' : 'text-rose-600'
                                }`}
                              >
                                {feedback.startsWith('✓') && (
                                  <CheckCircle2 className="w-3.5 h-3.5" />
                                )}
                                {feedback}
                              </span>
                            )}
                            {busy ? (
                              <Loader2 className="w-4 h-4 animate-spin text-indigo-500" />
                            ) : user.is_active ? (
                              <button
                                onClick={() => handleToggleStatus(user)}
                                className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-rose-200 text-rose-600 text-[11px] font-semibold hover:bg-rose-50 transition cursor-pointer"
                                title="Deactivate user"
                              >
                                <ShieldOff className="w-3.5 h-3.5" />
                                Deactivate
                              </button>
                            ) : (
                              <button
                                onClick={() => handleToggleStatus(user)}
                                className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-emerald-200 text-emerald-700 text-[11px] font-semibold hover:bg-emerald-50 transition cursor-pointer"
                                title="Reactivate user"
                              >
                                <ShieldCheck className="w-3.5 h-3.5" />
                                Reactivate
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ══════════════════════ AUDIT LOGS ══════════════════════ */}
      {tab === 'audit' && (
        <div className="bg-white rounded-2xl border border-slate-200/90 shadow-sm overflow-hidden">
          {/* Toolbar */}
          <div className="p-4 border-b border-slate-100 flex items-center justify-between">
            <div>
              <h2 className="text-sm font-bold text-slate-800">Platform Audit Log</h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Chronological record of all admin-initiated user lifecycle events
              </p>
            </div>
            <button
              onClick={loadAudit}
              disabled={loadingAudit}
              className="p-2 rounded-xl border border-slate-200 text-slate-500 hover:bg-slate-50 hover:text-slate-700 transition cursor-pointer disabled:opacity-50"
              title="Refresh"
            >
              <RefreshCw className={`w-4 h-4 ${loadingAudit ? 'animate-spin' : ''}`} />
            </button>
          </div>

          {/* Error */}
          {auditError && (
            <div className="m-4 p-3 rounded-xl bg-rose-50 border border-rose-200 flex items-center gap-2 text-xs text-rose-700">
              <AlertCircle className="w-4 h-4 shrink-0" />
              {auditError}
            </div>
          )}

          {/* Log entries */}
          {loadingAudit ? (
            <div className="py-12 flex flex-col items-center gap-2 text-slate-400 text-xs">
              <Loader2 className="w-5 h-5 animate-spin" />
              Loading audit logs…
            </div>
          ) : auditLogs.length === 0 ? (
            <div className="py-12 text-center text-slate-400 text-xs">
              No audit events recorded yet.
            </div>
          ) : (
            <ul className="divide-y divide-slate-100">
              {auditLogs.map((log) => {
                const actionLabel = ACTION_LABELS[log.action] || log.action.replace(/_/g, ' ');
                const isPositive = log.action === 'user_activated' || log.action === 'role_change';
                const isNegative = log.action === 'user_deactivated';

                return (
                  <li key={log.id} className="px-5 py-3.5 hover:bg-slate-50/50 transition flex flex-col sm:flex-row sm:items-start gap-1 sm:gap-4">
                    {/* Action badge */}
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider border shrink-0 self-start ${
                        isNegative
                          ? 'bg-rose-50 text-rose-600 border-rose-200'
                          : isPositive
                          ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                          : 'bg-slate-100 text-slate-500 border-slate-200'
                      }`}
                    >
                      {actionLabel}
                    </span>

                    {/* Detail */}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-slate-700">
                        {log.detail || 'No detail provided.'}
                      </p>
                      <p className="text-xs text-slate-400 mt-0.5">
                        Actor&nbsp;
                        <span className="font-mono text-slate-500">{log.actor_id}</span>
                        {log.target_id && (
                          <>
                            {' → '}
                            <span className="font-mono text-slate-500">{log.target_id}</span>
                          </>
                        )}
                      </p>
                    </div>

                    {/* Timestamp */}
                    <span className="text-xs text-slate-400 whitespace-nowrap shrink-0 self-start sm:pt-0.5">
                      {formatDate(log.created_at)}
                    </span>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}
    </div>
  );
};

export default AdminPanel;
