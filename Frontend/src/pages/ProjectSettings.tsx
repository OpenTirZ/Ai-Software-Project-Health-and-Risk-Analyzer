import React, { useState } from 'react';
import type { PageView } from '../types';
import type { ProjectResponse } from '../services/api';
import { projectLifecycleApi } from '../services/api';
import {
  Settings,
  Archive,
  Trash2,
  AlertTriangle,
  CheckCircle2,
  Loader2,
  X,
  ShieldAlert,
} from 'lucide-react';

interface ProjectSettingsProps {
  project: ProjectResponse;
  onNavigate: (view: PageView) => void;
  onProjectChanged?: () => void;
}

/* ------------------------------------------------------------------ */
/*  Confirmation Modal                                                 */
/* ------------------------------------------------------------------ */
interface ConfirmModalProps {
  open: boolean;
  title: string;
  description: string;
  projectName: string;
  variant: 'archive' | 'delete';
  loading: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

const ConfirmModal: React.FC<ConfirmModalProps> = ({
  open,
  title,
  description,
  projectName,
  variant,
  loading,
  onConfirm,
  onCancel,
}) => {
  const [typedName, setTypedName] = useState('');
  const [understood, setUnderstood] = useState(false);

  const nameMatches = typedName.trim() === projectName;
  const canConfirm = variant === 'delete' ? nameMatches && understood : nameMatches;

  if (!open) return null;

  const colorMap = {
    archive: {
      ring: 'ring-amber-200',
      iconBg: 'bg-amber-100',
      iconColor: 'text-amber-600',
      btn: 'bg-amber-600 hover:bg-amber-700 focus:ring-amber-500',
      icon: Archive,
    },
    delete: {
      ring: 'ring-red-200',
      iconBg: 'bg-red-100',
      iconColor: 'text-red-600',
      btn: 'bg-[#CC1F2E] hover:bg-red-700 focus:ring-red-500',
      icon: Trash2,
    },
  };
  const cm = colorMap[variant];
  const Icon = cm.icon;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div
        className={`relative w-full max-w-md rounded-2xl bg-white shadow-2xl ring-1 ${cm.ring}`}
      >
        {/* Close */}
        <button
          onClick={onCancel}
          className="absolute right-4 top-4 rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
        >
          <X className="h-4 w-4" />
        </button>

        <div className="p-6">
          {/* Icon */}
          <div className={`mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full ${cm.iconBg}`}>
            <Icon className={`h-6 w-6 ${cm.iconColor}`} />
          </div>

          <h3 className="text-center text-lg font-bold text-slate-900">{title}</h3>
          <p className="mt-2 text-center text-sm text-slate-500">{description}</p>

          {/* Type project name */}
          <div className="mt-5">
            <label className="block text-xs font-medium text-slate-600">
              Type <span className="font-bold text-slate-800">{projectName}</span> to confirm
            </label>
            <input
              type="text"
              value={typedName}
              onChange={(e) => setTypedName(e.target.value)}
              placeholder={projectName}
              className="mt-1.5 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700 placeholder:text-slate-300 focus:border-[#0B6B63] focus:outline-none focus:ring-1 focus:ring-[#0B6B63]"
            />
          </div>

          {/* Double-confirm checkbox for delete */}
          {variant === 'delete' && (
            <label className="mt-4 flex items-start gap-2 rounded-lg border border-red-100 bg-red-50 p-3 cursor-pointer">
              <input
                type="checkbox"
                checked={understood}
                onChange={(e) => setUnderstood(e.target.checked)}
                className="mt-0.5 h-4 w-4 rounded border-red-300 text-red-600 focus:ring-red-500"
              />
              <span className="text-xs text-red-700">
                I understand this action is irreversible. All associated data including
                commits, PRs, issues, reports, and metrics will be permanently removed.
              </span>
            </label>
          )}

          {/* Actions */}
          <div className="mt-6 flex gap-3">
            <button
              onClick={onCancel}
              disabled={loading}
              className="flex-1 rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              onClick={onConfirm}
              disabled={!canConfirm || loading}
              className={`flex flex-1 items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50 transition-colors ${cm.btn}`}
            >
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Icon className="h-4 w-4" />
              )}
              {variant === 'delete' ? 'Delete Project' : 'Archive Project'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

/* ------------------------------------------------------------------ */
/*  Main Component                                                     */
/* ------------------------------------------------------------------ */
export const ProjectSettings: React.FC<ProjectSettingsProps> = ({
  project,
  onNavigate,
  onProjectChanged,
}) => {
  const [archiveModal, setArchiveModal] = useState(false);
  const [deleteModal, setDeleteModal] = useState(false);
  const [archiving, setArchiving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [result, setResult] = useState<{ type: 'success' | 'error'; message: string } | null>(
    null
  );

  const handleArchive = async () => {
    setArchiving(true);
    setResult(null);
    try {
      const res = await projectLifecycleApi.archiveProject(project.id);
      setArchiveModal(false);
      setResult({ type: 'success', message: res.message || 'Project archived successfully.' });
      onProjectChanged?.();
    } catch (err: any) {
      setResult({ type: 'error', message: err.message || 'Archive failed.' });
    } finally {
      setArchiving(false);
    }
  };

  const handleDelete = async () => {
    setDeleting(true);
    setResult(null);
    try {
      const res = await projectLifecycleApi.deleteProject(project.id);
      setDeleteModal(false);
      setResult({
        type: 'success',
        message: res.message || 'Project deleted successfully.',
      });
      // Navigate away after short delay
      setTimeout(() => onNavigate('projects'), 2000);
    } catch (err: any) {
      setResult({ type: 'error', message: err.message || 'Delete failed.' });
    } finally {
      setDeleting(false);
    }
  };

  const projectStatus = project.status || 'active';

  return (
    <div className="mx-auto max-w-3xl space-y-8 p-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#EAF8F3]">
            <Settings className="h-5 w-5 text-[#0B6B63]" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Project Settings</h1>
            <p className="text-sm text-slate-500">{project.name}</p>
          </div>
        </div>
      </div>

      {/* Result banner */}
      {result && (
        <div
          className={`rounded-lg border p-4 text-sm ${
            result.type === 'success'
              ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
              : 'border-red-200 bg-red-50 text-red-700'
          }`}
        >
          {result.type === 'success' ? (
            <CheckCircle2 className="mr-2 inline-block h-4 w-4" />
          ) : (
            <AlertTriangle className="mr-2 inline-block h-4 w-4" />
          )}
          {result.message}
        </div>
      )}

      {/* Project Status */}
      <section className="rounded-xl border border-[#9ED4C8] bg-white p-6">
        <h2 className="text-base font-semibold text-slate-800">Project Status</h2>
        <div className="mt-3 flex items-center gap-3">
          <span
            className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold ${
              projectStatus === 'active'
                ? 'bg-emerald-100 text-emerald-700'
                : projectStatus === 'archived'
                ? 'bg-amber-100 text-amber-700'
                : 'bg-red-100 text-red-700'
            }`}
          >
            <span
              className={`h-2 w-2 rounded-full ${
                projectStatus === 'active'
                  ? 'bg-emerald-500'
                  : projectStatus === 'archived'
                  ? 'bg-amber-500'
                  : 'bg-red-500'
              }`}
            />
            {projectStatus.charAt(0).toUpperCase() + projectStatus.slice(1)}
          </span>
          <span className="text-xs text-slate-400">
            Created{' '}
            {project.createdAt
              ? new Date(project.createdAt).toLocaleDateString('en-US', {
                  month: 'short',
                  day: 'numeric',
                  year: 'numeric',
                })
              : 'recently'}
          </span>
        </div>
      </section>

      {/* Archive Section */}
      <section className="rounded-xl border border-amber-200 bg-white p-6">
        <div className="flex items-start gap-4">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-amber-100">
            <Archive className="h-5 w-5 text-amber-600" />
          </div>
          <div className="flex-1">
            <h2 className="text-base font-semibold text-slate-800">Archive Project</h2>
            <p className="mt-1 text-sm text-slate-500">
              Archiving makes the project read-only. Data is preserved but no new syncs,
              reports, or health checks will run. This action can be reversed by an admin.
            </p>
            <button
              onClick={() => setArchiveModal(true)}
              disabled={projectStatus !== 'active'}
              className="mt-4 rounded-lg border border-amber-300 bg-amber-50 px-4 py-2 text-sm font-medium text-amber-700 hover:bg-amber-100 disabled:cursor-not-allowed disabled:opacity-50 transition-colors"
            >
              <Archive className="mr-1.5 inline-block h-4 w-4" />
              Archive this project
            </button>
            {projectStatus === 'archived' && (
              <p className="mt-2 text-xs text-amber-600">
                This project is already archived.
              </p>
            )}
          </div>
        </div>
      </section>

      {/* Danger Zone — Delete */}
      <section className="rounded-xl border-2 border-red-200 bg-white p-6">
        <div className="flex items-start gap-4">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-red-100">
            <ShieldAlert className="h-5 w-5 text-[#CC1F2E]" />
          </div>
          <div className="flex-1">
            <h2 className="text-base font-semibold text-[#CC1F2E]">Danger Zone</h2>
            <p className="mt-1 text-sm text-slate-500">
              Permanently delete this project and all associated data. This includes
              commits, pull requests, issues, milestones, reports, health metrics, and
              contributor records. <strong>This action cannot be undone.</strong>
            </p>
            <button
              onClick={() => setDeleteModal(true)}
              className="mt-4 rounded-lg bg-[#CC1F2E] px-4 py-2 text-sm font-semibold text-white hover:bg-red-700 transition-colors"
            >
              <Trash2 className="mr-1.5 inline-block h-4 w-4" />
              Delete this project
            </button>
          </div>
        </div>
      </section>

      {/* Modals */}
      <ConfirmModal
        open={archiveModal}
        title="Archive Project"
        description="This will make the project read-only. No new data will be synced."
        projectName={project.name}
        variant="archive"
        loading={archiving}
        onConfirm={handleArchive}
        onCancel={() => setArchiveModal(false)}
      />

      <ConfirmModal
        open={deleteModal}
        title="Delete Project Permanently"
        description="This will permanently remove the project and cascade-delete all associated data across all collections."
        projectName={project.name}
        variant="delete"
        loading={deleting}
        onConfirm={handleDelete}
        onCancel={() => setDeleteModal(false)}
      />
    </div>
  );
};

export default ProjectSettings;
