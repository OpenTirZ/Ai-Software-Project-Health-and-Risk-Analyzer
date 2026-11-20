import React, { useState, useEffect } from 'react';
import type { PageView, ReportItem } from '../types';
import { reportsData } from '../data/mockData';
import { reportApi, type ProjectResponse } from '../services/api';
import { Plus, Download, Eye, CheckCircle, Sparkles, X, AlertCircle } from 'lucide-react';

interface ReportsProps {
  selectedRepo: string;
  project?: ProjectResponse | null;
  onNavigate: (view: PageView) => void;
}

function escapePdf(str: string): string {
  return str.replace(/[\\()]/g, '\\$&');
}

function generatePDFBlob(report: ReportItem): Blob {
  const sanitize = (text: string) => escapePdf(text.replace(/[^\x20-\x7E]/g, ''));
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
    ...report.recommendations.map((rec, idx) => `0 -18 Td (${idx + 1}. ${sanitize(rec)}) Tj`),
    'ET',
  ].join('\n');

  const stream = lines;
  const streamLen = stream.length;

  const pdfParts = [
    '%PDF-1.4\n',
    '1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n',
    '2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n',
    '3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n',
    '4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n',
    `5 0 obj\n<< /Length ${streamLen} >>\nstream\n${stream}\nendstream\nendobj\n`,
  ];

  let offset = 0;
  const offsets: number[] = [0];
  for (let i = 0; i < pdfParts.length; i++) {
    if (i > 0) offsets.push(offset);
    offset += pdfParts[i].length;
  }

  let xref = 'xref\n0 6\n0000000000 65535 f \n';
  for (let i = 1; i <= 5; i++) {
    xref += String(offsets[i]).padStart(10, '0') + ' 00000 n \n';
  }

  const trailer = `trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n${offset}\n%%EOF`;
  const fullPdf = pdfParts.join('') + xref + trailer;

  return new Blob([fullPdf], { type: 'application/pdf' });
}

