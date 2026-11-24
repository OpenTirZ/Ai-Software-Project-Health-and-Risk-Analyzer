import React, { useState } from 'react';
import { 
  Users, 
  Search, 
  UserPlus, 
  ShieldCheck, 
  MoreVertical, 
  CheckCircle2, 
  AlertCircle, 
  X, 
  Key, 
  UserCheck, 
  UserX,
  Mail,
  Shield
} from 'lucide-react';

const INITIAL_USERS = [
  {
    id: 'usr_vandit_01',
    fullName: 'Vandit Bhalani',
    username: '@vanditbhalani07',
    email: 'vanditbhalani07@gmail.com',
    role: 'System Administrator',
    status: 'Active',
    assignedRepos: ['DevOps-Projects', 'Ai-Software-Project-Health-and-Risk-Analyzer'],
    lastActive: 'Just now',
  },
  {
    id: 'usr_john_dev',
    fullName: 'John Developer',
    username: '@johndev',
    email: 'john.dev@aegis-health.io',
    role: 'Team Lead',
    status: 'Active',
    assignedRepos: ['core-api-service', 'payment-gateway', 'auth-microservice'],
    lastActive: '12m ago',
  },
  {
    id: 'usr_sarah_c',
    fullName: 'Sarah Connor',
    username: '@sarahc',
    email: 'sarah.connor@aegis-health.io',
    role: 'Senior Developer',
    status: 'Active',
    assignedRepos: ['core-api-service', 'infra-terraform'],
    lastActive: '2h ago',
  },
  {
    id: 'usr_alex_c',
    fullName: 'Alex Chen',
    username: '@alexchen',
    email: 'alex.chen@aegis-health.io',
    role: 'Developer',
    status: 'Active',
    assignedRepos: ['payment-gateway', 'notification-service'],
    lastActive: '5h ago',
  },
  {
    id: 'usr_elena_r',
    fullName: 'Elena Rostova',
    username: '@elenar',
    email: 'elena.rostova@aegis-health.io',
    role: 'Developer',
    status: 'Active',
    assignedRepos: ['data-pipeline', 'analytics-worker'],
    lastActive: '1d ago',
  },
  {
    id: 'usr_jinal_02',
    fullName: 'Jinal Bhalani',
    username: '@jinalbhalani1414',
    email: 'jinalbhalani1414@gmail.com',
    role: 'Developer',
    status: 'Active',
    assignedRepos: ['DevOps-Projects'],
    lastActive: '2d ago',
  },
];

