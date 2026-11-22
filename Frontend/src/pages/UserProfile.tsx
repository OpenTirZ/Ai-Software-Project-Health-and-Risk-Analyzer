
import React, { useState, useEffect, useRef } from 'react';
import type { PageView, UserProfileData } from '../types';
import {
  CheckCircle2,
  LogOut,
  Edit3,
  Save,
  AlertCircle,
  Loader2,
  Lock,
  ArrowRight,
} from 'lucide-react';
import {
  settingsApi,
  type NotificationPreferences,
  type ProjectResponse,
} from '../services/api';

interface UserProfileProps {
  currentUser?: UserProfileData;
  onUpdateProfile?: (updated: UserProfileData) => void;
  onLogout: () => void;
  onNavigate: (view: PageView) => void;
  projects?: ProjectResponse[];
  loadingProjects?: boolean;
}

const DEFAULT_PREFS: NotificationPreferences = {
  high_risk_threshold: true,
  weekly_digest: true,
};

const inputClass =
  'w-full rounded-lg border border-[#9ED4C8] bg-white px-4 py-2.5 text-sm text-[#0E2A2A] outline-none focus:border-[#0B6B63] focus:ring-2 focus:ring-[#1FB5A4]/15';

const cardClass =
  'space-y-6 rounded-xl border border-[#9ED4C8] bg-white p-5 sm:p-7';

