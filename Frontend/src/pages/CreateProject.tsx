import React, { useState } from 'react';
import type { PageView } from '../types';
import {
  Layers,
  FileText,
  ArrowRight,
  AlertCircle,
  Loader2,
  Check,
  ArrowLeft,
  Tag,
} from 'lucide-react';
import { projectApi, type ProjectResponse } from '../services/api';

interface CreateProjectProps {
  onProjectCreated: (project: ProjectResponse) => void;
  onNavigate: (view: PageView) => void;
}

const projectTypes = [
  {
    id: 'backend-service',
    label: 'Backend / Microservice',
    description: 'Node, Python, Go, Java',
  },
  {
    id: 'frontend-app',
    label: 'Frontend / Web App',
    description: 'React, Vue, Next.js',
  },
  {
    id: 'fullstack-monorepo',
    label: 'Monorepo / Fullstack',
    description: 'Turborepo, Nx, Multi-tier',
  },
];

export const CreateProject: React.FC<CreateProjectProps> = ({
  onProjectCreated,
  onNavigate,
}) => {
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
      newErrors.name =
        'Project name can only contain letters, numbers, hyphens, and spaces.';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setApiError(null);

    if (!validate()) return;

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
    <main className="mx-auto w-full max-w-4xl space-y-6 p-4 sm:p-6 lg:p-8">
      <button
        type="button"
        onClick={() => onNavigate('projects')}
        className="inline-flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-[#0B6B63] focus:outline-none focus:ring-2 focus:ring-teal-700 focus:ring-offset-2"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Projects
      </button>

      <section className="rounded-xl border border-[#9ED4C8] bg-white p-5 sm:p-6">
        <div className="mx-auto flex max-w-lg items-center">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#0B6B63] text-sm font-bold text-white">
              1
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-[#0B6B63]">
                Step 1
              </p>
              <p className="text-sm font-semibold text-slate-900">
                Project Details
              </p>
            </div>
          </div>

          <div className="mx-4 h-px flex-1 bg-[#9ED4C8]" />

          <div className="flex items-center gap-3 opacity-60">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-[#9ED4C8] bg-slate-50 text-sm font-semibold text-slate-600">
              2
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                Step 2
              </p>
              <p className="text-sm font-semibold text-slate-600">
                Connect GitHub
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="rounded-xl border border-[#9ED4C8] bg-white p-5 sm:p-8">
        <div className="mb-7">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-[#0B6B63]">
            Project setup
          </p>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
            Create New Project
          </h1>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            Define your project metadata to initialize कVaच's health analytics and sprint risk tracking.
          </p>
        </div>

        {apiError && (
          <div
            role="alert"
            className="mb-6 flex items-start gap-3 rounded-lg border border-[#CC1F2E]/20 bg-[#CC1F2E]/5 p-4 text-sm text-[#CC1F2E]"
          >
            <AlertCircle className="mt-0.5 h-5 w-5 shrink-0" />
            <div>
              <p className="font-semibold">Creation Error</p>
              <p className="mt-1 text-xs">{apiError}</p>
            </div>
          </div>
        )}

        {successMsg && (
          <div
            role="status"
            className="mb-6 flex items-center gap-3 rounded-lg border border-[#0B6B63]/20 bg-[#CDEFE6] p-4 text-sm text-[#0B6B63]"
          >
            <Check className="h-5 w-5 shrink-0" />
            <p className="font-semibold">{successMsg}</p>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-7" noValidate>

          <div>
            <label
              htmlFor="project-name"
              className="mb-2 flex items-center gap-2 text-sm font-semibold text-slate-900"
            >
              <Layers className="h-4 w-4 text-[#0B6B63]" />
              Project Name <span className="text-[#CC1F2E]">*</span>
            </label>

            <input
              id="project-name"
              type="text"
              disabled={isLoading}
              value={name}
              onChange={(event) => {
                setName(event.target.value);
                if (errors.name) setErrors({});
              }}
              placeholder="e.g. payment-gateway-service"
              aria-invalid={Boolean(errors.name)}
              aria-describedby={errors.name ? 'project-name-error' : 'project-name-help'}
              className={`w-full rounded-lg border bg-white px-4 py-3 text-sm text-slate-900 outline-none placeholder:text-slate-400 focus:ring-2 focus:ring-[#0B6B63]/15 disabled:opacity-60 ${
                errors.name
                  ? 'border-[#CC1F2E] focus:border-[#CC1F2E]'
                  : 'border-[#9ED4C8] focus:border-[#0B6B63]'
              }`}
            />

            {errors.name ? (
              <p
                id="project-name-error"
                className="mt-2 flex items-center gap-1.5 text-xs font-medium text-[#CC1F2E]"
              >
                <AlertCircle className="h-3.5 w-3.5" />
                {errors.name}
              </p>
            ) : (
              <p id="project-name-help" className="mt-2 text-xs text-slate-500">
                At least 3 characters. Use letters, numbers, hyphens, or spaces.
              </p>
            )}
          </div>

          <fieldset>
            <legend className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-900">
              <Tag className="h-4 w-4 text-[#0B6B63]" />
              Architecture / Project Type
            </legend>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              {projectTypes.map((item) => {
                const selected = projectType === item.id;

                return (
                  <button
                    type="button"
                    key={item.id}
                    disabled={isLoading}
                    aria-pressed={selected}
                    onClick={() => setProjectType(item.id)}
                    className={`rounded-lg border p-4 text-left focus:outline-none focus:ring-2 focus:ring-teal-700 focus:ring-offset-2 disabled:opacity-60 ${
                      selected
                        ? 'border-[#0B6B63] bg-[#CDEFE6]'
                        : 'border-[#9ED4C8] bg-white hover:bg-slate-50'
                    }`}
                  >
                    <span className="block text-sm font-semibold text-slate-900">
                      {item.label}
                    </span>
                    <span className="mt-1 block text-xs leading-5 text-slate-500">
                      {item.description}
                    </span>
                    {selected && (
                      <span className="mt-3 inline-flex items-center gap-1 text-xs font-semibold text-[#0B6B63]">
                        <Check className="h-3.5 w-3.5" />
                        Selected
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          </fieldset>

          <div>
            <label
              htmlFor="project-description"
              className="mb-2 flex items-center gap-2 text-sm font-semibold text-slate-900"
            >
              <FileText className="h-4 w-4 text-[#0B6B63]" />
              Project Description
              <span className="text-xs font-normal text-slate-500">
                (Optional)
              </span>
            </label>

            <textarea
              id="project-description"
              rows={4}
              disabled={isLoading}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="Provide architecture context, SLA targets, or sprint objectives..."
              className="w-full resize-y rounded-lg border border-[#9ED4C8] bg-white px-4 py-3 text-sm text-slate-900 outline-none placeholder:text-slate-400 focus:border-[#0B6B63] focus:ring-2 focus:ring-[#0B6B63]/15 disabled:opacity-60"
            />
          </div>

          <div className="flex flex-col-reverse gap-3 border-t border-[#9ED4C8] pt-5 sm:flex-row sm:items-center sm:justify-between">
            <button
              type="button"
              onClick={() => onNavigate('projects')}
              disabled={isLoading}
              className="inline-flex min-h-11 items-center justify-center rounded-lg border border-[#9ED4C8] px-5 text-sm font-semibold text-slate-700 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-teal-700 focus:ring-offset-2 disabled:opacity-60"
            >
              Cancel
            </button>

            <button
              type="submit"
              disabled={isLoading || Boolean(successMsg)}
              className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-[#0B6B63] px-6 text-sm font-semibold text-white hover:bg-[#084F49] focus:outline-none focus:ring-2 focus:ring-teal-700 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isLoading ? (
                <>
                  <Loader2 className="h-4 w-4" />
                  Creating Project...
                </>
              ) : successMsg ? (
                <>
                  <Check className="h-4 w-4" />
                  Continuing to Step 2...
                </>
              ) : (
                <>
                  Next: Connect Repository
                  <ArrowRight className="h-4 w-4" />
                </>
              )}
            </button>
          </div>
        </form>
      </section>
    </main>
  );
};
