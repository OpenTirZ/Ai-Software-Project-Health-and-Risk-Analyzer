import React, { useState, useEffect, useCallback } from 'react';
import type { PageView } from '../types';
import type { ProjectResponse } from '../services/api';
import {
  metricsApi,
  appealApi,
  type HealthSummaryData,
  type Appeal,
} from '../services/api';
import {
  Flag,
  Send,
  CheckCircle2,
  XCircle,
  Clock,
  AlertTriangle,
  MessageSquareWarning,
  ChevronDown,
  ChevronUp,
  Loader2,
} from 'lucide-react';

interface AppealsProps {
  project: ProjectResponse;
  onNavigate: (view: PageView) => void;
}

type SeverityColor = { bg: string; text: string; border: string; dot: string };

const severityColors: Record<string, SeverityColor> = {
  HIGH: { bg: 'bg-red-50', text: 'text-red-700', border: 'border-red-200', dot: 'bg-red-500' },
  MEDIUM: { bg: 'bg-amber-50', text: 'text-amber-700', border: 'border-amber-200', dot: 'bg-amber-500' },
  LOW: { bg: 'bg-blue-50', text: 'text-blue-700', border: 'border-blue-200', dot: 'bg-blue-500' },
};

const statusConfig: Record<
  Appeal['status'],
  { icon: React.ElementType; label: string; badge: string }
> = {
  pending: { icon: Clock, label: 'Pending Review', badge: 'bg-amber-100 text-amber-700' },
  approved: { icon: CheckCircle2, label: 'Approved', badge: 'bg-emerald-100 text-emerald-700' },
  rejected: { icon: XCircle, label: 'Rejected', badge: 'bg-red-100 text-red-700' },
};

