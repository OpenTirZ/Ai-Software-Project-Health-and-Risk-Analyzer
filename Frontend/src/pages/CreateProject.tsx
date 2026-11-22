import React, { useState } from 'react';
import type { PageView } from '../types';
import { Layers, FileText, ArrowRight, AlertCircle, Loader2, Check, ArrowLeft, Tag } from 'lucide-react';
import { projectApi, type ProjectResponse } from '../services/api';

interface CreateProjectProps {
  onProjectCreated: (project: ProjectResponse) => void;
  onNavigate: (view: PageView) => void;
}

export const CreateProject: React.FC<CreateProjectProps> = ({ onProjectCreated, onNavigate }) => {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [projectType, setProjectType] = useState('backend-service');
  const [errors, setErrors] = useState<{ name?: string }>({});
  const [apiError, setApiError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const validate = (): boolean => {
    const newErrors: { name?: string } = {};

    if (!name.trim()) {
      newErrors.name = 'Project name is required.';
    } else if (name.trim().length < 3) {
      newErrors.name = 'Project name must be at least 3 characters long.';
    } else if (!/^[a-zA-Z0-9-_ ]+$/.test(name)) {
      newErrors.name = 'Project name can only contain letters, numbers, hyphens, and spaces.';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setApiError(null);

    if (!validate()) {
      return;
    }

    setIsLoading(true);
    try {
      const newProject = await projectApi.createProject({
        name: name.trim(),
        description: description.trim(),
        projectType,
      });
      setSuccessMsg(`Project "${newProject.name}" created successfully!`);
      setTimeout(() => {
        onProjectCreated(newProject);
        onNavigate('connect-repo');
      }, 700);
    } catch (err: any) {
      setApiError(err.message || 'Failed to create project. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="p-4 md:p-8 max-w-4xl mx-auto space-y-6">
      {/* Top Breadcrumb Navigation */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => onNavigate('projects')}
          className="inline-flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-800 font-medium transition-colors cursor-pointer"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Repositories</span>
        </button>
      </div>

      {/* Stepper Wizard Indicator */}
      <div className="bg-white rounded-2xl border border-slate-200/80 p-4 md:p-6 shadow-sm">
        <div className="flex items-center justify-between max-w-lg mx-auto">
          {/* Step 1 */}
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-indigo-600 text-white font-bold flex items-center justify-center text-sm shadow-md shadow-indigo-200">
              1
            </div>
            <div>
              <p className="text-xs font-bold text-indigo-600 uppercase tracking-wider">Step 1</p>
              <p className="text-sm font-semibold text-slate-900">Project Details</p>
            </div>
          </div>

          {/* Divider */}
          <div className="flex-1 h-0.5 bg-slate-200 mx-4" />

          {/* Step 2 */}
          <div className="flex items-center gap-3 opacity-60">
            <div className="w-8 h-8 rounded-full bg-slate-200 text-slate-600 font-bold flex items-center justify-center text-sm">
              2
            </div>
            <div>
              <p className="text-xs font-bold text-slate-500 uppercase tracking-wider">Step 2</p>
              <p className="text-sm font-semibold text-slate-600">Connect GitHub</p>
            </div>
          </div>
        </div>
      </div>

      {/* Form Card */}
      <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm p-6 md:p-8">
        <div className="mb-6">
          <h1 className="text-2xl md:text-3xl font-bold text-slate-900 tracking-tight">
            Create New Project
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Define your project metadata to initialize कVaच's health analytics and sprint risk tracking.
          </p>
        </div>

        {/* Backend Error Banner */}
        {apiError && (
          <div className="mb-6 p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-sm flex items-start gap-2.5">
            <AlertCircle className="w-5 h-5 shrink-0 mt-0.5 text-rose-500" />
            <div>
              <p className="font-semibold">Creation Error</p>
              <p className="text-xs mt-0.5">{apiError}</p>
            </div>
          </div>
        )}

        {/* Success Banner */}
        {successMsg && (
          <div className="mb-6 p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-sm flex items-center gap-2.5">
            <Check className="w-5 h-5 text-emerald-600" />
            <p className="font-semibold">{successMsg}</p>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-6" noValidate>
          {/* Project Name Field */}
          <div>
            <label htmlFor="project-name" className="text-sm font-bold text-slate-900 mb-2 flex items-center gap-2">
              <Layers className="w-4 h-4 text-indigo-500" />
              <span>Project Name <span className="text-rose-500">*</span></span>
            </label>
            <div className={`rounded-xl border shadow-sm transition-all overflow-hidden bg-slate-50/50 ${
              errors.name ? 'border-rose-400 focus-within:ring-2 focus-within:ring-rose-100' : 'border-slate-300 focus-within:border-indigo-600 focus-within:ring-2 focus-within:ring-indigo-100'
            }`}>
              <input
                id="project-name"
                type="text"
                disabled={isLoading}
                value={name}
                onChange={(e) => {
                  setName(e.target.value);
                  if (errors.name) setErrors({});
                }}
                placeholder="e.g. payment-gateway-service"
                className="w-full px-4 py-3 text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none bg-transparent disabled:opacity-60"
              />
            </div>
            {errors.name ? (
              <p className="text-xs text-rose-600 mt-1.5 font-medium flex items-center gap-1">
                <AlertCircle className="w-3.5 h-3.5" />
                {errors.name}
              </p>
            ) : (
              <p className="text-xs text-slate-400 mt-1.5">
                Must be at least 3 characters. This will identify your project across audits.
              </p>
            )}
          </div>

          {/* Project Type / Category */}
          <div>
            <label className="text-sm font-bold text-slate-900 mb-2 flex items-center gap-2">
              <Tag className="w-4 h-4 text-indigo-500" />
              <span>Architecture / Project Type</span>
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {[
                { id: 'backend-service', label: 'Backend / Microservice', desc: 'Node, Python, Go, Java' },
                { id: 'frontend-app', label: 'Frontend / Web App', desc: 'React, Vue, Next.js' },
                { id: 'fullstack-monorepo', label: 'Monorepo / Fullstack', desc: 'Turborepo, Nx, Multi-tier' },
              ].map((item) => (
                <button
                  type="button"
                  key={item.id}
                  onClick={() => setProjectType(item.id)}
                  className={`p-3.5 rounded-xl border text-left transition-all cursor-pointer ${
                    projectType === item.id
                      ? 'border-indigo-600 bg-indigo-50/50 ring-2 ring-indigo-100 text-slate-900'
                      : 'border-slate-200 bg-white hover:border-slate-300 text-slate-700'
                  }`}
                >
                  <p className="text-xs font-bold">{item.label}</p>
                  <p className="text-[11px] text-slate-400 mt-0.5">{item.desc}</p>
                </button>
              ))}
            </div>
          </div>

          {/* Project Description */}
          <div>
            <label htmlFor="project-description" className="text-sm font-bold text-slate-900 mb-2 flex items-center gap-2">
              <FileText className="w-4 h-4 text-indigo-500" />
              <span>Project Description <span className="text-xs font-normal text-slate-400">(Optional)</span></span>
            </label>
            <div className="rounded-xl border border-slate-300 focus-within:border-indigo-600 focus-within:ring-2 focus-within:ring-indigo-100 transition-all overflow-hidden bg-slate-50/50">
              <textarea
                id="project-description"
                rows={3}
                disabled={isLoading}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Provide architecture context, SLA targets, or sprint objectives..."
                className="w-full px-4 py-3 text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none bg-transparent resize-none disabled:opacity-60"
              />
            </div>
          </div>

          {/* Actions */}
          <div className="pt-4 border-t border-slate-100 flex items-center justify-between">
            <button
              type="button"
              onClick={() => onNavigate('projects')}
              className="px-5 py-2.5 rounded-xl border border-slate-300 text-sm font-semibold text-slate-700 hover:bg-slate-50 transition-colors cursor-pointer"
            >
              Cancel
            </button>

            <button
              type="submit"
              disabled={isLoading || Boolean(successMsg)}
              className="px-6 py-2.5 rounded-xl text-white text-sm font-semibold shadow-md shadow-indigo-600/25 transition-all hover:opacity-95 active:scale-95 flex items-center gap-2 cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed"
              style={{
                background: 'linear-gradient(90deg, rgba(0, 0, 0, 0.2) 0%, rgba(0, 0, 0, 0.2) 100%), linear-gradient(90deg, rgb(99, 102, 241) 0%, rgb(168, 85, 247) 100%)',
              }}
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Creating Project...</span>
                </>
              ) : successMsg ? (
                <>
                  <Check className="w-4 h-4" />
                  <span>Continuing to Step 2...</span>
                </>
              ) : (
                <>
                  <span>Next: Connect Repository</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
