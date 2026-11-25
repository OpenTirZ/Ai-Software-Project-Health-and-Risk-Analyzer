// ===========================================================================
// Report Service — data layer for the Reports page
// Wraps metricsApi / reportApi from api.ts, adds AI explanation fetching
// and backend PDF download support.
// ===========================================================================

import {
  reportApi,
  metricsApi,
  API_BASE_URL,
  type GeneratedReport,
  type HealthSummaryData,
  type MetricsBreakdownData,
} from './api';

// ---------------------------------------------------------------------------
// View-model types
// ---------------------------------------------------------------------------

/** AI explanation for a single risk flag */
export interface FlagExplanation {
  indicatorName: string;
  severity: 'INFO' | 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  explanation: string;
  contributingMetrics: Record<string, any>;
  sourcePeriod: string | null;
  evidence: string[];
  uncertaintyOrCaveats: string | null;
}

/** Advisory recommendation */
export interface Recommendation {
  category: string;
  condition: string;
  action: string;
  rationale: string;
  priority: 'LOW' | 'MEDIUM' | 'HIGH';
  targetRole: string;
  isAdvisory: boolean;
  disclaimer: string;
}

/** Extended report with AI-powered insights */
export interface EnrichedReport extends GeneratedReport {
  executiveSummary?: string;
  flags?: Array<{
    id: string;
    type: string;
    severity: string;
    message: string;
    evidence?: any;
  }>;
  recommendations: string[];
  aiRecommendations?: Recommendation[];
}

// ---------------------------------------------------------------------------
// Service object
// ---------------------------------------------------------------------------

export const reportService = {
  /**
   * Generate a new report and return enriched data.
   */
  async generateReport(projectId: string): Promise<EnrichedReport> {
    const report = await reportApi.generateReport(projectId);
    return report as EnrichedReport;
  },

  /**
   * List all reports for a project.
   */
  async getReports(projectId: string): Promise<EnrichedReport[]> {
    const reports = await reportApi.getReports(projectId);
    return reports as EnrichedReport[];
  },

  /**
   * Fetch health summary + flags for explanation drawer integration.
   */
  async getHealthFlags(projectId: string): Promise<HealthSummaryData> {
    return metricsApi.getHealthSummary(projectId);
  },

  /**
   * Fetch metrics breakdown which includes recommendations.
   */
  async getBreakdownWithRecommendations(
    projectId: string
  ): Promise<{ breakdown: MetricsBreakdownData; recommendations: Recommendation[] }> {
    const breakdown = await metricsApi.getMetricsBreakdown(projectId);

    // The breakdown response includes recommendations array from the backend
    const rawRecs = (breakdown as any).recommendations || [];
    const recommendations: Recommendation[] = rawRecs.map((r: any) => ({
      category: r.category || 'general',
      condition: r.condition || '',
      action: r.action || r.message || '',
      rationale: r.rationale || '',
      priority: normalizePriority(r.priority),
      targetRole: r.target_role || r.targetRole || 'Team Lead',
      isAdvisory: r.is_advisory ?? r.isAdvisory ?? true,
      disclaimer:
        r.disclaimer ||
        'Recommendations are advisory. Final decisions remain with the engineering team.',
    }));

    return { breakdown, recommendations };
  },

  /**
   * Request AI explanation for a specific flag from the backend.
   * Falls back to a local explanation if the endpoint is unavailable.
   */
  async explainFlag(
    projectId: string,
    flag: { id: string; type: string; severity: string; message: string; evidence?: any }
  ): Promise<FlagExplanation> {
    const token = localStorage.getItem('aegis_token');

    try {
      const response = await fetch(
        `${API_BASE_URL}/projects/${projectId}/metrics/explain-flag`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({ flag }),
        }
      );

      if (response.ok) {
        const data = await response.json();
        const exp = data.explanation || data;
        return {
          indicatorName: exp.indicator_name || exp.indicatorName || flag.id,
          severity: normalizeSeverity(exp.severity || flag.severity),
          explanation: exp.explanation || flag.message,
          contributingMetrics: exp.contributing_metrics || exp.contributingMetrics || {},
          sourcePeriod: exp.source_period || exp.sourcePeriod || null,
          evidence: Array.isArray(exp.evidence) ? exp.evidence : [],
          uncertaintyOrCaveats:
            exp.uncertainty_or_caveats || exp.uncertaintyOrCaveats || null,
        };
      }
    } catch {
      // Fall through to local fallback
    }

    // Local fallback when backend explanation endpoint is unavailable
    return buildLocalExplanation(flag);
  },

  /**
   * Download a PDF report from the backend.
   * Falls back to client-side generation if the endpoint is unavailable.
   */
  async downloadPDF(
    projectId: string,
    reportId: string,
    fallbackReport?: GeneratedReport
  ): Promise<void> {
    const token = localStorage.getItem('aegis_token');

    try {
      const response = await fetch(
        `${API_BASE_URL}/projects/${projectId}/reports/${reportId}/pdf`,
        {
          headers: {
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
        }
      );

      if (response.ok) {
        const blob = await response.blob();
        triggerDownload(blob, `project_report_${reportId}.pdf`);
        return;
      }
    } catch {
      // Fall through to client-side generation
    }

    // Client-side fallback
    if (fallbackReport) {
      const blob = generateClientPDFBlob(fallbackReport);
      const cleanName = (fallbackReport.project || 'report').replace(/[^a-zA-Z0-9_-]/g, '_');
      triggerDownload(blob, `${cleanName}_health_report.pdf`);
    }
  },
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function normalizePriority(raw: string | undefined): 'LOW' | 'MEDIUM' | 'HIGH' {
  const upper = (raw || 'MEDIUM').toUpperCase();
  if (upper === 'HIGH') return 'HIGH';
  if (upper === 'LOW') return 'LOW';
  return 'MEDIUM';
}

function normalizeSeverity(
  raw: string
): 'INFO' | 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL' {
  const upper = (raw || 'MEDIUM').toUpperCase();
  if (['INFO', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'].includes(upper))
    return upper as any;
  return 'MEDIUM';
}

function buildLocalExplanation(flag: {
  id: string;
  severity: string;
  message: string;
  evidence?: any;
}): FlagExplanation {
  const evidence: string[] = [];
  if (flag.evidence && typeof flag.evidence === 'object') {
    for (const [key, val] of Object.entries(flag.evidence)) {
      evidence.push(`${key}: ${JSON.stringify(val)}`);
    }
  }

  return {
    indicatorName: flag.id,
    severity: normalizeSeverity(flag.severity),
    explanation: flag.message,
    contributingMetrics: flag.evidence || {},
    sourcePeriod: null,
    evidence: evidence.length > 0 ? evidence : ['No detailed evidence available.'],
    uncertaintyOrCaveats:
      'This explanation was generated locally without AI assistance.',
  };
}

function triggerDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', filename);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

function escapePdf(str: string): string {
  return str.replace(/[\\()]/g, '\\$&');
}

function generateClientPDFBlob(report: GeneratedReport): Blob {
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
    ...report.recommendations.map(
      (rec, idx) => `0 -18 Td (${idx + 1}. ${sanitize(rec)}) Tj`
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