export const UserManagementTable = ({ onUserUpdated }) => {
  const [users, setUsers] = useState(INITIAL_USERS);
  const [searchQuery, setSearchQuery] = useState('');
  const [roleFilter, setRoleFilter] = useState('ALL');
  const [statusFilter, setStatusFilter] = useState('ALL');

  // Modal States
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [newUserName, setNewUserName] = useState('');
  const [newUserEmail, setNewUserEmail] = useState('');
  const [newUserRole, setNewUserRole] = useState('Developer');

  const [activeMenuUserId, setActiveMenuUserId] = useState(null);
  const [toastMessage, setToastMessage] = useState(null);

  const showToast = (msg) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  };

  const filteredUsers = users.filter((u) => {
    const matchesSearch =
      u.fullName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      u.email.toLowerCase().includes(searchQuery.toLowerCase()) ||
      u.username.toLowerCase().includes(searchQuery.toLowerCase());

    const matchesRole = roleFilter === 'ALL' || u.role === roleFilter;
    const matchesStatus = statusFilter === 'ALL' || u.status === statusFilter;

    return matchesSearch && matchesRole && matchesStatus;
  });

  const handleRoleChange = (userId, newRole) => {
    setUsers((prev) =>
      prev.map((u) => (u.id === userId ? { ...u, role: newRole } : u))
    );
    setActiveMenuUserId(null);
    showToast(`User role updated to ${newRole}`);
  };

  const handleToggleStatus = (userId) => {
    setUsers((prev) =>
      prev.map((u) => {
        if (u.id === userId) {
          const nextStatus = u.status === 'Active' ? 'Suspended' : 'Active';
          showToast(`User marked as ${nextStatus}`);
          return { ...u, status: nextStatus };
        }
        return u;
      })
    );
    setActiveMenuUserId(null);
  };

  const handleResetSession = (userName) => {
    setActiveMenuUserId(null);
    showToast(`Active sessions invalidated for ${userName}`);
  };

  const handleInviteSubmit = (e) => {
    e.preventDefault();
    if (!newUserEmail.trim()) return;

    const cleanUsername = `@${newUserEmail.split('@')[0]}`;
    const newUser = {
      id: `usr_${Date.now()}`,
      fullName: newUserName.trim() || 'New Team Member',
      username: cleanUsername,
      email: newUserEmail.trim(),
      role: newUserRole,
      status: 'Active',
      assignedRepos: ['Main Platform'],
      lastActive: 'Pending first login',
    };

    setUsers([newUser, ...users]);
    setNewUserName('');
    setNewUserEmail('');
    setNewUserRole('Developer');
    setShowInviteModal(false);
    showToast(`Invitation dispatched to ${newUser.email}`);
  };

  const getRoleBadge = (role) => {
    switch (role) {
      case 'System Administrator':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-purple-50 text-purple-700 border border-purple-200">
            <Shield className="w-3 h-3 text-purple-600" />
            Admin
          </span>
        );
      case 'Team Lead':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-indigo-50 text-indigo-700 border border-indigo-200">
            <ShieldCheck className="w-3 h-3 text-indigo-600" />
            Lead
          </span>
        );
      case 'Senior Developer':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-blue-50 text-blue-700 border border-blue-200">
            Senior Dev
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-slate-100 text-slate-700 border border-slate-200">
            Developer
          </span>
        );
    }
  };

  return (
    <div className="space-y-4">
      {/* Toast */}
      {toastMessage && (
        <div className="p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-xl text-xs font-semibold flex items-center justify-between animate-in fade-in">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
            <span>{toastMessage}</span>
          </div>
          <button onClick={() => setToastMessage(null)} className="text-emerald-600">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Control Bar: Search, Filters, Invite */}
      <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3 bg-white p-4 rounded-2xl border border-slate-200/90 shadow-xs">
        <div className="flex items-center gap-2 flex-1">
          <Search className="w-4 h-4 text-slate-400 ml-1" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search users by name, email, or @handle..."
            className="w-full text-xs text-slate-800 placeholder:text-slate-400 focus:outline-none bg-transparent"
          />
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {/* Role Filter */}
          <select
            value={roleFilter}
            onChange={(e) => setRoleFilter(e.target.value)}
            className="text-xs text-slate-700 bg-slate-50 border border-slate-200 rounded-xl px-3 py-1.5 focus:outline-none cursor-pointer"
          >
            <option value="ALL">All Roles</option>
            <option value="System Administrator">System Administrator</option>
            <option value="Team Lead">Team Lead</option>
            <option value="Senior Developer">Senior Developer</option>
            <option value="Developer">Developer</option>
          </select>

          {/* Status Filter */}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="text-xs text-slate-700 bg-slate-50 border border-slate-200 rounded-xl px-3 py-1.5 focus:outline-none cursor-pointer"
          >
            <option value="ALL">All Statuses</option>
            <option value="Active">Active</option>
            <option value="Suspended">Suspended</option>
          </select>

          {/* Invite User Button */}
          <button
            onClick={() => setShowInviteModal(true)}
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold transition-all shadow-sm shadow-indigo-600/20 cursor-pointer"
          >
            <UserPlus className="w-3.5 h-3.5" />
            <span>Invite User</span>
          </button>
        </div>
      </div>

      {/* Users Table */}
      <div className="bg-white rounded-2xl border border-slate-200/90 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50/70 text-slate-600 text-xs font-bold uppercase tracking-wider">
                <th className="py-4 px-6">User</th>
                <th className="py-4 px-6">System Role</th>
                <th className="py-4 px-6">Assigned Repositories</th>
                <th className="py-4 px-6">Status</th>
                <th className="py-4 px-6">Last Active</th>
                <th className="py-4 px-6 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-sm">
              {filteredUsers.map((u) => {
                const initials = u.fullName
                  .split(' ')
                  .map((n) => n[0])
                  .slice(0, 2)
                  .join('')
                  .toUpperCase();

                const isMenuOpen = activeMenuUserId === u.id;

                return (
                  <tr key={u.id} className="hover:bg-slate-50/80 transition-colors">
                    {/* User Identity */}
                    <td className="py-4 px-6">
                      <div className="flex items-center gap-3">
                        <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white text-xs font-bold shadow-xs">
                          {initials}
                        </div>
                        <div>
                          <p className="font-bold text-slate-900 text-sm leading-tight">
                            {u.fullName}
                          </p>
                          <p className="text-xs text-slate-400 font-mono mt-0.5">
                            {u.username} • {u.email}
                          </p>
                        </div>
                      </div>
                    </td>

                    {/* Role */}
                    <td className="py-4 px-6">
                      {getRoleBadge(u.role)}
                    </td>

                    {/* Assigned Repositories */}
                    <td className="py-4 px-6">
                      <div className="flex flex-wrap gap-1 max-w-xs">
                        {u.assignedRepos.map((repo, idx) => (
                          <span
                            key={idx}
                            className="px-2 py-0.5 rounded-md bg-slate-100 text-slate-700 text-[11px] font-mono border border-slate-200"
                          >
                            {repo}
                          </span>
                        ))}
                      </div>
                    </td>

                    {/* Status */}
                    <td className="py-4 px-6">
                      <span
                        className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold ${
                          u.status === 'Active'
                            ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                            : 'bg-rose-50 text-rose-700 border border-rose-200'
                        }`}
                      >
                        <span
                          className={`w-1.5 h-1.5 rounded-full ${
                            u.status === 'Active' ? 'bg-emerald-500' : 'bg-rose-500'
                          }`}
                        />
                        {u.status}
                      </span>
                    </td>

                    {/* Last Active */}
                    <td className="py-4 px-6 text-xs text-slate-500 font-mono">
                      {u.lastActive}
                    </td>

                    {/* Quick Action Popover */}
                    <td className="py-4 px-6 text-right relative">
                      <button
                        onClick={() => setActiveMenuUserId(isMenuOpen ? null : u.id)}
                        className="p-1.5 text-slate-400 hover:text-slate-700 rounded-lg hover:bg-slate-100 transition-colors cursor-pointer"
                        title="Manage user"
                      >
                        <MoreVertical className="w-4 h-4" />
                      </button>

                      {isMenuOpen && (
                        <div className="absolute right-6 mt-1 w-48 bg-white rounded-xl shadow-xl border border-slate-200 py-1.5 z-30 text-left animate-in fade-in text-xs">
                          <p className="px-3 py-1 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                            Assign Role
                          </p>
                          <button
                            onClick={() => handleRoleChange(u.id, 'Team Lead')}
                            className="w-full text-left px-3 py-1.5 hover:bg-slate-50 text-slate-700 cursor-pointer"
                          >
                            Set as Team Lead
                          </button>
                          <button
                            onClick={() => handleRoleChange(u.id, 'Senior Developer')}
                            className="w-full text-left px-3 py-1.5 hover:bg-slate-50 text-slate-700 cursor-pointer"
                          >
                            Set as Senior Dev
                          </button>
                          <button
                            onClick={() => handleRoleChange(u.id, 'Developer')}
                            className="w-full text-left px-3 py-1.5 hover:bg-slate-50 text-slate-700 cursor-pointer"
                          >
                            Set as Developer
                          </button>

                          <div className="my-1 border-t border-slate-100" />

                          <button
                            onClick={() => handleResetSession(u.fullName)}
                            className="w-full text-left px-3 py-1.5 hover:bg-slate-50 text-slate-700 flex items-center gap-1.5 cursor-pointer"
                          >
                            <Key className="w-3.5 h-3.5 text-slate-400" />
                            <span>Invalidate Session</span>
                          </button>

                          <button
                            onClick={() => handleToggleStatus(u.id)}
                            className={`w-full text-left px-3 py-1.5 hover:bg-slate-50 flex items-center gap-1.5 cursor-pointer font-bold ${
                              u.status === 'Active' ? 'text-rose-600' : 'text-emerald-600'
                            }`}
                          >
                            {u.status === 'Active' ? (
                              <>
                                <UserX className="w-3.5 h-3.5" />
                                <span>Suspend Access</span>
                              </>
                            ) : (
                              <>
                                <UserCheck className="w-3.5 h-3.5" />
                                <span>Reactivate Access</span>
                              </>
                            )}
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Invite User Modal */}
      {showInviteModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div className="flex items-center gap-2">
                <UserPlus className="w-5 h-5 text-indigo-600" />
                <h3 className="text-base font-bold text-slate-900">
                  Invite New Team Member
                </h3>
              </div>
              <button
                onClick={() => setShowInviteModal(false)}
                className="text-slate-400 hover:text-slate-600 cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleInviteSubmit} className="space-y-3.5">
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">
                  Full Name
                </label>
                <input
                  type="text"
                  required
                  value={newUserName}
                  onChange={(e) => setNewUserName(e.target.value)}
                  placeholder="e.g. Maya Patel"
                  className="w-full text-xs px-3.5 py-2.5 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">
                  Corporate Email
                </label>
                <input
                  type="email"
                  required
                  value={newUserEmail}
                  onChange={(e) => setNewUserEmail(e.target.value)}
                  placeholder="name@company.io"
                  className="w-full text-xs px-3.5 py-2.5 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">
                  System Role
                </label>
                <select
                  value={newUserRole}
                  onChange={(e) => setNewUserRole(e.target.value)}
                  className="w-full text-xs px-3.5 py-2.5 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 bg-white"
                >
                  <option value="Developer">Developer</option>
                  <option value="Senior Developer">Senior Developer</option>
                  <option value="Team Lead">Team Lead</option>
                  <option value="System Administrator">System Administrator</option>
                </select>
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowInviteModal(false)}
                  className="px-4 py-2 rounded-xl border border-slate-200 text-xs font-semibold text-slate-600 hover:bg-slate-50 cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold shadow-md shadow-indigo-600/20 cursor-pointer"
                >
                  Send Invitation
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default UserManagementTable;