export const Appeals: React.FC<AppealsProps> = ({ project, onNavigate: _onNavigate }) => {
  const [flags, setFlags] = useState<HealthSummaryData['active_flags']>([]);
  const [appeals, setAppeals] = useState<Appeal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Appeal form state
  const [openFlagId, setOpenFlagId] = useState<string | null>(null);
  const [reason, setReason] = useState('');
  const [submitting, setSubmitting] = useState(false);

  // Review form state (for project_manager / admin)
  const [reviewingId, setReviewingId] = useState<string | null>(null);
  const [reviewComment, setReviewComment] = useState('');
  const [reviewSubmitting, setReviewSubmitting] = useState(false);

  const currentUser = (() => {
    try {
      const saved = localStorage.getItem('aegis_user');
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  })();

  const isReviewer =
    currentUser?.role === 'project_manager' || currentUser?.role === 'admin';

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [healthData, appealData] = await Promise.all([
        metricsApi.getHealthSummary(project.id),
        appealApi.getAppeals(project.id),
      ]);
      setFlags(healthData.active_flags || []);
      setAppeals(Array.isArray(appealData) ? appealData : []);
    } catch (err: any) {
      setError(err.message || 'Failed to load data');
    } finally {
      setLoading(false);
    }
  }, [project.id]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const handleSubmitAppeal = async (flag: HealthSummaryData['active_flags'][0]) => {
    if (!reason.trim()) return;
    setSubmitting(true);
    try {
      const newAppeal = await appealApi.submitAppeal(project.id, {
        flag_id: flag.id,
        flag_type: flag.type,
        flag_message: flag.message,
        reason: reason.trim(),
      });
      setAppeals((prev) => [newAppeal, ...prev]);
      setReason('');
      setOpenFlagId(null);
    } catch (err: any) {
      setError(err.message || 'Failed to submit appeal');
    } finally {
      setSubmitting(false);
    }
  };

  const handleReview = async (appealId: string, decision: 'approved' | 'rejected') => {
    setReviewSubmitting(true);
    try {
      const updated = await appealApi.reviewAppeal(project.id, appealId, {
        status: decision,
        review_comment: reviewComment.trim() || undefined,
      });
      setAppeals((prev) =>
        prev.map((a) => (a.id === appealId ? { ...a, ...updated } : a))
      );
      setReviewingId(null);
      setReviewComment('');
    } catch (err: any) {
      setError(err.message || 'Failed to review appeal');
    } finally {
      setReviewSubmitting(false);
    }
  };

  const appealedFlagIds = new Set(appeals.map((a) => a.flag_id));

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-[#0B6B63]" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl space-y-8 p-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#EAF8F3]">
            <MessageSquareWarning className="h-5 w-5 text-[#0B6B63]" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Developer Appeals</h1>
            <p className="text-sm text-slate-500">
              {project.name} · Review flags and submit clarifications
            </p>
          </div>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          <AlertTriangle className="mr-2 inline-block h-4 w-4" />
          {error}
          <button
            onClick={() => setError(null)}
            className="ml-3 font-medium underline hover:no-underline"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Active Flags Section */}
      <section>
        <h2 className="mb-4 text-lg font-semibold text-slate-800">Active Health Flags</h2>
        {flags.length === 0 ? (
          <div className="rounded-xl border border-[#9ED4C8] bg-[#EAF8F3] p-6 text-center">
            <CheckCircle2 className="mx-auto mb-2 h-8 w-8 text-[#0B6B63]" />
            <p className="font-medium text-[#0B6B63]">No active flags</p>
            <p className="mt-1 text-sm text-slate-500">
              All health indicators are within normal thresholds.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {flags.map((flag) => {
              const sc = severityColors[flag.severity?.toUpperCase()] || severityColors.LOW;
              const isOpen = openFlagId === flag.id;
              const alreadyAppealed = appealedFlagIds.has(flag.id);

              return (
                <div
                  key={flag.id}
                  className={`rounded-xl border ${sc.border} bg-white overflow-hidden`}
                >
                  <div className="flex items-start gap-4 p-4">
                    <div className={`mt-0.5 h-2.5 w-2.5 shrink-0 rounded-full ${sc.dot}`} />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className={`rounded px-2 py-0.5 text-[11px] font-semibold ${sc.bg} ${sc.text}`}>
                          {flag.severity?.toUpperCase() || 'FLAG'}
                        </span>
                        <span className="text-xs text-slate-400">{flag.type}</span>
                      </div>
                      <p className="mt-1 text-sm text-slate-700">{flag.message}</p>
                    </div>
                    <div className="shrink-0">
                      {alreadyAppealed ? (
                        <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-500">
                          Appealed
                        </span>
                      ) : (
                        <button
                          onClick={() => setOpenFlagId(isOpen ? null : flag.id)}
                          className="flex items-center gap-1 rounded-lg border border-[#9ED4C8] bg-[#EAF8F3] px-3 py-1.5 text-xs font-medium text-[#0B6B63] hover:bg-[#CDEFE6] transition-colors"
                        >
                          <Flag className="h-3 w-3" />
                          Appeal
                          {isOpen ? (
                            <ChevronUp className="h-3 w-3" />
                          ) : (
                            <ChevronDown className="h-3 w-3" />
                          )}
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Inline appeal form */}
                  {isOpen && !alreadyAppealed && (
                    <div className="border-t border-slate-100 bg-slate-50 p-4">
                      <label className="mb-1.5 block text-xs font-medium text-slate-600">
                        Why should this flag be reconsidered?
                      </label>
                      <textarea
                        rows={3}
                        value={reason}
                        onChange={(e) => setReason(e.target.value)}
                        placeholder="Provide context, supporting evidence, or clarification..."
                        className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 placeholder:text-slate-400 focus:border-[#0B6B63] focus:outline-none focus:ring-1 focus:ring-[#0B6B63]"
                      />
                      <div className="mt-3 flex justify-end gap-2">
                        <button
                          onClick={() => {
                            setOpenFlagId(null);
                            setReason('');
                          }}
                          className="rounded-lg px-4 py-1.5 text-xs font-medium text-slate-500 hover:bg-slate-100"
                        >
                          Cancel
                        </button>
                        <button
                          disabled={!reason.trim() || submitting}
                          onClick={() => handleSubmitAppeal(flag)}
                          className="flex items-center gap-1.5 rounded-lg bg-[#0B6B63] px-4 py-1.5 text-xs font-semibold text-white hover:bg-[#095c55] disabled:opacity-50 transition-colors"
                        >
                          {submitting ? (
                            <Loader2 className="h-3 w-3 animate-spin" />
                          ) : (
                            <Send className="h-3 w-3" />
                          )}
                          Submit Appeal
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* Appeals History */}
      <section>
        <h2 className="mb-4 text-lg font-semibold text-slate-800">
          Appeals History
          {appeals.length > 0 && (
            <span className="ml-2 rounded-full bg-slate-100 px-2 py-0.5 text-xs font-normal text-slate-500">
              {appeals.length}
            </span>
          )}
        </h2>
        {appeals.length === 0 ? (
          <div className="rounded-xl border border-slate-200 bg-white p-8 text-center">
            <MessageSquareWarning className="mx-auto mb-2 h-8 w-8 text-slate-300" />
            <p className="text-sm text-slate-500">No appeals have been submitted yet.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {appeals.map((appeal) => {
              const cfg = statusConfig[appeal.status];
              const StatusIcon = cfg.icon;
              const isReviewOpen = reviewingId === appeal.id;

              return (
                <div
                  key={appeal.id}
                  className="rounded-xl border border-slate-200 bg-white overflow-hidden"
                >
                  <div className="p-4">
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span
                            className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${cfg.badge}`}
                          >
                            <StatusIcon className="h-3 w-3" />
                            {cfg.label}
                          </span>
                          <span className="text-xs text-slate-400">{appeal.flag_type}</span>
                        </div>
                        <p className="mt-2 text-sm font-medium text-slate-700">
                          {appeal.flag_message}
                        </p>
                        <div className="mt-2 rounded-lg bg-slate-50 p-3">
                          <p className="text-xs font-medium text-slate-500">Reason for appeal:</p>
                          <p className="mt-1 text-sm text-slate-600">{appeal.reason}</p>
                        </div>
                        <p className="mt-2 text-xs text-slate-400">
                          Submitted{' '}
                          {appeal.submitted_at
                            ? new Date(appeal.submitted_at).toLocaleDateString('en-US', {
                                month: 'short',
                                day: 'numeric',
                                year: 'numeric',
                                hour: '2-digit',
                                minute: '2-digit',
                              })
                            : 'recently'}
                        </p>
                        {appeal.review_comment && (
                          <div className="mt-2 rounded-lg border border-slate-100 bg-slate-50 p-3">
                            <p className="text-xs font-medium text-slate-500">Reviewer comment:</p>
                            <p className="mt-1 text-sm text-slate-600">{appeal.review_comment}</p>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Reviewer actions */}
                    {isReviewer && appeal.status === 'pending' && (
                      <div className="mt-4 border-t border-slate-100 pt-4">
                        {!isReviewOpen ? (
                          <button
                            onClick={() => setReviewingId(appeal.id)}
                            className="text-xs font-medium text-[#0B6B63] hover:underline"
                          >
                            Review this appeal →
                          </button>
                        ) : (
                          <div className="space-y-3">
                            <textarea
                              rows={2}
                              value={reviewComment}
                              onChange={(e) => setReviewComment(e.target.value)}
                              placeholder="Add a review comment (optional)..."
                              className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 placeholder:text-slate-400 focus:border-[#0B6B63] focus:outline-none focus:ring-1 focus:ring-[#0B6B63]"
                            />
                            <div className="flex gap-2">
                              <button
                                disabled={reviewSubmitting}
                                onClick={() => handleReview(appeal.id, 'approved')}
                                className="flex items-center gap-1 rounded-lg bg-emerald-600 px-4 py-1.5 text-xs font-semibold text-white hover:bg-emerald-700 disabled:opacity-50 transition-colors"
                              >
                                {reviewSubmitting ? (
                                  <Loader2 className="h-3 w-3 animate-spin" />
                                ) : (
                                  <CheckCircle2 className="h-3 w-3" />
                                )}
                                Approve
                              </button>
                              <button
                                disabled={reviewSubmitting}
                                onClick={() => handleReview(appeal.id, 'rejected')}
                                className="flex items-center gap-1 rounded-lg bg-red-600 px-4 py-1.5 text-xs font-semibold text-white hover:bg-red-700 disabled:opacity-50 transition-colors"
                              >
                                {reviewSubmitting ? (
                                  <Loader2 className="h-3 w-3 animate-spin" />
                                ) : (
                                  <XCircle className="h-3 w-3" />
                                )}
                                Reject
                              </button>
                              <button
                                onClick={() => {
                                  setReviewingId(null);
                                  setReviewComment('');
                                }}
                                className="rounded-lg px-4 py-1.5 text-xs font-medium text-slate-500 hover:bg-slate-100"
                              >
                                Cancel
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
};

export default Appeals;
