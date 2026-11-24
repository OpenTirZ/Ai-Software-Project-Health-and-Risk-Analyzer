import React, { useState } from 'react';
import type { AdminUser } from '../../services/api';
import {
  Search,
  UserCheck,
  UserX,
  ChevronDown,
  Loader2,
  AlertTriangle,
  Users,
} from 'lucide-react';

interface UserManagementTableProps {
  users: AdminUser[];
  loading: boolean;
  error: string | null;
  onRoleChange: (userId: string, role: AdminUser['role']) => Promise<void>;
  onToggleStatus: (userId: string, activate: boolean) => Promise<void>;
  onSearch?: (term: string) => void;
}

const ROLES: { value: AdminUser['role']; label: string }[] = [
  { value: 'developer', label: 'Developer' },
  { value: 'project_manager', label: 'Project Manager' },
  { value: 'admin', label: 'Admin' },
];

const roleBadge: Record<AdminUser['role'], string> = {
  admin: 'bg-purple-100 text-purple-700',
  project_manager: 'bg-blue-100 text-blue-700',
  developer: 'bg-slate-100 text-slate-600',
};

export const UserManagementTable: React.FC<UserManagementTableProps> = ({
  users,
  loading,
  error,
  onRoleChange,
  onToggleStatus,
  onSearch,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [changingRole, setChangingRole] = useState<string | null>(null);
  const [togglingStatus, setTogglingStatus] = useState<string | null>(null);

  const handleSearchChange = (value: string) => {
    setSearchTerm(value);
    onSearch?.(value);
  };

  const handleRoleChange = async (userId: string, role: AdminUser['role']) => {
    setChangingRole(userId);
    try {
      await onRoleChange(userId, role);
    } finally {
      setChangingRole(null);
    }
  };

  const handleToggleStatus = async (userId: string, activate: boolean) => {
    setTogglingStatus(userId);
    try {
      await onToggleStatus(userId, activate);
    } finally {
      setTogglingStatus(null);
    }
  };

  // Client-side filter (supplement to server-side search)
  const filtered = searchTerm.trim()
    ? users.filter(
        (u) =>
          u.name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
          u.email?.toLowerCase().includes(searchTerm.toLowerCase())
      )
    : users;

  if (error) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-center">
        <AlertTriangle className="mx-auto mb-2 h-6 w-6 text-red-500" />
        <p className="text-sm text-red-700">{error}</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
        <input
          type="text"
          value={searchTerm}
          onChange={(e) => handleSearchChange(e.target.value)}
          placeholder="Search users by name or email..."
          className="w-full rounded-lg border border-slate-200 bg-white py-2 pl-10 pr-4 text-sm text-slate-700 placeholder:text-slate-400 focus:border-[#0B6B63] focus:outline-none focus:ring-1 focus:ring-[#0B6B63]"
        />
      </div>

      {/* Table */}
      {loading && users.length === 0 ? (
        <div className="flex h-40 items-center justify-center">
          <Loader2 className="h-6 w-6 animate-spin text-[#0B6B63]" />
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-slate-100 bg-slate-50">
                  <th className="px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                    User
                  </th>
                  <th className="px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                    Email
                  </th>
                  <th className="px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                    Role
                  </th>
                  <th className="px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider text-right">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {filtered.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="p-8 text-center">
                      <Users className="mx-auto mb-2 h-6 w-6 text-slate-300" />
                      <p className="text-sm text-slate-400">No users found</p>
                    </td>
                  </tr>
                ) : (
                  filtered.map((user) => (
                    <tr key={user.id} className="hover:bg-slate-50/60 transition-colors">
                      {/* Name */}
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-[#0B6B63] to-[#095c55] text-xs font-bold text-white">
                            {user.name
                              ? user.name
                                  .split(' ')
                                  .map((w) => w[0])
                                  .slice(0, 2)
                                  .join('')
                                  .toUpperCase()
                              : 'U'}
                          </div>
                          <span className="text-sm font-medium text-slate-700">{user.name}</span>
                        </div>
                      </td>

                      {/* Email */}
                      <td className="px-4 py-3 text-sm text-slate-500">{user.email}</td>

                      {/* Role Dropdown */}
                      <td className="px-4 py-3">
                        <div className="relative inline-block">
                          {changingRole === user.id ? (
                            <Loader2 className="h-4 w-4 animate-spin text-[#0B6B63]" />
                          ) : (
                            <div className="relative">
                              <select
                                value={user.role}
                                onChange={(e) =>
                                  handleRoleChange(user.id, e.target.value as AdminUser['role'])
                                }
                                className={`appearance-none rounded-full px-3 py-1 pr-7 text-xs font-medium ${roleBadge[user.role]} border-0 cursor-pointer focus:outline-none focus:ring-2 focus:ring-[#0B6B63]`}
                              >
                                {ROLES.map((r) => (
                                  <option key={r.value} value={r.value}>
                                    {r.label}
                                  </option>
                                ))}
                              </select>
                              <ChevronDown className="pointer-events-none absolute right-2 top-1/2 h-3 w-3 -translate-y-1/2 text-current opacity-50" />
                            </div>
                          )}
                        </div>
                      </td>

                      {/* Status */}
                      <td className="px-4 py-3">
                        <span
                          className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${
                            user.is_active
                              ? 'bg-emerald-100 text-emerald-700'
                              : 'bg-slate-100 text-slate-500'
                          }`}
                        >
                          <span
                            className={`h-1.5 w-1.5 rounded-full ${
                              user.is_active ? 'bg-emerald-500' : 'bg-slate-400'
                            }`}
                          />
                          {user.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </td>

                      {/* Toggle action */}
                      <td className="px-4 py-3 text-right">
                        <button
                          disabled={togglingStatus === user.id}
                          onClick={() => handleToggleStatus(user.id, !user.is_active)}
                          className={`inline-flex items-center gap-1 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                            user.is_active
                              ? 'border border-red-200 text-red-600 hover:bg-red-50'
                              : 'border border-emerald-200 text-emerald-600 hover:bg-emerald-50'
                          } disabled:opacity-50`}
                        >
                          {togglingStatus === user.id ? (
                            <Loader2 className="h-3 w-3 animate-spin" />
                          ) : user.is_active ? (
                            <UserX className="h-3 w-3" />
                          ) : (
                            <UserCheck className="h-3 w-3" />
                          )}
                          {user.is_active ? 'Deactivate' : 'Activate'}
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};

export default UserManagementTable;