export const UserProfile: React.FC<UserProfileProps> = ({
  currentUser,
  onUpdateProfile,
  onLogout,
  onNavigate,
  projects = [],
  loadingProjects = false,
}) => {
  const [isEditing, setIsEditing] = useState(false);
  const [activeTab, setActiveTab] = useState<
    'profile' | 'security' | 'notifications'
  >('profile');

  const [profile, setProfile] = useState<UserProfileData>(() => ({
    fullName: currentUser?.fullName || 'John Developer',
    username: currentUser?.username || '@johndev',
    email: currentUser?.email || 'john.dev@aegis-health.io',
    role: currentUser?.role || 'Lead Staff Architect',
    team: currentUser?.team || 'Enterprise Core Platform',
    bio:
      currentUser?.bio ||
      'Leading backend architecture, microservices refactoring, and AI CI/CD guardrail adoption across all cloud clusters.',
  }));

  const confirmedPrefsRef = useRef<NotificationPreferences>(DEFAULT_PREFS);
  const savingRef = useRef(false);

  const [notifPrefs, setNotifPrefs] =
    useState<NotificationPreferences>(DEFAULT_PREFS);
  const [notifLoading, setNotifLoading] = useState(false);
  const [notifSaving, setNotifSaving] = useState(false);
  const [notifError, setNotifError] = useState<string | null>(null);
  const [notifSaved, setNotifSaved] = useState(false);
  const [notifLoadWarning, setNotifLoadWarning] = useState(false);

  // Load notification preferences from the existing API.
  useEffect(() => {
    let isMounted = true;

    setNotifLoading(true);
    setNotifLoadWarning(false);

    settingsApi
      .getNotificationPreferences()
      .then((prefs) => {
        if (isMounted) {
          setNotifPrefs(prefs);
          confirmedPrefsRef.current = prefs;
        }
      })
      .catch(() => {
        if (isMounted) {
          setNotifLoadWarning(true);
        }
      })
      .finally(() => {
        if (isMounted) {
          setNotifLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, []);

  // Count only projects that have a connected repository URL.
  const connectedReposCount = projects.filter((project) =>
    Boolean(project.repo_url),
  ).length;

  // Keep profile information synchronized with updated props.
  useEffect(() => {
    if (currentUser) {
      setProfile((previous) => ({
        ...previous,
        fullName: currentUser.fullName || previous.fullName,
        username: currentUser.username || previous.username,
        email: currentUser.email || previous.email,
        role: currentUser.role || previous.role,
        team: currentUser.team || previous.team,
        bio:
          currentUser.bio !== undefined
            ? currentUser.bio
            : previous.bio,
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
    const cleanUsername = profile.username.trim()
      ? profile.username.trim().startsWith('@')
        ? profile.username.trim()
        : `@${profile.username.trim()}`
      : '@developer';

    const updated: UserProfileData = {
      ...profile,
      username: cleanUsername,
    };

    setProfile(updated);
    setIsEditing(false);

    if (onUpdateProfile) {
      onUpdateProfile(updated);
    }
  };

  const handleTogglePreference = async (
    key: keyof NotificationPreferences,
  ) => {
    if (savingRef.current || notifLoading) {
      return;
    }

    const previousValue = notifPrefs[key];

    const updatedPrefs: NotificationPreferences = {
      ...notifPrefs,
      [key]: !previousValue,
    };

    // Optimistic UI update.
    setNotifPrefs(updatedPrefs);
    setNotifError(null);
    setNotifSaved(false);
    setNotifSaving(true);
    savingRef.current = true;

    try {
      // Keep the partial update payload expected by the API.
      const saved = await settingsApi.updateNotificationPreferences({
        [key]: !previousValue,
      });

      confirmedPrefsRef.current = saved;
      setNotifPrefs(saved);
      setNotifSaved(true);

      setTimeout(() => {
        setNotifSaved(false);
      }, 2000);
    } catch {
      // Restore the last successfully confirmed server state.
      setNotifPrefs(confirmedPrefsRef.current);
      setNotifError(
        'Unable to save preference. Restored previous settings.',
      );
    } finally {
      savingRef.current = false;
      setNotifSaving(false);
    }
  };

  const tabButtonClass = (tab: typeof activeTab) =>
    `min-h-10 rounded-lg px-3 py-2 text-xs font-semibold focus:outline-none focus:ring-2 focus:ring-[#1FB5A4] focus:ring-offset-2 sm:px-4 ${
      activeTab === tab
        ? 'bg-[#0B6B63] text-white'
        : 'text-slate-600 hover:bg-[#CDEFE6] hover:text-[#0B6B63]'
    }`;

  return (
    <main className="mx-auto w-full max-w-6xl space-y-6 p-4 sm:p-6 lg:p-8">
      {/* Profile banner */}
      <section className="rounded-xl border border-[#E5344A]/50 hero-vibrant p-5 text-white sm:p-7">
        <div className="flex flex-col justify-between gap-6 lg:flex-row lg:items-center">
          <div className="flex min-w-0 items-center gap-4 sm:gap-5">
            <div className="relative flex h-16 w-16 shrink-0 items-center justify-center rounded-xl border border-white/20 bg-white/10 text-xl font-bold sm:h-20 sm:w-20 sm:text-2xl">
              {initials}
              <span className="absolute -bottom-1 -right-1 rounded-full border-2 border-[#0B6B63] bg-white p-1 text-[#0B6B63]">
                <CheckCircle2 className="h-3.5 w-3.5" />
              </span>
            </div>

            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="!text-white text-xl font-bold tracking-tight sm:text-2xl">
                  {profile.fullName}
                </h1>
                <span className="rounded-full border border-white/25 bg-white/10 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-white">
                  Team Admin
                </span>
              </div>

              <p className="mt-1 break-words text-xs text-white/75 sm:text-sm">
                {profile.username} • {profile.role} • {profile.team}
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-5 sm:justify-end">
            {/* Keep the label and value as adjacent elements for tests. */}
            <div className="border-l border-white/25 pl-4">
              <p className="text-[10px] font-bold uppercase tracking-wider text-white/75">
                REPOSITORIES MONITORED
              </p>
              <p className="mt-0.5 text-3xl font-extrabold text-white">
                {loadingProjects ? '—' : connectedReposCount}
              </p>
            </div>

            <button
              type="button"
              onClick={() => {
                if (isEditing) {
                  handleSave();
                } else {
                  setIsEditing(true);
                }
              }}
              className="flex shrink-0 items-center gap-2 rounded-lg bg-white px-4 py-2.5 text-xs font-bold text-[#0B6B63] hover:bg-[#CDEFE6] focus:outline-none focus:ring-2 focus:ring-white focus:ring-offset-2 focus:ring-offset-[#0B6B63]"
            >
              {isEditing ? (
                <>
                  <Save className="h-4 w-4" />
                  <span>Save Changes</span>
                </>
              ) : (
                <>
                  <Edit3 className="h-4 w-4" />
                  <span>Edit Profile</span>
                </>
              )}
            </button>
          </div>
        </div>
      </section>

      {/* Tabs */}
      <nav
        aria-label="Profile settings"
        className="flex flex-wrap items-center gap-2 border-b border-[#9ED4C8] pb-3"
      >
        <button
          type="button"
          onClick={() => setActiveTab('profile')}
          className={tabButtonClass('profile')}
        >
          Profile &amp; General
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('security')}
          className={tabButtonClass('security')}
        >
          Security &amp; API Keys
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('notifications')}
          className={tabButtonClass('notifications')}
        >
          Notifications
        </button>
      </nav>

      {/* Profile and general settings */}
      {activeTab === 'profile' && (
        <section className={cardClass}>
          <div className="border-b border-[#9ED4C8] pb-4">
            <h2 className="text-lg font-bold text-[#0E2A2A]">
              Personal Information
            </h2>
            <p className="mt-1 text-xs text-slate-500">
              Manage your public persona, team assignments, and contact email.
            </p>
          </div>

          <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
            {/* Full name */}
            <div>
              <label
                htmlFor="profile-full-name"
                className="mb-2 block text-xs font-bold uppercase tracking-wide text-slate-500"
              >
                Full Name
              </label>

              {isEditing ? (
                <input
                  id="profile-full-name"
                  type="text"
                  value={profile.fullName}
                  onChange={(event) =>
                    setProfile({
                      ...profile,
                      fullName: event.target.value,
                    })
                  }
                  className={inputClass}
                />
              ) : (
                <div className="rounded-lg border border-[#9ED4C8] bg-[#EAF8F3] px-4 py-3 text-sm font-medium text-[#0E2A2A]">
                  {profile.fullName}
                </div>
              )}
            </div>

            {/* Username */}
            <div>
              <label
                htmlFor="profile-username"
                className="mb-2 block text-xs font-bold uppercase tracking-wide text-slate-500"
              >
                Username
              </label>

              {isEditing ? (
                <input
                  id="profile-username"
                  type="text"
                  value={profile.username}
                  onChange={(event) =>
                    setProfile({
                      ...profile,
                      username: event.target.value,
                    })
                  }
                  className={inputClass}
                />
              ) : (
                <div className="rounded-lg border border-[#9ED4C8] bg-[#EAF8F3] px-4 py-3 font-mono text-sm text-[#0E2A2A]">
                  {profile.username}
                </div>
              )}
            </div>

            {/* Email */}
            <div className="md:col-span-2">
              <label className="mb-2 flex items-center gap-2 text-xs font-bold uppercase tracking-wide text-slate-500">
                <span>Email Address</span>
                <span className="rounded border border-[#9ED4C8] bg-[#CDEFE6] px-2 py-0.5 text-[10px] font-semibold text-[#0B6B63]">
                  Verified
                </span>
              </label>

              <div className="flex items-center justify-between gap-3 rounded-lg border border-[#9ED4C8] bg-[#EAF8F3] px-4 py-3 font-mono text-sm text-[#0E2A2A]">
                <span className="break-all">{profile.email}</span>
                <CheckCircle2 className="h-4 w-4 shrink-0 text-[#0B6B63]" />
              </div>
            </div>

            {/* Bio */}
            <div className="md:col-span-2">
              <label
                htmlFor="profile-bio"
                className="mb-2 block text-xs font-bold uppercase tracking-wide text-slate-500"
              >
                Bio &amp; Responsibilities
              </label>

              {isEditing ? (
                <textarea
                  id="profile-bio"
                  rows={3}
                  value={profile.bio || ''}
                  onChange={(event) =>
                    setProfile({
                      ...profile,
                      bio: event.target.value,
                    })
                  }
                  className={`${inputClass} resize-none`}
                />
              ) : (
                <div className="rounded-lg border border-[#9ED4C8] bg-[#EAF8F3] px-4 py-3.5 text-sm leading-relaxed text-slate-700">
                  {profile.bio}
                </div>
              )}
            </div>
          </div>

          {/* Logout */}
          <div className="flex flex-col justify-between gap-4 border-t border-[#9ED4C8] pt-5 sm:flex-row sm:items-center">
            <span className="text-xs text-slate-500">
              Session authenticated via Aegis AI Security Layer
            </span>

            <button
              type="button"
              onClick={onLogout}
              className="flex items-center justify-center gap-2 self-start rounded-lg border border-[#CC1F2E]/25 px-4 py-2 text-xs font-bold text-[#CC1F2E] hover:bg-[#CC1F2E]/5 focus:outline-none focus:ring-2 focus:ring-[#CC1F2E] focus:ring-offset-2 sm:self-auto"
            >
              <LogOut className="h-4 w-4" />
              <span>Log out</span>
            </button>
          </div>
        </section>
      )}

      {/* Security settings */}
      {activeTab === 'security' && (
        <section className={cardClass}>
          <div className="border-b border-[#9ED4C8] pb-4">
            <h2 className="text-lg font-bold text-[#0E2A2A]">
              API Keys &amp; Permissions
            </h2>
            <p className="mt-1 text-xs text-slate-500">
              Review continuous integration analyzer credentials and connected
              project integrations.
            </p>
          </div>

          <div className="space-y-4">
            {/* Webhook credentials */}
            <div className="flex flex-col justify-between gap-3 rounded-lg border border-[#9ED4C8] bg-[#EAF8F3] p-4 sm:flex-row sm:items-center">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <p className="text-sm font-bold text-[#0E2A2A]">
                    Production Webhook Token
                  </p>
                  <span className="rounded border border-[#9ED4C8] bg-white px-2 py-0.5 text-[10px] font-semibold text-slate-600">
                    Not configured
                  </span>
                </div>

                <p className="mt-1 text-xs text-slate-500">
                  Webhook token generation is managed by workspace
                  administrators. No token currently active.
                </p>
              </div>

              <button
                type="button"
                disabled
                title="Webhook regeneration is disabled in this environment"
                className="flex shrink-0 cursor-not-allowed items-center gap-1.5 self-start rounded-lg border border-[#9ED4C8] bg-slate-100 px-3 py-1.5 text-xs font-semibold text-slate-400 sm:self-auto"
              >
                <Lock className="h-3.5 w-3.5" />
                <span>Regenerate</span>
              </button>
            </div>

            {/* Repository integrations */}
            <div className="flex flex-col justify-between gap-3 rounded-lg border border-[#9ED4C8] bg-[#EAF8F3] p-4 sm:flex-row sm:items-center">
              <div>
                <p className="text-sm font-bold text-[#0E2A2A]">
                  GitHub Repository Integrations
                </p>

                <p className="mt-1 text-xs font-semibold text-[#0B6B63]">
                  {loadingProjects
                    ? 'Checking repository connections...'
                    : `${connectedReposCount} of ${projects.length} Repositories Connected`}
                </p>
              </div>

              <button
                type="button"
                onClick={() => onNavigate('projects')}
                className="flex shrink-0 items-center gap-1.5 self-start rounded-lg border border-[#9ED4C8] bg-white px-3.5 py-1.5 text-xs font-semibold text-[#0B6B63] hover:bg-[#CDEFE6] sm:self-auto"
              >
                <span>View Projects</span>
                <ArrowRight className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        </section>
      )}

      {/* Notification settings */}
      {activeTab === 'notifications' && (
        <section className={cardClass}>
          <div className="border-b border-[#9ED4C8] pb-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-lg font-bold text-[#0E2A2A]">
                Notification Preferences
              </h2>

              {notifSaving && (
                <div
                  className="flex items-center gap-1.5 text-xs font-medium text-[#0B6B63]"
                  role="status"
                >
                  <Loader2 className="h-3.5 w-3.5" />
                  <span>Saving...</span>
                </div>
              )}

              {notifSaved && (
                <span
                  className="rounded border border-[#9ED4C8] bg-[#CDEFE6] px-2 py-1 text-xs font-semibold text-[#0B6B63]"
                  role="status"
                >
                  Saved ✓
                </span>
              )}
            </div>

            <p className="mt-1 text-xs leading-relaxed text-slate-500">
              Choose which events Aegis AI should remember as your alert
              preferences. Delivery channels (email, Slack) are configured
              separately and must be enabled in your organization settings.
            </p>
          </div>

          {/* Initial load warning */}
          {notifLoadWarning && (
            <div
              className="flex items-center gap-2.5 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800"
              role="alert"
            >
              <AlertCircle className="h-4 w-4 shrink-0 text-[#B45309]" />
              <span>
                Could not load preferences from server. Displaying default
                settings.
              </span>
            </div>
          )}

          {/* Save error */}
          {notifError && (
            <div
              className="flex items-center gap-2.5 rounded-lg border border-[#CC1F2E]/20 bg-[#CC1F2E]/5 p-3 text-xs text-[#CC1F2E]"
              role="alert"
            >
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{notifError}</span>
            </div>
          )}

          <div className="space-y-3">
            <label
              className={`flex items-center justify-between gap-4 rounded-lg border border-[#9ED4C8] p-4 ${
                notifSaving || notifLoading
                  ? 'cursor-not-allowed bg-slate-50 opacity-70'
                  : 'cursor-pointer hover:bg-[#EAF8F3]'
              }`}
            >
              <div>
                <p className="text-sm font-semibold text-[#0E2A2A]">
                  High Risk Threshold Exceeded
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  Alert immediately when pull requests exceed 48h
                </p>
              </div>

              <input
                type="checkbox"
                checked={notifPrefs.high_risk_threshold}
                onChange={() =>
                  handleTogglePreference('high_risk_threshold')
                }
                disabled={notifSaving || notifLoading}
                className="h-4 w-4 shrink-0 cursor-pointer accent-[#0B6B63] disabled:cursor-not-allowed"
              />
            </label>

            <label
              className={`flex items-center justify-between gap-4 rounded-lg border border-[#9ED4C8] p-4 ${
                notifSaving || notifLoading
                  ? 'cursor-not-allowed bg-slate-50 opacity-70'
                  : 'cursor-pointer hover:bg-[#EAF8F3]'
              }`}
            >
              <div>
                <p className="text-sm font-semibold text-[#0E2A2A]">
                  Weekly Health Summary Digest
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  Receive comprehensive PDF report every Monday at 9 AM
                </p>
              </div>

              <input
                type="checkbox"
                checked={notifPrefs.weekly_digest}
                onChange={() => handleTogglePreference('weekly_digest')}
                disabled={notifSaving || notifLoading}
                className="h-4 w-4 shrink-0 cursor-pointer accent-[#0B6B63] disabled:cursor-not-allowed"
              />
            </label>
          </div>
        </section>
      )}
    </main>
  );
};
