
import React, { useState, useEffect } from 'react';
import type { PageView, ReportItem } from '../types';
import { reportsData } from '../data/mockData';
import { reportApi, type ProjectResponse } from '../services/api';
import {
  Plus,
  Download,
  Eye,
  CheckCircle,
  X,
  AlertCircle,
  FileText,
} from 'lucide-react';

interface ReportsProps {
  selectedRepo: string;
  project?: ProjectResponse | null;
  onNavigate: (view: PageView) => void;
}

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

  const streamLen = streamLength(lines);

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

function streamLength(value: string): number {
  return new TextEncoder().encode(value).length;
}

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

  const handleDownloadPDF = (reportToDownload?: ReportItem) => {
    const target = reportToDownload || selectedReport;
    if (!target) return;

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
  };

  const healthColor = (score: number) => {
    if (score < 50) return 'text-[#CC1F2E]';
    if (score < 75) return 'text-[#B45309]';
    return 'text-[#0B6B63]';
  };

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-5 md:p-8">
      {/* Header */}
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
          className="inline-flex items-center gap-2 rounded-lg bg-[#0B6B63] px-5 py-2.5 text-sm font-semibold text-white hover:bg-[#084F49] disabled:cursor-not-allowed disabled:opacity-60 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0B6B63]"
        >
          <Plus className="h-4 w-4" />
          {generating ? 'Generating Report...' : 'Generate Report'}
        </button>
      </div>

      {/* Error */}
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
              <p className="mt-1 text-sm text-[#A3151F]">{apiError}</p>
            </div>
          </div>

          <button
            onClick={handleGenerateReport}
            disabled={generating}
            className="shrink-0 rounded-lg bg-[#CC1F2E] px-3 py-2 text-xs font-semibold text-white hover:bg-[#A3151F] disabled:opacity-60"
          >
            Retry
          </button>
        </div>
      )}

      {/* Reports */}
      {reports.length === 0 ? (
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
              {/* Report heading */}
              <div className="flex flex-col justify-between gap-3 border-b border-[#9ED4C8] pb-4 sm:flex-row sm:items-start">
                <div>
                  <h2 className="text-lg font-bold tracking-tight text-[#0E2A2A]">
                    {report.title}
                  </h2>
                  <p className="mt-1 text-sm font-semibold text-[#2B4745]">
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

              {/* Metrics */}
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
                      <span className="text-sm leading-5 text-[#2B4745]">
                        {rec}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Actions */}
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
                  className="inline-flex items-center gap-2 rounded-lg bg-[#0B6B63] px-4 py-2 text-sm font-semibold text-white hover:bg-[#084F49] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0B6B63]"
                >
                  <Download className="h-4 w-4" />
                  Download PDF
                </button>
              </div>
            </article>
          ))}
        </div>
      )}

      {/* Report details modal */}
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
                    <span className="text-sm leading-5 text-[#2B4745]">
                      {recommendation}
                    </span>
                  </li>
                ))}
              </ul>
            </div>

            <div className="flex flex-wrap justify-end gap-2 border-t border-[#9ED4C8] pt-4">
              <button
                onClick={() => setShowViewModal(false)}
                className="rounded-lg border border-[#9ED4C8] bg-white px-4 py-2 text-sm font-semibold text-[#2B4745] hover:bg-[#EAF8F3]"
              >
                Close
              </button>

              <button
                onClick={() => handleDownloadPDF(selectedReport)}
                className="inline-flex items-center gap-2 rounded-lg bg-[#0B6B63] px-4 py-2 text-sm font-semibold text-white hover:bg-[#084F49]"
              >
                <Download className="h-4 w-4" />
                Export PDF
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
