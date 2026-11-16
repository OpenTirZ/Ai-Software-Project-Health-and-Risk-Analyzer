import React, { useState, useEffect } from 'react';
import type { PageView, UserProfileData } from '../types';
import { 
  CheckCircle2, 
  LogOut, 
  Edit3, 
  Save 
} from 'lucide-react';

interface UserProfileProps {
  currentUser?: UserProfileData;
  onUpdateProfile?: (updated: UserProfileData) => void;
  onLogout: () => void;
  onNavigate: (view: PageView) => void;
}

export const UserProfile: React.FC<UserProfileProps> = ({ 
  currentUser, 
  onUpdateProfile, 
  onLogout 
}) => {
  const [isEditing, setIsEditing] = useState(false);
  const [activeTab, setActiveTab] = useState<'profile' | 'security' | 'notifications'>('profile');
  
  const [profile, setProfile] = useState<UserProfileData>(() => ({
    fullName: currentUser?.fullName || 'John Developer',
    username: currentUser?.username || '@johndev',
    email: currentUser?.email || 'john.dev@aegis-health.io',
    role: currentUser?.role || 'Lead Staff Architect',
    team: currentUser?.team || 'Enterprise Core Platform',
    bio: currentUser?.bio || 'Leading backend architecture, microservices refactoring, and AI CI/CD guardrail adoption across all cloud clusters.',
  }));

  // Keep state in sync if currentUser prop updates
  useEffect(() => {
    if (currentUser) {
      setProfile((prev) => ({
        ...prev,
        fullName: currentUser.fullName || prev.fullName,
        username: currentUser.username || prev.username,
        email: currentUser.email || prev.email,
        role: currentUser.role || prev.role,
        team: currentUser.team || prev.team,
        bio: currentUser.bio !== undefined ? currentUser.bio : prev.bio,
      }));
    }
  }, [currentUser]);

  const initials = profile.fullName
    ? profile.fullName
        .trim()
        .split(/\s+/)
        .map((part) => part[0])
        .slice(0, 2)
        .join('')
        .toUpperCase()
    : 'U';

  const handleSave = () => {
    setIsEditing(false);
    const cleanUsername = profile.username.trim()
      ? (profile.username.trim().startsWith('@') ? profile.username.trim() : `@${profile.username.trim()}`)
      : '@developer';
    const updated = {
      ...profile,
      username: cleanUsername,
    };
    setProfile(updated);
    if (onUpdateProfile) {
      onUpdateProfile(updated);
    }
  };

  return (
    <div className="p-6 md:p-8 max-w-5xl mx-auto space-y-6">
      {/* Top Banner Card */}
      <div className="bg-[#0f172a] rounded-2xl p-6 md:p-8 border border-slate-800 text-white shadow-xl relative overflow-hidden">
        {/* Ambient subtle glow */}
        <div className="absolute top-0 right-0 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />

        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 relative z-10">
          <div className="flex items-center gap-5">
            {/* Avatar */}
            <div className="relative">
              <div className="w-20 h-20 rounded-2xl bg-gradient-to-tr from-indigo-500 via-indigo-600 to-purple-600 flex items-center justify-center text-white text-2xl font-bold shadow-lg shadow-indigo-500/30">
                {initials}
              </div>
              <span className="absolute -bottom-1 -right-1 p-1 bg-emerald-500 rounded-full ring-4 ring-[#0f172a] text-white">
                <CheckCircle2 className="w-3.5 h-3.5" />
              </span>
            </div>

            {/* User Meta */}
            <div>
              <div className="flex items-center gap-3">
                <h1 className="text-2xl font-bold tracking-tight">
                  {profile.fullName}
                </h1>
                <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold tracking-wider uppercase bg-indigo-950 text-indigo-300 border border-indigo-700/60">
                  TEAM ADMIN
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-1">
                {profile.username} • {profile.role} • {profile.team}
              </p>
            </div>
          </div>

          {/* Right Repositories Monitored KPI + Edit Button */}
          <div className="flex items-center gap-6">
            <div className="text-right border-l border-slate-800 pl-6 hidden sm:block">
              <p className="text-[10px] font-bold uppercase text-slate-400 tracking-wider">
                REPOSITORIES MONITORED
              </p>
              <p className="text-3xl font-extrabold text-white mt-0.5">
                42
              </p>
            </div>

            <button
              onClick={() => {
                if (isEditing) handleSave();
                else setIsEditing(true);
              }}
              className="px-5 py-2.5 rounded-xl text-white text-xs font-bold shadow-md shadow-indigo-600/30 transition-all hover:opacity-95 active:scale-95 flex items-center gap-2 cursor-pointer shrink-0"
              style={{
                background: 'linear-gradient(90deg, rgba(0, 0, 0, 0.2) 0%, rgba(0, 0, 0, 0.2) 100%), linear-gradient(90deg, rgb(99, 102, 241) 0%, rgb(168, 85, 247) 100%)',
              }}
            >
              {isEditing ? (
                <>
                  <Save className="w-4 h-4" />
                  <span>Save Changes</span>
                </>
              ) : (
                <>
                  <Edit3 className="w-4 h-4" />
                  <span>Edit Profile</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-2 border-b border-slate-200 pb-2">
        <button
          onClick={() => setActiveTab('profile')}
          className={`px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer ${
            activeTab === 'profile'
              ? 'bg-indigo-600 text-white shadow-sm'
              : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
          }`}
        >
          Profile & General
        </button>
        <button
          onClick={() => setActiveTab('security')}
          className={`px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer ${
            activeTab === 'security'
              ? 'bg-indigo-600 text-white shadow-sm'
              : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
          }`}
        >
          Security & API Keys
        </button>
        <button
          onClick={() => setActiveTab('notifications')}
          className={`px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer ${
            activeTab === 'notifications'
              ? 'bg-indigo-600 text-white shadow-sm'
              : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
          }`}
        >
          Notifications
        </button>
      </div>

      {/* Profile & General Card */}
      {activeTab === 'profile' && (
        <div className="bg-white rounded-2xl p-6 md:p-8 border border-slate-200/90 shadow-sm space-y-6">
          <div className="border-b border-slate-100 pb-4">
            <h2 className="text-lg font-bold text-slate-900">
              Personal Information
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Manage your public persona, team assignments, and contact email.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Full Name */}
            <div>
              <label className="block text-xs font-bold uppercase text-slate-500 mb-2">
                Full Name
              </label>
              {isEditing ? (
                <input
                  type="text"
                  value={profile.fullName}
                  onChange={(e) => setProfile({ ...profile, fullName: e.target.value })}
                  className="w-full px-4 py-2.5 rounded-xl border border-slate-300 text-sm text-slate-900 focus:outline-none focus:border-indigo-600"
                />
              ) : (
                <div className="px-4 py-3 rounded-xl bg-slate-50 border border-slate-200/80 text-sm font-medium text-slate-800">
                  {profile.fullName}
                </div>
              )}
            </div>

            {/* Username */}
            <div>
              <label className="block text-xs font-bold uppercase text-slate-500 mb-2">
                Username
              </label>
              {isEditing ? (
                <input
                  type="text"
                  value={profile.username}
                  onChange={(e) => setProfile({ ...profile, username: e.target.value })}
                  className="w-full px-4 py-2.5 rounded-xl border border-slate-300 text-sm text-slate-900 focus:outline-none focus:border-indigo-600"
                />
              ) : (
                <div className="px-4 py-3 rounded-xl bg-slate-50 border border-slate-200/80 text-sm font-mono text-slate-800">
                  {profile.username}
                </div>
              )}
            </div>

            {/* Email Address */}
            <div className="md:col-span-2">
              <label className="block text-xs font-bold uppercase text-slate-500 mb-2 flex items-center gap-1.5">
                <span>Email Address</span>
                <span className="text-[10px] text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded font-semibold border border-emerald-200">
                  Verified
                </span>
              </label>
              <div className="flex items-center justify-between px-4 py-3 rounded-xl bg-slate-50 border border-slate-200/80 text-sm text-slate-800 font-mono">
                <span>{profile.email}</span>
                <CheckCircle2 className="w-4 h-4 text-emerald-500" />
              </div>
            </div>

            {/* Bio & Responsibilities */}
            <div className="md:col-span-2">
              <label className="block text-xs font-bold uppercase text-slate-500 mb-2">
                Bio & Responsibilities
              </label>
              {isEditing ? (
                <textarea
                  rows={3}
                  value={profile.bio}
                  onChange={(e) => setProfile({ ...profile, bio: e.target.value })}
                  className="w-full px-4 py-2.5 rounded-xl border border-slate-300 text-sm text-slate-900 focus:outline-none focus:border-indigo-600 resize-none"
                />
              ) : (
                <div className="px-4 py-3.5 rounded-xl bg-slate-50 border border-slate-200/80 text-sm text-slate-700 leading-relaxed">
                  {profile.bio}
                </div>
              )}
            </div>
          </div>

          {/* Logout Section */}
          <div className="pt-6 border-t border-slate-100 flex items-center justify-between">
            <span className="text-xs text-slate-400">
              Session authenticated via Aegis AI Security Layer
            </span>
            <button
              onClick={onLogout}
              className="px-5 py-2 rounded-xl border border-rose-200 text-rose-600 hover:bg-rose-50 text-xs font-bold transition-colors flex items-center gap-1.5 cursor-pointer"
            >
              <LogOut className="w-4 h-4" />
              <span>Log out</span>
            </button>
          </div>
        </div>
      )}

      {/* Security Tab */}
      {activeTab === 'security' && (
        <div className="bg-white rounded-2xl p-6 md:p-8 border border-slate-200/90 shadow-sm space-y-6">
          <div className="border-b border-slate-100 pb-4">
            <h2 className="text-lg font-bold text-slate-900">
              API Keys & Permissions
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Manage webhook tokens and continuous integration analyzer credentials.
            </p>
          </div>

          <div className="space-y-4">
            <div className="p-4 rounded-xl border border-slate-200 bg-slate-50/60 flex items-center justify-between">
              <div>
                <p className="text-sm font-bold text-slate-800">Production Webhook Token</p>
                <p className="text-xs font-mono text-slate-500 mt-0.5">aegis_sec_******************391f</p>
              </div>
              <button className="px-3 py-1.5 rounded-lg border border-slate-300 text-xs font-semibold text-slate-700 hover:bg-white cursor-pointer">
                Regenerate
              </button>
            </div>

            <div className="p-4 rounded-xl border border-slate-200 bg-slate-50/60 flex items-center justify-between">
              <div>
                <p className="text-sm font-bold text-slate-800">GitHub Enterprise Integration</p>
                <p className="text-xs text-emerald-600 font-semibold mt-0.5">Connected (All 42 Repositories)</p>
              </div>
              <button className="px-3 py-1.5 rounded-lg border border-slate-300 text-xs font-semibold text-slate-700 hover:bg-white cursor-pointer">
                Configure
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Notifications Tab */}
      {activeTab === 'notifications' && (
        <div className="bg-white rounded-2xl p-6 md:p-8 border border-slate-200/90 shadow-sm space-y-6">
          <div className="border-b border-slate-100 pb-4">
            <h2 className="text-lg font-bold text-slate-900">
              Notification Preferences
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Choose when and how Aegis AI alerts you about potential risk bottlenecks.
            </p>
          </div>

          <div className="space-y-3">
            <label className="flex items-center justify-between p-3 rounded-xl border border-slate-200 hover:bg-slate-50 cursor-pointer">
              <div>
                <p className="text-sm font-semibold text-slate-800">High Risk Threshold Exceeded</p>
                <p className="text-xs text-slate-500">Alert immediately when pull requests exceed 48h</p>
              </div>
              <input type="checkbox" defaultChecked className="w-4 h-4 text-indigo-600 rounded" />
            </label>

            <label className="flex items-center justify-between p-3 rounded-xl border border-slate-200 hover:bg-slate-50 cursor-pointer">
              <div>
                <p className="text-sm font-semibold text-slate-800">Weekly Health Summary Digest</p>
                <p className="text-xs text-slate-500">Receive comprehensive PDF report every Monday at 9 AM</p>
              </div>
              <input type="checkbox" defaultChecked className="w-4 h-4 text-indigo-600 rounded" />
            </label>
          </div>
        </div>
      )}
    </div>
  );
};
