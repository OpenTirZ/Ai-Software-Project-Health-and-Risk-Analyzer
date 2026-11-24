import React, { useState, useEffect, useCallback } from 'react';
import { 
  Sparkles, 
  Download, 
  RefreshCw, 
  AlertTriangle, 
  TrendingUp, 
  ShieldCheck, 
  Clock, 
  FileText, 
  CheckCircle2, 
  Info,
  Calendar,
  Layers,
  ArrowRight
} from 'lucide-react';
import { reportService } from '../services/reportService';
import { ExplanationDrawer } from '../components/reports/ExplanationDrawer';
import { RecommendationCard } from '../components/reports/RecommendationCard';

/**
 * Report Generation View Component
 * Provides on-demand status report generation, multi-stage progress skeleton,
 * rendered executive summary, interactive AI Explanation Drawer on metric flags,
 * priority-tagged advisory recommendation cards, and backend PDF report download.
 */
export const Reports = ({ 
  projectId = 'proj_core_platform', 
  selectedRepo = 'core-api-service',
  onNavigate 
}) => {
  const [report, setReport] = useState(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generationStage, setGenerationStage] = useState(1);
  const [isDownloadingPdf, setIsDownloadingPdf] = useState(false);
  const [downloadSuccessMsg, setDownloadSuccessMsg] = useState(null);

  // AI Explanation Drawer State
  const [activeFlag, setActiveFlag] = useState(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  // Load initial report on mount or when repository changes
  const loadReport = useCallback(async (isInitial = false) => {
    if (!isInitial) {
      setIsGenerating(true);
      setGenerationStage(1);
    }

    try {
      if (!isInitial) {
        // Multi-stage visual skeleton progression
        await new Promise((res) => setTimeout(res, 350));
        setGenerationStage(2);
        await new Promise((res) => setTimeout(res, 400));
        setGenerationStage(3);
        await new Promise((res) => setTimeout(res, 350));
      }

      const generated = await reportService.generateReport(projectId, selectedRepo);
      setReport(generated);
    } catch (err) {
      console.error('[Reports] Failed to generate status report:', err);
    } finally {
      setIsGenerating(false);
      setGenerationStage(1);
    }
  }, [projectId, selectedRepo]);

  useEffect(() => {
    loadReport(true);
  }, [loadReport]);

  // Handle PDF Download from Backend
  const handleDownloadPdf = async () => {
    setIsDownloadingPdf(true);
    setDownloadSuccessMsg(null);
    try {
      const res = await reportService.downloadReportPdf(
        projectId, 
        selectedRepo, 
        report?.reportId || ''
      );
      setDownloadSuccessMsg(`Downloaded: ${res.filename}`);
      setTimeout(() => setDownloadSuccessMsg(null), 4000);
    } catch (err) {
      console.error('[Reports] Error downloading PDF report:', err);
    } finally {
      setIsDownloadingPdf(false);
    }
  };

  const handleOpenFlagExplanation = (flag) => {
    setActiveFlag(flag);
    setIsDrawerOpen(true);
  };

  const overallHealth = report?.overallHealth || { score: 82, status: 'Healthy', color: '#10b981' };

  return (
    <div className="p-6 md:p-8 max-w-7xl mx-auto space-y-8">
      {/* Top Action Header */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 pb-2 border-b border-slate-100">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-indigo-50 text-indigo-700 border border-indigo-100">
              AUDIT & GOVERNANCE
            </span>
            <span className="text-xs text-slate-400 font-mono">
              Target: <strong className="text-slate-700">{selectedRepo}</strong>
            </span>
          </div>
          <h1 className="text-2xl md:text-3xl font-extrabold text-slate-900 tracking-tight">
            Status Reports & AI Advisory
          </h1>
          <p className="text-sm text-slate-500 mt-0.5">
            On-demand executive audits, explainable metric flags, and actionable mitigation roadmaps.
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-3 flex-wrap">
          {/* PDF Download Button */}
          <button
            onClick={handleDownloadPdf}
            disabled={isDownloadingPdf || isGenerating}
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 text-xs font-bold transition-all shadow-xs disabled:opacity-50 cursor-pointer"
            title="Download executive audit report in PDF format"
          >
            {isDownloadingPdf ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin text-indigo-600" />
                <span>Downloading PDF...</span>
              </>
            ) : (
              <>
                <Download className="w-4 h-4 text-slate-600" />
                <span>Download PDF Report</span>
              </>
            )}
          </button>

          {/* On-Demand Generate Status Report Button */}
          <button
            onClick={() => loadReport(false)}
            disabled={isGenerating}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-white text-xs font-bold transition-all shadow-md shadow-indigo-500/25 hover:opacity-95 active:scale-98 disabled:opacity-60 cursor-pointer"
            style={{
              background: 'linear-gradient(90deg, rgba(0, 0, 0, 0.2) 0%, rgba(0, 0, 0, 0.2) 100%), linear-gradient(90deg, rgb(99, 102, 241) 0%, rgb(168, 85, 247) 100%)',
            }}
          >
            {isGenerating ? (
              <>
                <Sparkles className="w-4 h-4 animate-spin" />
                <span>Generating Status Report...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" />
                <span>Generate Status Report</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Success Notification Pill */}
      {downloadSuccessMsg && (
        <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl flex items-center justify-between text-xs text-emerald-800 font-semibold animate-in fade-in duration-200">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
            <span>{downloadSuccessMsg}</span>
          </div>
          <span className="text-[11px] text-emerald-600">Saved to default downloads</span>
        </div>
      )}

      {/* MULTI-STAGE PROGRESS SKELETON */}
      {isGenerating && (
        <div className="bg-white rounded-2xl p-6 md:p-8 border border-indigo-100 shadow-md space-y-6 animate-pulse">
          <div className="flex items-center justify-between border-b border-slate-100 pb-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-indigo-50 flex items-center justify-center">
                <RefreshCw className="w-5 h-5 text-indigo-600 animate-spin" />
              </div>
              <div>
                <h3 className="text-base font-bold text-slate-800">
                  Synthesizing Real-Time Status Audit...
                </h3>
                <p className="text-xs text-indigo-600 font-medium">
                  {generationStage === 1 && 'Stage 1/3: Ingesting repository commit telemetry and PR latencies...'}
                  {generationStage === 2 && 'Stage 2/3: Calculating bus factor and issue hygiene indices...'}
                  {generationStage === 3 && 'Stage 3/3: Synthesizing executive summary and AI advisory recommendations...'}
                </p>
              </div>
            </div>
            <span className="text-xs font-mono text-slate-400">
              Processing {selectedRepo}
            </span>
          </div>

          {/* Skeleton Progress Bars */}
          <div className="space-y-3">
            <div className="h-4 bg-slate-100 rounded-lg w-3/4" />
            <div className="h-4 bg-slate-100 rounded-lg w-full" />
            <div className="h-4 bg-slate-100 rounded-lg w-5/6" />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 pt-2">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-24 bg-slate-50 border border-slate-100 rounded-xl p-4 space-y-2">
                <div className="h-3 bg-slate-200 rounded w-1/2" />
                <div className="h-6 bg-slate-200 rounded w-3/4" />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* RENDERED EXECUTIVE SUMMARY CARD */}
      {!isGenerating && report && (
        <div className="bg-white rounded-2xl p-6 md:p-8 border border-slate-200/90 shadow-sm space-y-6">
          <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 border-b border-slate-100 pb-4">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                  VERIFIED AUDIT
                </span>
                <span className="text-xs text-slate-400 font-mono">
                  {report.generatedDate} ({report.generatedAt})
                </span>
              </div>
              <h2 className="text-xl font-bold text-slate-900 tracking-tight">
                {report.title}
              </h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Audit scope: <span className="font-semibold text-slate-700">{report.repoName}</span> • Audit ID: <span className="font-mono text-slate-400">{report.reportId}</span>
              </p>
            </div>

            {/* Health Score Summary Gauge */}
            <div className="flex items-center gap-4 bg-slate-50 px-4 py-2.5 rounded-xl border border-slate-200/80">
              <div className="text-right">
                <p className="text-[10px] font-extrabold uppercase text-slate-400 tracking-wider">
                  HEALTH SCORE
                </p>
                <p className="text-xs font-bold text-slate-600">
                  {overallHealth.status}
                </p>
              </div>
              <div
                className="text-3xl font-extrabold"
                style={{ color: overallHealth.color }}
              >
                {overallHealth.score}
              </div>
            </div>
          </div>

          {/* Rendered Executive Narrative */}
          <div className="p-4 md:p-5 rounded-xl bg-slate-50/80 border border-slate-200/80 text-sm text-slate-700 leading-relaxed space-y-2">
            <div className="flex items-center gap-2 font-bold text-slate-900 text-xs uppercase tracking-wider">
              <FileText className="w-4 h-4 text-indigo-600" />
              <span>Executive Briefing</span>
            </div>
            <p>{report.executiveSummary}</p>
          </div>

          {/* Telemetry Snapshot KPI Pills */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="p-3 bg-white border border-slate-200 rounded-xl shadow-2xs">
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                Review Latency
              </span>
              <span className="text-lg font-bold text-slate-900 font-mono">
                {report.kpis?.latencyHours}h avg
              </span>
            </div>
            <div className="p-3 bg-white border border-slate-200 rounded-xl shadow-2xs">
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                Bus Factor Risk
              </span>
              <span className="text-lg font-bold text-slate-900 font-mono">
                {report.kpis?.busFactorRisk}
              </span>
            </div>
            <div className="p-3 bg-white border border-slate-200 rounded-xl shadow-2xs">
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                Dormant Issues
              </span>
              <span className="text-lg font-bold text-slate-900 font-mono">
                {report.kpis?.dormantCount} issues
              </span>
            </div>
            <div className="p-3 bg-white border border-slate-200 rounded-xl shadow-2xs">
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                Sprint Burndown
              </span>
              <span className="text-lg font-bold text-slate-900 font-mono">
                {report.kpis?.burnRate}% burned
              </span>
            </div>
          </div>
        </div>
      )}

      {/* METRIC FLAGS & AI EXPLANATION DRAWER SECTION */}
      {!isGenerating && report?.metricFlags && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-bold text-slate-900 tracking-tight flex items-center gap-2">
                <span>Metric Flags & AI Explanations</span>
                <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-slate-100 text-slate-600">
                  {report.metricFlags.length} Flags
                </span>
              </h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Click any metric flag card below to open the interactive AI explanation popover citing data timestamps.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {report.metricFlags.map((flag) => {
              const isHigh = flag.severity === 'High';
              const isMedium = flag.severity === 'Medium';

              return (
                <div
                  key={flag.id}
                  onClick={() => handleOpenFlagExplanation(flag)}
                  className={`p-5 rounded-2xl border transition-all cursor-pointer group bg-white shadow-xs hover:shadow-md ${
                    isHigh
                      ? 'border-rose-100 hover:border-rose-300'
                      : isMedium
                      ? 'border-amber-100 hover:border-amber-300'
                      : 'border-slate-200/90 hover:border-indigo-300'
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span
                      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold ${
                        isHigh
                          ? 'bg-rose-50 text-rose-700 border border-rose-200'
                          : isMedium
                          ? 'bg-amber-50 text-amber-700 border border-amber-200'
                          : 'bg-blue-50 text-blue-700 border border-blue-200'
                      }`}
                    >
                      <AlertTriangle className="w-3 h-3" />
                      <span>{flag.severity} Flag</span>
                    </span>

                    <span className="text-[11px] font-mono text-slate-400">
                      Detected: {flag.detectedAt.split(' ')[0]}
                    </span>
                  </div>

                  <h3 className="text-base font-bold text-slate-900 group-hover:text-indigo-600 transition-colors">
                    {flag.metric}
                  </h3>

                  <div className="my-2 flex items-baseline gap-2">
                    <span className="text-xl font-bold font-mono text-slate-900">
                      {flag.value}
                    </span>
                    <span className="text-xs text-slate-400 font-mono">
                      (Target: {flag.benchmark})
                    </span>
                  </div>

                  <p className="text-xs text-slate-600 line-clamp-2">
                    {flag.summary}
                  </p>

                  <div className="mt-3 pt-3 border-t border-slate-100 flex items-center justify-between text-xs font-bold text-indigo-600">
                    <span className="flex items-center gap-1">
                      <Sparkles className="w-3.5 h-3.5" />
                      <span>Click to view AI Explanation Drawer</span>
                    </span>
                    <ArrowRight className="w-3.5 h-3.5 transition-transform group-hover:translate-x-1" />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ADVISORY RECOMMENDATION CARDS SECTION */}
      {!isGenerating && report?.recommendations && (
        <div className="space-y-4">
          <div>
            <h2 className="text-lg font-bold text-slate-900 tracking-tight flex items-center gap-2">
              <span>Advisory Action Recommendations</span>
              <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-indigo-50 text-indigo-700 border border-indigo-100">
                Actionable Next Steps
              </span>
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Prioritized mitigation roadmaps with High, Medium, and Low impact classifications.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {report.recommendations.map((rec) => (
              <RecommendationCard
                key={rec.id}
                recommendation={rec}
                onNavigate={onNavigate}
                onAction={(recItem) => {
                  if (onNavigate && recItem.targetView) {
                    onNavigate(recItem.targetView);
                  }
                }}
              />
            ))}
          </div>
        </div>
      )}

      {/* AI EXPLANATION DRAWER POPOVER */}
      <ExplanationDrawer
        isOpen={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
        flag={activeFlag}
        repoName={selectedRepo}
        onNavigate={onNavigate}
      />
    </div>
  );
};

export default Reports;
