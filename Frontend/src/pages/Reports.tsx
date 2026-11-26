import React, { useState, useEffect } from 'react';
import type { PageView, ReportItem } from '../types';
import { reportsData } from '../data/mockData';
import { reportApi, metricsApi, type ProjectResponse, type HealthSummaryData } from '../services/api';
import {
  reportService,
  type Recommendation,
  type EnrichedReport,
} from '../services/reportService';
import { ExplanationDrawer } from '../components/reports/ExplanationDrawer';
import { RecommendationCards } from '../components/reports/RecommendationCard';
import {
  Plus,
  Download,
  Eye,
  CheckCircle,
  X,
  AlertCircle,
  FileText,
  Info,
  Loader2,
  ShieldAlert,
} from 'lucide-react';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface ReportsProps {
  selectedRepo: string;
  project?: ProjectResponse | null;
  onNavigate: (view: PageView) => void;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function escapePdf(str: string): string {
  return str.replace(/[\\()]/g, '\\$&');
}

function generatePDFBlob(report: ReportItem): Blob {
  const sanitize = (text: string) =>
    escapePdf(text.replace(/[^\x20-\x7E]/g, ''));

  const lines = [
    'BT',
    '/F1 20 Tf',
    `50 740 Td (${sanitize(report.title)}) Tj`,
    '/F1 12 Tf',
    `0 -28 Td (Project: ${sanitize(report.project)}) Tj`,
    `0 -18 Td (Generated: ${sanitize(report.generatedDate)}) Tj`,
    `0 -18 Td (Overall Health Score: ${report.healthScore} / 100) Tj`,
    `0 -18 Td (Active Risks Detected: ${report.risksCount}  |  Potential Bottlenecks: ${report.bottlenecksCount}) Tj`,
    '0 -30 Td (Recommended Actions:) Tj',
    ...report.recommendations.map(
      (rec, idx) => `0 -18 Td (${idx + 1}. ${sanitize(rec)}) Tj`,
    ),
    'ET',
  ].join('\n');

  const streamLen = new TextEncoder().encode(lines).length;

  const pdfParts = [
    '%PDF-1.4\n',
    '1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n',
    '2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n',
    '3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n',
    '4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n',
    `5 0 obj\n<< /Length ${streamLen} >>\nstream\n${lines}\nendstream\nendobj\n`,
  ];

  let offset = 0;
  const offsets: number[] = [0];

  for (let i = 0; i < pdfParts.length; i++) {
    if (i > 0) offsets.push(offset);
    offset += pdfParts[i].length;
  }

  let xref = 'xref\n0 6\n0000000000 65535 f \n';

  for (let i = 1; i <= 5; i++) {
    xref += `${String(offsets[i]).padStart(10, '0')} 00000 n \n`;
  }

  const trailer = `trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n${offset}\n%%EOF`;
  const fullPdf = pdfParts.join('') + xref + trailer;

  return new Blob([fullPdf], { type: 'application/pdf' });
}

const healthColor = (score: number) => {
  if (score < 50) return 'text-[#CC1F2E]';
  if (score < 75) return 'text-[#B45309]';
  return 'text-[#0B6B63]';
};

// ---------------------------------------------------------------------------
// Generation Skeleton
// ---------------------------------------------------------------------------
const GenerationSkeleton: React.FC = () => (
  <div className="space-y-5 animate-pulse">
    <div className="rounded-xl border border-[#9ED4C8] bg-white p-6">
      <div className="flex items-center gap-3 mb-4">
        <Loader2 className="h-5 w-5 animate-spin text-[#0B6B63]" />
        <span className="text-sm font-semibold text-[#0B6B63]">
          Generating Status Report…
        </span>
      </div>
      <div className="space-y-3">
        <div className="h-4 w-3/4 rounded bg-slate-100" />
        <div className="h-4 w-1/2 rounded bg-slate-100" />
        <div className="grid grid-cols-3 gap-3 mt-4">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-20 rounded-lg bg-slate-100" />
          ))}
        </div>
        <div className="mt-4 space-y-2">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-10 rounded-lg bg-slate-50" />
          ))}
        </div>
      </div>
    </div>
  </div>
);

// ---------------------------------------------------------------------------
// Reports Page
// ---------------------------------------------------------------------------

