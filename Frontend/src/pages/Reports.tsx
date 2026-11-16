import React, { useState } from 'react';
import type { PageView } from '../types';
import { reportsData } from '../data/mockData';
import { Plus, Download, Eye, CheckCircle, Sparkles, X } from 'lucide-react';

interface ReportsProps {
  selectedRepo: string;
  onNavigate: (view: PageView) => void;
}

export const Reports: React.FC<ReportsProps> = ({ selectedRepo }) => {
  const [reports, setReports] = useState(reportsData);
  const [selectedReport, setSelectedReport] = useState(reportsData[0]);
  const [showViewModal, setShowViewModal] = useState(false);
  const [generating, setGenerating] = useState(false);

  const handleGenerateReport = () => {
    setGenerating(true);
    setTimeout(() => {
      const newReport = {
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
      setReports([newReport, ...reports]);
      setSelectedReport(newReport);
      setGenerating(false);
    }, 900);
  };

  const handleDownloadPDF = () => {
    window.print();
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
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-white text-xs font-bold shadow-md shadow-indigo-600/25 transition-all hover:opacity-95 active:scale-95 cursor-pointer"
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
                  Generated: {report.generatedDate}
                </p>
              </div>
              <span className="self-start sm:self-auto px-3 py-1 rounded-full text-xs font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                Verified Audit
              </span>
            </div>

            {/* 3 Metric Summary Boxes */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {/* HEALTH */}
              <div className="bg-slate-50/80 rounded-xl p-4 border border-slate-200/70 text-center">
                <p className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                  HEALTH
                </p>
                <p className="text-3xl font-extrabold text-emerald-600 mt-1">
                  {report.healthScore}
                </p>
              </div>

              {/* RISKS */}
              <div className="bg-slate-50/80 rounded-xl p-4 border border-slate-200/70 text-center">
                <p className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                  RISKS
                </p>
                <p className="text-3xl font-extrabold text-amber-500 mt-1">
                  {report.risksCount}
                </p>
              </div>

              {/* BOTTLENECKS */}
              <div className="bg-slate-50/80 rounded-xl p-4 border border-slate-200/70 text-center">
                <p className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                  BOTTLENECKS
                </p>
                <p className="text-3xl font-extrabold text-blue-600 mt-1">
                  {report.bottlenecksCount}
                </p>
              </div>
            </div>

            {/* Key Recommendations */}
            <div className="bg-slate-50/50 p-5 rounded-xl border border-slate-100">
              <h3 className="text-sm font-bold text-slate-900 mb-2.5">
                Key Recommendations
              </h3>
              <ul className="space-y-2 text-sm text-slate-700">
                {report.recommendations.map((rec, i) => (
                  <li key={i} className="flex items-start gap-2">
                    <span className="text-indigo-600 font-bold">•</span>
                    <span>{rec}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Actions */}
            <div className="flex items-center justify-end gap-3 pt-2">
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
                onClick={handleDownloadPDF}
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
                onClick={handleDownloadPDF}
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