export const Reports: React.FC<ReportsProps> = ({ selectedRepo, project }) => {
  const [reports, setReports] = useState<ReportItem[]>(reportsData);
  const [selectedReport, setSelectedReport] = useState<ReportItem>(reportsData[0]);
  const [showViewModal, setShowViewModal] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  useEffect(() => {
    if (project?.id) {
      reportApi.getReports(project.id).then((fetched) => {
        if (fetched.length > 0) {
          setReports(fetched);
          setSelectedReport(fetched[0]);
        }
      });
    }
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
        // Fallback for simulation when project ID is not set
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
    } catch (err: any) {
      setApiError(err.message || 'Failed to generate report from backend.');
    } finally {
      setGenerating(false);
    }
  };

  const handleDownloadPDF = (reportToDownload?: ReportItem) => {
    const target = reportToDownload || selectedReport;
    const blob = generatePDFBlob(target);
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    const cleanName = (target.project || selectedRepo).replace(/[^a-zA-Z0-9_-]/g, '_');
    link.setAttribute('download', `${cleanName}_health_report.pdf`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="p-6 md:p-8 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold text-slate-900 tracking-tight">
            Reports
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Generate and review project health reports for <span className="font-semibold text-slate-700">{selectedRepo}</span>.
          </p>
        </div>

        {/* Generate Report Button */}
        <button
          onClick={handleGenerateReport}
          disabled={generating}
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-white text-xs font-bold shadow-md shadow-indigo-600/25 transition-all hover:opacity-95 active:scale-95 cursor-pointer disabled:opacity-50"
          style={{
            background: 'linear-gradient(90deg, rgba(0, 0, 0, 0.2) 0%, rgba(0, 0, 0, 0.2) 100%), linear-gradient(90deg, rgb(99, 102, 241) 0%, rgb(168, 85, 247) 100%)',
          }}
        >
          {generating ? (
            <>
              <Sparkles className="w-4 h-4 animate-spin" />
              <span>Analyzing & Generating...</span>
            </>
          ) : (
            <>
              <Plus className="w-4 h-4" />
              <span>+ Generate Report</span>
            </>
          )}
        </button>
      </div>

      {/* Error Alert */}
      {apiError && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-sm flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-5 h-5 text-rose-500 shrink-0" />
            <div>
              <p className="font-semibold text-xs text-rose-900">Report generation failed</p>
              <p className="text-xs text-rose-700">{apiError}</p>
            </div>
          </div>
          <button
            onClick={handleGenerateReport}
            className="px-3 py-1.5 bg-rose-600 hover:bg-rose-700 text-white font-semibold text-xs rounded-lg transition-colors cursor-pointer shrink-0"
          >
            Retry
          </button>
        </div>
      )}

      {/* Reports List */}
      <div className="space-y-6">
        {reports.map((report) => (
          <div
            key={report.id}
            className="bg-white rounded-2xl p-6 md:p-8 border border-slate-200/90 shadow-sm space-y-6 hover:border-slate-300 transition-all"
          >
            {/* Report Header Title */}
            <div className="border-b border-slate-100 pb-4 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div>
                <h2 className="text-xl font-bold text-slate-900 tracking-tight">
                  {report.title}
                </h2>
                <p className="text-sm font-semibold text-slate-600 mt-0.5">
                  {report.project}
                </p>
                <p className="text-xs text-slate-400 mt-0.5">
                  Generated on {report.generatedDate}
                </p>
              </div>

              <div className="flex items-center gap-2">
                <span className="px-3 py-1 rounded-full text-xs font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                  Health: {report.healthScore}/100
                </span>
              </div>
            </div>

            {/* Metrics Snapshot */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="p-4 rounded-xl bg-slate-50 border border-slate-100">
                <p className="text-xs font-semibold text-slate-500 uppercase">
                  Project Health
                </p>
                <p className="text-2xl font-bold text-slate-900 mt-1">
                  {report.healthScore}%
                </p>
                <p className="text-xs text-emerald-600 mt-0.5">
                  Automated telemetry evaluation
                </p>
              </div>

              <div className="p-4 rounded-xl bg-slate-50 border border-slate-100">
                <p className="text-xs font-semibold text-slate-500 uppercase">
                  Flagged Risks
                </p>
                <p className="text-2xl font-bold text-slate-900 mt-1">
                  {report.risksCount}
                </p>
                <p className="text-xs text-amber-600 mt-0.5">
                  Active threshold warnings
                </p>
              </div>

              <div className="p-4 rounded-xl bg-slate-50 border border-slate-100">
                <p className="text-xs font-semibold text-slate-500 uppercase">
                  Bottlenecks
                </p>
                <p className="text-2xl font-bold text-slate-900 mt-1">
                  {report.bottlenecksCount}
                </p>
                <p className="text-xs text-blue-600 mt-0.5">
                  Aging pull request queues
                </p>
              </div>
            </div>

            {/* Key Recommendations */}
            <div>
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3">
                Key Actionable Recommendations
              </h3>
              <div className="space-y-2">
                {report.recommendations.map((rec, i) => (
                  <div
                    key={i}
                    className="flex items-start gap-2.5 text-xs text-slate-700 bg-slate-50/70 p-3 rounded-xl border border-slate-100"
                  >
                    <CheckCircle className="w-4 h-4 text-emerald-500 shrink-0 mt-0.5" />
                    <span>{rec}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Actions */}
            <div className="pt-4 border-t border-slate-100 flex items-center justify-end gap-3">
              <button
                onClick={() => {
                  setSelectedReport(report);
                  setShowViewModal(true);
                }}
                className="px-5 py-2 rounded-xl border border-blue-300 text-blue-600 hover:bg-blue-50 text-xs font-bold transition-colors flex items-center gap-1.5 cursor-pointer"
              >
                <Eye className="w-3.5 h-3.5" />
                <span>View Report</span>
              </button>

              <button
                onClick={() => handleDownloadPDF(report)}
                className="px-5 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold transition-colors flex items-center gap-1.5 cursor-pointer shadow-sm shadow-blue-500/20"
              >
                <Download className="w-3.5 h-3.5" />
                <span>Download PDF</span>
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Report Details Modal */}
      {showViewModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-2xl w-full p-6 md:p-8 shadow-2xl border border-slate-200 max-h-[90vh] overflow-y-auto space-y-6">
            <div className="flex items-center justify-between border-b border-slate-100 pb-4">
              <div>
                <h3 className="text-xl font-bold text-slate-900">
                  {selectedReport.title}
                </h3>
                <p className="text-xs text-slate-500 mt-1">
                  Target: {selectedReport.project} • {selectedReport.generatedDate}
                </p>
              </div>
              <button
                onClick={() => setShowViewModal(false)}
                className="text-slate-400 hover:text-slate-600 p-1 cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="grid grid-cols-3 gap-4">
              <div className="p-3 bg-slate-50 rounded-lg text-center">
                <span className="text-xs text-slate-500">Health</span>
                <p className="text-2xl font-bold text-emerald-600">{selectedReport.healthScore}</p>
              </div>
              <div className="p-3 bg-slate-50 rounded-lg text-center">
                <span className="text-xs text-slate-500">Risks</span>
                <p className="text-2xl font-bold text-amber-600">{selectedReport.risksCount}</p>
              </div>
              <div className="p-3 bg-slate-50 rounded-lg text-center">
                <span className="text-xs text-slate-500">Bottlenecks</span>
                <p className="text-2xl font-bold text-blue-600">{selectedReport.bottlenecksCount}</p>
              </div>
            </div>

            <div className="space-y-3">
              <h4 className="text-sm font-bold text-slate-800">Executive Summary</h4>
              <p className="text-xs text-slate-600 leading-relaxed">
                The software project evaluated meets the enterprise reliability criteria. No blocker regressions were detected across the master pipeline. Key improvement opportunities center around pull request aging velocity.
              </p>
            </div>

            <div className="space-y-3">
              <h4 className="text-sm font-bold text-slate-800">Actionable Checklist</h4>
              <ul className="text-xs text-slate-600 space-y-2">
                {selectedReport.recommendations.map((r, i) => (
                  <li key={i} className="flex items-center gap-2 p-2 rounded bg-slate-50 border border-slate-100">
                    <CheckCircle className="w-4 h-4 text-emerald-500 shrink-0" />
                    <span>{r}</span>
                  </li>
                ))}
              </ul>
            </div>

            <div className="flex justify-end gap-3 pt-4 border-t border-slate-100">
              <button
                onClick={() => setShowViewModal(false)}
                className="px-5 py-2 rounded-xl border border-slate-300 text-slate-700 text-xs font-semibold hover:bg-slate-50 cursor-pointer"
              >
                Close
              </button>
              <button
                onClick={() => handleDownloadPDF(selectedReport)}
                className="px-5 py-2 rounded-xl bg-blue-600 text-white text-xs font-semibold hover:bg-blue-700 flex items-center gap-1.5 cursor-pointer"
              >
                <Download className="w-3.5 h-3.5" />
                <span>Export PDF</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