export const Reports: React.FC<ReportsProps> = ({
  selectedRepo,
  project,
}) => {
  const [reports, setReports] = useState<ReportItem[]>(reportsData);
  const [selectedReport, setSelectedReport] = useState<ReportItem>(
    reportsData[0],
  );
  const [showViewModal, setShowViewModal] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  // AI explanation drawer state
  const [drawerFlag, setDrawerFlag] = useState<{
    id: string;
    type: string;
    severity: string;
    message: string;
    evidence?: any;
  } | null>(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  // Flags + recommendations state
  const [healthFlags, setHealthFlags] = useState<HealthSummaryData | null>(null);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [loadingRecs, setLoadingRecs] = useState(false);
  const [recsError, setRecsError] = useState<string | null>(null);

  // PDF download state
  const [downloadingPdf, setDownloadingPdf] = useState<string | null>(null);

  // Load reports from API
  useEffect(() => {
    if (!project?.id) return;

    reportApi
      .getReports(project.id)
      .then((fetched) => {
        if (fetched.length > 0) {
          setReports(fetched);
          setSelectedReport(fetched[0]);
        }
      })
      .catch((err: unknown) => {
        setApiError(
          err instanceof Error
            ? err.message
            : 'Failed to load project reports.',
        );
      });
  }, [project?.id]);

  // Load flags + recommendations
  useEffect(() => {
    if (!project?.id) return;

    // Health flags for explanation drawer
    reportService
      .getHealthFlags(project.id)
      .then(setHealthFlags)
      .catch(() => {/* non-critical */});

    // Recommendations
    setLoadingRecs(true);
    setRecsError(null);
    reportService
      .getBreakdownWithRecommendations(project.id)
      .then(({ recommendations: recs }) => setRecommendations(recs))
      .catch((e) => setRecsError(e.message || 'Failed to load recommendations'))
      .finally(() => setLoadingRecs(false));
  }, [project?.id]);

  // Generate report
  const handleGenerateReport = async () => {
    setGenerating(true);
    setApiError(null);

    try {
      if (project?.id) {
        const generated = await reportApi.generateReport(project.id);
        setReports((prev) => [generated, ...prev]);
        setSelectedReport(generated);
      } else {
        const newReport: ReportItem = {
          id: Date.now().toString(),
          title: 'PROJECT HEALTH AUDIT REPORT',
          project: selectedRepo,
          generatedDate: new Date().toLocaleDateString('en-US', {
            month: 'short',
            day: '2-digit',
            year: 'numeric',
          }),
          healthScore: 84,
          risksCount: 2,
          bottlenecksCount: 2,
          recommendations: [
            'Immediate rebase on main branch recommended',
            'Automated CI build times stabilized under 4 minutes',
            'Zero critical CVEs discovered in container images',
          ],
        };

        setReports((prev) => [newReport, ...prev]);
        setSelectedReport(newReport);
      }
    } catch (err: unknown) {
      setApiError(
        err instanceof Error
          ? err.message
          : 'Failed to generate report from backend.',
      );
    } finally {
      setGenerating(false);
    }
  };

  // PDF download — try backend first, then client-side
  const handleDownloadPDF = async (reportToDownload?: ReportItem) => {
    const target = reportToDownload || selectedReport;
    if (!target) return;

    setDownloadingPdf(target.id);

    if (project?.id) {
      try {
        await reportService.downloadPDF(project.id, target.id, target);
        setDownloadingPdf(null);
        return;
      } catch {
        // Fall through to client-side
      }
    }

    // Client-side fallback
    const blob = generatePDFBlob(target);
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    const cleanName = (target.project || selectedRepo).replace(
      /[^a-zA-Z0-9_-]/g,
      '_',
    );
    link.setAttribute('download', `${cleanName}_health_report.pdf`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    setDownloadingPdf(null);
  };

  // Open explanation drawer for a flag
  const handleExplainFlag = (flag: {
    id: string;
    type: string;
    severity: string;
    message: string;
    evidence?: any;
  }) => {
    setDrawerFlag(flag);
    setIsDrawerOpen(true);
  };

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-5 md:p-8">

      {/* ─── Header ─── */}
      <div className="flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[#0E2A2A] md:text-3xl">
            Reports
          </h1>
          <p className="mt-1 text-sm text-[#3F5F5C]">
            Generate and review project health reports for{' '}
            <span className="font-semibold text-[#0E2A2A]">
              {selectedRepo}
            </span>
            .
          </p>
        </div>

        <button
          onClick={handleGenerateReport}
          disabled={generating}
          className="w-full sm:w-auto inline-flex items-center gap-2 rounded-lg bg-[#0B6B63] px-5 py-2.5 text-sm font-semibold text-white hover:bg-[#084F49] disabled:cursor-not-allowed disabled:opacity-60 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0B6B63]"
        >
          {generating ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Plus className="h-4 w-4" />
          )}
          {generating ? 'Generating Report…' : 'Generate Status Report'}
        </button>
      </div>

      {/* ─── Error banner ─── */}
      {apiError && (
        <div
          role="alert"
          className="flex flex-col justify-between gap-3 rounded-xl border border-[#CC1F2E]/20 bg-[#CC1F2E]/5 p-4 sm:flex-row sm:items-center"
        >
          <div className="flex items-start gap-3">
            <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-[#CC1F2E]" />
            <div>
              <p className="text-sm font-semibold text-[#CC1F2E]">
                Report operation failed
              </p>
              <p className="mt-1 text-sm text-[#CC1F2E]">{apiError}</p>
            </div>
          </div>

          <button
            onClick={handleGenerateReport}
            disabled={generating}
            className="shrink-0 rounded-lg bg-[#CC1F2E] px-3 py-2 text-xs font-semibold text-white hover:bg-[#CC1F2E] disabled:opacity-60"
          >
            Retry
          </button>
        </div>
      )}

      {/* ─── Generation skeleton ─── */}
      {generating && <GenerationSkeleton />}

      {/* ─── Active Flags (clickable for AI explanation) ─── */}
      {Array.isArray(healthFlags?.active_flags) && healthFlags.active_flags.length > 0 && !generating && (
        <section className="rounded-xl border border-[#9ED4C8] bg-white p-5">
          <div className="flex items-center gap-2 mb-3">
            <ShieldAlert className="h-5 w-5 text-[#CC1F2E]" />
            <h2 className="text-sm font-bold text-[#0E2A2A]">Active Risk Flags</h2>
            <span className="rounded-full bg-red-50 px-2 py-0.5 text-[11px] font-semibold text-red-700">
              {healthFlags.active_flags.length}
            </span>
            <span className="ml-auto text-[11px] text-slate-400">
              Click a flag for AI-powered explanation
            </span>
          </div>
          <div className="space-y-2">
            {healthFlags.active_flags.map((flag) => {
              const isHigh = flag.severity === 'high';
              const isMed = flag.severity === 'medium';
              return (
                <button
                  key={flag.id}
                  type="button"
                  onClick={() => handleExplainFlag(flag)}
                  className="flex w-full items-center gap-3 rounded-lg border px-4 py-3 text-left transition-colors hover:bg-slate-50"
                  style={{
                    borderColor: isHigh ? '#FECACA' : isMed ? '#FDE68A' : '#BBF7D0',
                    backgroundColor: isHigh ? '#FEF2F2' : isMed ? '#FFFBEB' : '#F0FDF4',
                  }}
                >
                  <Info className="h-4 w-4 shrink-0 text-slate-400" />
                  <div className="min-w-0 flex-1">
                    <span className="text-xs font-semibold text-slate-800 block truncate">
                      {flag.message}
                    </span>
                    <span className="text-[11px] text-slate-500">
                      {flag.type} · {flag.severity}
                    </span>
                  </div>
                  <span
                    className="shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold uppercase"
                    style={{
                      color: isHigh ? '#991B1B' : isMed ? '#92400E' : '#166534',
                      backgroundColor: isHigh ? '#FEE2E2' : isMed ? '#FEF3C7' : '#DCFCE7',
                    }}
                  >
                    Explain
                  </span>
                </button>
              );
            })}
          </div>
        </section>
      )}

      {/* ─── Advisory Recommendation Cards ─── */}
      {!generating && (
        <section className="rounded-xl border border-[#9ED4C8] bg-white p-5">
          <RecommendationCards
            recommendations={recommendations}
            isLoading={loadingRecs}
            error={recsError}
          />
        </section>
      )}

      {/* ─── Report list ─── */}
      {reports.length === 0 && !generating ? (
        <div className="rounded-xl border border-[#9ED4C8] bg-white px-6 py-14 text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-[#CDEFE6] text-[#0B6B63]">
            <FileText className="h-6 w-6" />
          </div>
          <h2 className="mt-4 text-base font-semibold text-[#0E2A2A]">
            No reports available
          </h2>
          <p className="mt-2 text-sm text-[#5F7C79]">
            Generate a project health report to get started.
          </p>
        </div>
      ) : (
        <div className="space-y-5">
          {reports.map((report) => (
            <article
              key={report.id}
              className="space-y-6 rounded-xl border border-[#9ED4C8] bg-white p-5 md:p-7"
            >

              <div className="flex flex-col justify-between gap-3 border-b border-[#9ED4C8] pb-4 sm:flex-row sm:items-start">
                <div>
                  <h2 className="text-lg font-bold tracking-tight text-[#0E2A2A]">
                    {report.title}
                  </h2>
                  <p className="mt-1 text-sm font-semibold text-[#3F5F5C]">
                    {report.project}
                  </p>
                  <p className="mt-1 text-xs text-[#5F7C79]">
                    Generated on {report.generatedDate}
                  </p>
                </div>

                <span className="inline-flex w-fit items-center rounded-md border border-[#9ED4C8] bg-[#CDEFE6] px-3 py-1.5 text-xs font-bold text-[#0B6B63]">
                  Health: {report.healthScore}/100
                </span>
              </div>

              {/* Stats cards */}
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                <div className="rounded-lg border border-[#9ED4C8] bg-[#EAF8F3] p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-[#5F7C79]">
                    Project Health
                  </p>
                  <p
                    className={`mt-1 text-2xl font-bold tabular-nums ${healthColor(
                      report.healthScore,
                    )}`}
                  >
                    {report.healthScore}%
                  </p>
                  <p className="mt-1 text-xs text-[#5F7C79]">
                    Automated telemetry evaluation
                  </p>
                </div>

                <div className="rounded-lg border border-[#9ED4C8] bg-[#EAF8F3] p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-[#5F7C79]">
                    Flagged Risks
                  </p>
                  <p className="mt-1 text-2xl font-bold tabular-nums text-[#CC1F2E]">
                    {report.risksCount}
                  </p>
                  <p className="mt-1 text-xs text-[#5F7C79]">
                    Active threshold warnings
                  </p>
                </div>

                <div className="rounded-lg border border-[#9ED4C8] bg-[#EAF8F3] p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-[#5F7C79]">
                    Bottlenecks
                  </p>
                  <p className="mt-1 text-2xl font-bold tabular-nums text-[#B45309]">
                    {report.bottlenecksCount}
                  </p>
                  <p className="mt-1 text-xs text-[#5F7C79]">
                    Aging pull request queues
                  </p>
                </div>
              </div>

              {/* Executive summary */}
              <div>
                <h3 className="mb-2 text-xs font-bold uppercase tracking-wide text-[#3F5F5C]">
                  Executive Summary
                </h3>
                <p className="text-sm leading-6 text-[#3F5F5C]">
                  The software project evaluated meets the enterprise
                  reliability criteria. No blocker regressions were detected
                  across the master pipeline. Key improvement opportunities
                  center around pull request aging velocity and workload
                  distribution balance.
                </p>
              </div>

              {/* Recommendations */}
              <div>
                <h3 className="mb-3 text-xs font-bold uppercase tracking-wide text-[#3F5F5C]">
                  Key Actionable Recommendations
                </h3>

                <div className="space-y-2">
                  {report.recommendations.map((rec, index) => (
                    <div
                      key={index}
                      className="flex items-start gap-3 rounded-lg border border-[#9ED4C8] bg-white p-3"
                    >
                      <CheckCircle className="mt-0.5 h-4 w-4 shrink-0 text-[#0B6B63]" />
                      <span className="text-sm leading-5 text-[#3F5F5C]">
                        {rec}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Action buttons */}
              <div className="flex flex-wrap justify-end gap-2 border-t border-[#9ED4C8] pt-4">
                <button
                  onClick={() => {
                    setSelectedReport(report);
                    setShowViewModal(true);
                  }}
                  className="inline-flex items-center gap-2 rounded-lg border border-[#9ED4C8] bg-white px-4 py-2 text-sm font-semibold text-[#0B6B63] hover:bg-[#CDEFE6] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0B6B63]"
                >
                  <Eye className="h-4 w-4" />
                  View Report
                </button>

                <button
                  onClick={() => handleDownloadPDF(report)}
                  disabled={downloadingPdf === report.id}
                  className="inline-flex items-center gap-2 rounded-lg bg-[#0B6B63] px-4 py-2 text-sm font-semibold text-white hover:bg-[#084F49] disabled:opacity-60 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0B6B63]"
                >
                  {downloadingPdf === report.id ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Download className="h-4 w-4" />
                  )}
                  {downloadingPdf === report.id ? 'Downloading…' : 'Download PDF'}
                </button>
              </div>
            </article>
          ))}
        </div>
      )}

      {/* ─── View Report Modal ─── */}
      {showViewModal && selectedReport && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-[#0E2A2A]/60 p-4"
          onClick={() => setShowViewModal(false)}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="report-modal-title"
            className="max-h-[90vh] w-full max-w-2xl space-y-6 overflow-y-auto rounded-xl border border-[#9ED4C8] bg-white p-5 md:p-7"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-4 border-b border-[#9ED4C8] pb-4">
              <div>
                <h3
                  id="report-modal-title"
                  className="text-lg font-bold text-[#0E2A2A]"
                >
                  {selectedReport.title}
                </h3>
                <p className="mt-1 text-xs text-[#5F7C79]">
                  Target: {selectedReport.project} ·{' '}
                  {selectedReport.generatedDate}
                </p>
              </div>

              <button
                onClick={() => setShowViewModal(false)}
                aria-label="Close report details"
                className="rounded-md p-1.5 text-[#5F7C79] hover:bg-[#CDEFE6] hover:text-[#0B6B63] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0B6B63]"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div className="rounded-lg border border-[#9ED4C8] bg-[#EAF8F3] p-3 text-center">
                <span className="text-xs text-[#5F7C79]">Health</span>
                <p
                  className={`mt-1 text-2xl font-bold tabular-nums ${healthColor(
                    selectedReport.healthScore,
                  )}`}
                >
                  {selectedReport.healthScore}
                </p>
              </div>

              <div className="rounded-lg border border-[#9ED4C8] bg-[#EAF8F3] p-3 text-center">
                <span className="text-xs text-[#5F7C79]">Risks</span>
                <p className="mt-1 text-2xl font-bold tabular-nums text-[#CC1F2E]">
                  {selectedReport.risksCount}
                </p>
              </div>

              <div className="rounded-lg border border-[#9ED4C8] bg-[#EAF8F3] p-3 text-center">
                <span className="text-xs text-[#5F7C79]">Bottlenecks</span>
                <p className="mt-1 text-2xl font-bold tabular-nums text-[#B45309]">
                  {selectedReport.bottlenecksCount}
                </p>
              </div>
            </div>

            <div className="space-y-2">
              <h4 className="text-sm font-bold text-[#0E2A2A]">
                Executive Summary
              </h4>
              <p className="text-sm leading-6 text-[#3F5F5C]">
                The software project evaluated meets the enterprise
                reliability criteria. No blocker regressions were detected
                across the master pipeline. Key improvement opportunities
                center around pull request aging velocity.
              </p>
            </div>

            <div className="space-y-3">
              <h4 className="text-sm font-bold text-[#0E2A2A]">
                Actionable Checklist
              </h4>

              <ul className="space-y-2">
                {selectedReport.recommendations.map((recommendation, index) => (
                  <li
                    key={index}
                    className="flex items-start gap-2 rounded-lg border border-[#9ED4C8] bg-[#EAF8F3] p-3"
                  >
                    <CheckCircle className="mt-0.5 h-4 w-4 shrink-0 text-[#0B6B63]" />
                    <span className="text-sm leading-5 text-[#3F5F5C]">
                      {recommendation}
                    </span>
                  </li>
                ))}
              </ul>
            </div>

            <div className="flex flex-wrap justify-end gap-2 border-t border-[#9ED4C8] pt-4">
              <button
                onClick={() => setShowViewModal(false)}
                className="rounded-lg border border-[#9ED4C8] bg-white px-4 py-2 text-sm font-semibold text-[#3F5F5C] hover:bg-[#EAF8F3]"
              >
                Close
              </button>

              <button
                onClick={() => handleDownloadPDF(selectedReport)}
                disabled={downloadingPdf === selectedReport.id}
                className="inline-flex items-center gap-2 rounded-lg bg-[#0B6B63] px-4 py-2 text-sm font-semibold text-white hover:bg-[#084F49] disabled:opacity-60"
              >
                {downloadingPdf === selectedReport.id ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Download className="h-4 w-4" />
                )}
                Export PDF
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ─── AI Explanation Drawer ─── */}
      <ExplanationDrawer
        projectId={project?.id || ''}
        flag={drawerFlag}
        isOpen={isDrawerOpen}
        onClose={() => {
          setIsDrawerOpen(false);
          setDrawerFlag(null);
        }}
      />
    </div>
  );
};
