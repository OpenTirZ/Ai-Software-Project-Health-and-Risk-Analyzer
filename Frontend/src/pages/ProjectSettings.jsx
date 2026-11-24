import React, { useState } from 'react';
import { 
  Settings, 
  Archive, 
  Trash2, 
  AlertTriangle, 
  Save, 
  CheckCircle2, 
  GitBranch, 
  Bell, 
  ShieldAlert, 
  X, 
  HelpCircle,
  FolderGit2
} from 'lucide-react';

export const ProjectSettings = ({ 
  projectId = 'proj_core_platform', 
  selectedRepo = 'DevOps-Projects',
  onNavigate,
  onRepoDeleted
}) => {
  // General Configuration State
  const [projectName, setProjectName] = useState(selectedRepo);
  const [defaultBranch, setDefaultBranch] = useState('main');
  const [prLatencyThreshold, setPrLatencyThreshold] = useState(24);
  const [staleIssueThreshold, setStaleIssueThreshold] = useState(14);
  const [slackAlertsEnabled, setSlackAlertsEnabled] = useState(true);
  const [weeklyDigestEnabled, setWeeklyDigestEnabled] = useState(true);

  // Status State
  const [isArchived, setIsArchived] = useState(false);
  const [saveSuccessMsg, setSaveSuccessMsg] = useState(null);

  // Archive Modal State (Double-confirmation dialog)
  const [showArchiveModal, setShowArchiveModal] = useState(false);
  const [archiveConfirmText, setArchiveConfirmText] = useState('');
  const [archiveConsentChecked, setArchiveConsentChecked] = useState(false);

  // Delete Modal State (Double-confirmation dialog)
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deleteConfirmText, setDeleteConfirmText] = useState('');
  const [deleteConsentChecked, setDeleteConsentChecked] = useState(false);

  const showToast = (msg) => {
    setSaveSuccessMsg(msg);
    setTimeout(() => setSaveSuccessMsg(null), 3500);
  };

  const handleSaveGeneralSettings = (e) => {
    e.preventDefault();
    showToast('Project settings successfully saved.');
  };

  // Archive Execution
  const handleConfirmArchive = () => {
    setIsArchived(true);
    setShowArchiveModal(false);
    setArchiveConfirmText('');
    setArchiveConsentChecked(false);
    showToast(`Project "${selectedRepo}" has been moved to read-only Archive.`);
  };

  // Delete Execution
  const handleConfirmDelete = () => {
    setShowDeleteModal(false);
    setDeleteConfirmText('');
    setDeleteConsentChecked(false);
    showToast(`Project "${selectedRepo}" deleted permanently.`);

    if (onRepoDeleted) {
      onRepoDeleted(selectedRepo);
    }
    setTimeout(() => {
      if (onNavigate) onNavigate('projects');
    }, 1200);
  };

  const isArchiveUnlocked =
    archiveConsentChecked &&
    archiveConfirmText.trim().toLowerCase() === selectedRepo.toLowerCase();

  const isDeleteUnlocked =
    deleteConsentChecked &&
    deleteConfirmText.trim().toLowerCase() === selectedRepo.toLowerCase();

  return (
    <div className="p-6 md:p-8 max-w-5xl mx-auto space-y-8">
      {/* Toast Feedback */}
      {saveSuccessMsg && (
        <div className="p-3.5 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-xl text-xs font-semibold flex items-center justify-between shadow-xs animate-in fade-in">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
            <span>{saveSuccessMsg}</span>
          </div>
          <button onClick={() => setSaveSuccessMsg(null)} className="text-emerald-600">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 pb-2 border-b border-slate-100">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-slate-100 text-slate-700 border border-slate-200">
              REPOSITORY SETTINGS
            </span>
            <span className="text-xs text-slate-400 font-mono">
              Target: <strong className="text-slate-700">{selectedRepo}</strong>
            </span>
          </div>
          <h1 className="text-2xl md:text-3xl font-extrabold text-slate-900 tracking-tight">
            Project & Policy Settings
          </h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Configure telemetry polling cadences, review SLAs, and repository lifecycle actions.
          </p>
        </div>

        {isArchived && (
          <span className="px-3.5 py-1.5 rounded-full bg-amber-50 text-amber-800 border border-amber-300 font-bold text-xs flex items-center gap-1.5">
            <Archive className="w-3.5 h-3.5 text-amber-600" />
            <span>ARCHIVED (READ-ONLY)</span>
          </span>
        )}
      </div>

      {/* General Settings Form */}
      <form onSubmit={handleSaveGeneralSettings} className="space-y-6">
        <div className="bg-white rounded-2xl p-6 md:p-8 border border-slate-200/90 shadow-xs space-y-5">
          <h2 className="text-base font-bold text-slate-900 border-b border-slate-100 pb-3 flex items-center gap-2">
            <Settings className="w-4 h-4 text-indigo-600" />
            <span>General Repository Configuration</span>
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">
                Display Project Name
              </label>
              <input
                type="text"
                value={projectName}
                onChange={(e) => setProjectName(e.target.value)}
                className="w-full text-xs px-3.5 py-2.5 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">
                Monitored Trunk Branch
              </label>
              <select
                value={defaultBranch}
                onChange={(e) => setDefaultBranch(e.target.value)}
                className="w-full text-xs px-3.5 py-2.5 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 bg-white cursor-pointer"
              >
                <option value="main">main (Default Trunk)</option>
                <option value="master">master</option>
                <option value="develop">develop</option>
                <option value="release/v2">release/v2</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-5 pt-2">
            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">
                PR Review Turnaround SLA (Hours)
              </label>
              <input
                type="number"
                min={4}
                max={96}
                value={prLatencyThreshold}
                onChange={(e) => setPrLatencyThreshold(Number(e.target.value))}
                className="w-full text-xs px-3.5 py-2.5 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
              />
              <p className="text-[11px] text-slate-400 mt-1">
                PRs unreviewed past this threshold trigger high-priority bottleneck warnings.
              </p>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">
                Issue Inactivity Dormancy SLA (Days)
              </label>
              <input
                type="number"
                min={3}
                max={60}
                value={staleIssueThreshold}
                onChange={(e) => setStaleIssueThreshold(Number(e.target.value))}
                className="w-full text-xs px-3.5 py-2.5 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
              />
              <p className="text-[11px] text-slate-400 mt-1">
                Issues idle beyond this count are classified as stale technical debt.
              </p>
            </div>
          </div>

          {/* Alert Toggles */}
          <div className="pt-4 border-t border-slate-100 space-y-3">
            <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
              Automated Governance Notifications
            </h3>

            <div className="flex items-center justify-between p-3 rounded-xl bg-slate-50 border border-slate-200/80">
              <div className="flex items-center gap-2.5">
                <Bell className="w-4 h-4 text-indigo-600" />
                <div>
                  <p className="text-xs font-bold text-slate-800">Slack Risk Webhook Alerts</p>
                  <p className="text-[11px] text-slate-500">Dispatch alerts when Health Score drops below 70.</p>
                </div>
              </div>
              <input
                type="checkbox"
                checked={slackAlertsEnabled}
                onChange={(e) => setSlackAlertsEnabled(e.target.checked)}
                className="w-4 h-4 accent-indigo-600 cursor-pointer"
              />
            </div>

            <div className="flex items-center justify-between p-3 rounded-xl bg-slate-50 border border-slate-200/80">
              <div className="flex items-center gap-2.5">
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                <div>
                  <p className="text-xs font-bold text-slate-800">Weekly Executive Health Digest</p>
                  <p className="text-[11px] text-slate-500">Summarize commit velocity, bus factor, and stale PRs every Monday.</p>
                </div>
              </div>
              <input
                type="checkbox"
                checked={weeklyDigestEnabled}
                onChange={(e) => setWeeklyDigestEnabled(e.target.checked)}
                className="w-4 h-4 accent-indigo-600 cursor-pointer"
              />
            </div>
          </div>

          <div className="flex justify-end pt-2">
            <button
              type="submit"
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold shadow-md shadow-indigo-600/20 transition-all cursor-pointer"
            >
              <Save className="w-4 h-4" />
              <span>Save Configuration</span>
            </button>
          </div>
        </div>
      </form>

      {/* DANGER & LIFECYCLE ZONE */}
      <div className="bg-white rounded-2xl p-6 md:p-8 border border-rose-200 shadow-xs space-y-5">
        <div className="border-b border-rose-100 pb-3">
          <h2 className="text-base font-bold text-rose-700 flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-rose-600" />
            <span>Danger & Lifecycle Zone</span>
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Destructive and archival repository lifecycle management.
          </p>
        </div>

        {/* Archive Action Card */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-4 rounded-xl bg-amber-50/60 border border-amber-200">
          <div>
            <h3 className="text-sm font-bold text-slate-900 flex items-center gap-1.5">
              <Archive className="w-4 h-4 text-amber-600" />
              <span>Archive this Project</span>
            </h3>
            <p className="text-xs text-slate-600 mt-1 max-w-lg">
              Places telemetry ingestion in read-only mode. Historical scores and reports remain accessible, but live background polling stops.
            </p>
          </div>
          <button
            type="button"
            onClick={() => setShowArchiveModal(true)}
            className="px-4 py-2 rounded-xl bg-white border border-amber-300 text-amber-800 hover:bg-amber-100 text-xs font-bold transition-all shadow-2xs shrink-0 cursor-pointer"
          >
            Archive Project...
          </button>
        </div>

        {/* Delete Action Card */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-4 rounded-xl bg-rose-50/60 border border-rose-200">
          <div>
            <h3 className="text-sm font-bold text-rose-900 flex items-center gap-1.5">
              <Trash2 className="w-4 h-4 text-rose-600" />
              <span>Permanently Delete this Project</span>
            </h3>
            <p className="text-xs text-rose-700/90 mt-1 max-w-lg">
              Irreversible action. Permanently removes all telemetry history, generated PDF reports, developer appeals, and connection metadata.
            </p>
          </div>
          <button
            type="button"
            onClick={() => setShowDeleteModal(true)}
            className="px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-700 text-white text-xs font-bold transition-all shadow-md shadow-rose-600/20 shrink-0 cursor-pointer"
          >
            Delete Project...
          </button>
        </div>
      </div>

      {/* DOUBLE-CONFIRMATION MODAL: ARCHIVE PROJECT */}
      {showArchiveModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-slate-200 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div className="flex items-center gap-2">
                <Archive className="w-5 h-5 text-amber-600" />
                <h3 className="text-base font-bold text-slate-900">
                  Archive Project: {selectedRepo}
                </h3>
              </div>
              <button
                onClick={() => setShowArchiveModal(false)}
                className="text-slate-400 hover:text-slate-600 cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-3.5 rounded-xl bg-amber-50 border border-amber-200 text-xs text-amber-900 space-y-2">
              <p className="font-bold flex items-center gap-1.5">
                <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
                <span>Notice: Read-Only Telemetry Mode</span>
              </p>
              <p>
                Archiving will freeze automated GitHub synchronizations for <strong>{selectedRepo}</strong>. Historical audits, appeals, and reports will remain viewable in read-only status.
              </p>
            </div>

            <div className="space-y-3 pt-1">
              {/* Checkbox 1: Consent */}
              <label className="flex items-start gap-2.5 text-xs text-slate-700 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={archiveConsentChecked}
                  onChange={(e) => setArchiveConsentChecked(e.target.checked)}
                  className="mt-0.5 w-4 h-4 accent-amber-600 cursor-pointer shrink-0"
                />
                <span>
                  I understand that archiving freezes live metric recalculations and puts this repository into read-only mode.
                </span>
              </label>

              {/* Input 2: Type repo name */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Type <span className="font-mono font-bold text-slate-900">{selectedRepo}</span> to confirm:
                </label>
                <input
                  type="text"
                  value={archiveConfirmText}
                  onChange={(e) => setArchiveConfirmText(e.target.value)}
                  placeholder={`Type "${selectedRepo}"`}
                  className="w-full text-xs px-3.5 py-2.5 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-amber-500/20 font-mono"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setShowArchiveModal(false)}
                className="px-4 py-2 rounded-xl border border-slate-200 text-xs font-semibold text-slate-600 hover:bg-slate-50 cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={!isArchiveUnlocked}
                onClick={handleConfirmArchive}
                className="px-5 py-2 rounded-xl bg-amber-600 hover:bg-amber-700 text-white text-xs font-bold shadow-md shadow-amber-600/20 disabled:opacity-40 disabled:cursor-not-allowed transition-all cursor-pointer"
              >
                Confirm & Archive Project
              </button>
            </div>
          </div>
        </div>
      )}

      {/* DOUBLE-CONFIRMATION MODAL: DELETE PROJECT */}
      {showDeleteModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-rose-200 space-y-4">
            <div className="flex items-center justify-between border-b border-rose-100 pb-3">
              <div className="flex items-center gap-2">
                <Trash2 className="w-5 h-5 text-rose-600" />
                <h3 className="text-base font-bold text-rose-900">
                  Delete Project: {selectedRepo}
                </h3>
              </div>
              <button
                onClick={() => setShowDeleteModal(false)}
                className="text-slate-400 hover:text-slate-600 cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-900 space-y-2">
              <p className="font-bold flex items-center gap-1.5 text-rose-700">
                <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
                <span>IRREVERSIBLE DESTRUCTION WARNING</span>
              </p>
              <p>
                Deleting <strong>{selectedRepo}</strong> permanently removes all connected repository records, health histories, AI risk scores, and developer appeals. This action cannot be reversed.
              </p>
            </div>

            <div className="space-y-3 pt-1">
              {/* Checkbox 1: Double confirmation check */}
              <label className="flex items-start gap-2.5 text-xs text-rose-800 cursor-pointer select-none font-medium">
                <input
                  type="checkbox"
                  checked={deleteConsentChecked}
                  onChange={(e) => setDeleteConsentChecked(e.target.checked)}
                  className="mt-0.5 w-4 h-4 accent-rose-600 cursor-pointer shrink-0"
                />
                <span>
                  I acknowledge this repository and all stored telemetry will be wiped permanently without recovery options.
                </span>
              </label>

              {/* Input 2: Type exact repo name */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Type <span className="font-mono font-bold text-rose-700">{selectedRepo}</span> to unlock deletion:
                </label>
                <input
                  type="text"
                  value={deleteConfirmText}
                  onChange={(e) => setDeleteConfirmText(e.target.value)}
                  placeholder={`Type "${selectedRepo}"`}
                  className="w-full text-xs px-3.5 py-2.5 rounded-xl border border-rose-300 focus:outline-none focus:ring-2 focus:ring-rose-500/20 font-mono"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setShowDeleteModal(false)}
                className="px-4 py-2 rounded-xl border border-slate-200 text-xs font-semibold text-slate-600 hover:bg-slate-50 cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={!isDeleteUnlocked}
                onClick={handleConfirmDelete}
                className="px-5 py-2 rounded-xl bg-rose-600 hover:bg-rose-700 text-white text-xs font-bold shadow-md shadow-rose-600/20 disabled:opacity-40 disabled:cursor-not-allowed transition-all cursor-pointer"
              >
                Permanently Delete Project
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ProjectSettings;
