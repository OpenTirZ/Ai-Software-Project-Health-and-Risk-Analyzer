import React, { useState, useEffect } from 'react';
import type { PageView, RiskItem } from '../types';
import { AlertTriangle, Info, ChevronRight } from 'lucide-react';
import { metricService } from '../services/metricService';

interface RiskAnalysisProps {
  projectId?: string;
  selectedRepo: string;
  onNavigate: (view: PageView) => void;
}

export const RiskAnalysis: React.FC<RiskAnalysisProps> = ({ 
  projectId = 'proj_core_platform', 
  selectedRepo, 
  onNavigate 
}) => {
  const [filter, setFilter] = useState<'All' | 'High' | 'Medium' | 'Low'>('All');
  const [risks, setRisks] = useState<RiskItem[]>([]);
  const [selectedRisk, setSelectedRisk] = useState<RiskItem | null>(null);

  useEffect(() => {
    let isMounted = true;
    metricService.getHealthSummary(projectId, selectedRepo)
      .then((data) => {
        if (!isMounted || !data) return;

        const generatedRisks: RiskItem[] = [];
        const bottlenecks = data.bottlenecks || {};
        const workload = data.workload || {};
        const staleIssues = data.staleIssues || [];
        const sprint = data.sprint || {};
        const prs = bottlenecks.criticalBottlenecks || [];

        // 1. PR Review Latency Risk
        const latency = bottlenecks.avgReviewLatencyHours ?? 18;
        const prSeverity = latency >= 24 ? 'HIGH' : latency >= 18 ? 'MEDIUM' : 'LOW';
        const prEvidence = prs.length > 0
          ? prs.slice(0, 4).map((p: any) => `${p.id} (${p.hoursPending}h - ${p.title.slice(0, 32)}...)`)
          : [`Average latency: ${latency}h`, `Pending >48h: ${bottlenecks.pendingPrsOver48hCount || 0} PRs`];
        generatedRisks.push({
          id: 'risk_pr_latency',
          severity: prSeverity,
          title: `PR Review Latency & Bottlenecks (${selectedRepo})`,
          description: `Time to first review averages ${latency}h with ${bottlenecks.pendingPrsOver48hCount || 0} PRs pending beyond 48 hours.`,
          evidence: prEvidence,
          threshold: 'Target ≤ 24h review turnaround',
          whyRisk: `Pull requests delayed past 48 hours create architectural drift, exacerbate merge conflicts, and throttle overall team velocity for ${selectedRepo}.`,
        });

        // 2. Bus Factor / Workload Concentration Risk
        const busRisk = workload.busFactorRisk || 'Moderate Risk';
        const topContrib = workload.contributors?.[0];
        const busSeverity = busRisk === 'Critical Risk' ? 'HIGH' : busRisk === 'Moderate Risk' ? 'MEDIUM' : 'LOW';
        const busEvidence = (workload.contributors || []).slice(0, 3).map((c: any) => 
          `${c.name} (${c.commits}c, ${c.percentage}% share)`
        );
        generatedRisks.push({
          id: 'risk_workload_bus',
          severity: busSeverity,
          title: `Workload Concentration & Bus Factor`,
          description: `Bus factor score is ${workload.busFactorScore || 2} (${busRisk}). ${topContrib ? `${topContrib.name} commands ${topContrib.percentage}% of repository activity.` : 'High author concentration.'}`,
          evidence: busEvidence.length > 0 ? busEvidence : ['Workload distribution metrics'],
          threshold: 'Single author share ≤ 35%',
          whyRisk: `Over-reliance on key contributors leaves critical knowledge unshared, resulting in deployment blockages when primary authors are unavailable.`,
        });

        // 3. Stale Issues Risk
        const staleCount = staleIssues.filter((i: any) => i.daysInactive >= 14).length;
        const issueSeverity = staleCount >= 4 ? 'HIGH' : staleCount >= 1 ? 'MEDIUM' : 'LOW';
        const issueEvidence = staleIssues.slice(0, 4).map((i: any) => 
          `${i.id} (${i.daysInactive}d dormant - ${i.title.slice(0, 28)}...)`
        );
        generatedRisks.push({
          id: 'risk_stale_issues',
          severity: issueSeverity,
          title: `Dormant & Stale Issue Backlog`,
          description: `${staleCount} issues in ${selectedRepo} have been dormant for more than 14 days without active updates.`,
          evidence: issueEvidence.length > 0 ? issueEvidence : ['No dormant issues flagged'],
          threshold: 'Max inactivity ≤ 14 days',
          whyRisk: `Lingering stale issues obscure production bugs, decay backlog hygiene, and impede sprint milestone planning.`,
        });

        // 4. Sprint Velocity Risk
        const compPts = sprint.completedStoryPoints ?? 30;
        const totalPts = sprint.totalStoryPoints ?? 50;
        const ratio = totalPts > 0 ? compPts / totalPts : 1;
        const sprintSeverity = ratio < 0.65 ? 'HIGH' : ratio < 0.85 ? 'MEDIUM' : 'LOW';
        generatedRisks.push({
          id: 'risk_sprint_velocity',
          severity: sprintSeverity,
          title: `Sprint Goal Velocity Variance (${sprint.sprintName || 'Current Sprint'})`,
          description: `${compPts}/${totalPts} story points burned at ${sprint.velocity || 20} pts/wk with ${sprint.daysRemaining || 4} days remaining.`,
          evidence: [
            `Burned: ${compPts}/${totalPts} points (${Math.round(ratio * 100)}%)`,
            `Pacing: ${sprint.velocity || 20} pts/wk (Target: ${sprint.velocityTarget || 16} pts/wk)`,
            `Status: ${sprint.velocityStatus || 'On Track'}`,
          ],
          threshold: 'Burndown velocity ≥ target schedule',
          whyRisk: `Burndown velocity variance increases the probability of carryover points and slipped sprint releases.`,
        });

        // 5. Stale Branches & Branch Divergence Risk
        const staleBranches = bottlenecks.staleBranchesCount ?? 2;
        const branchSeverity = staleBranches >= 4 ? 'HIGH' : staleBranches >= 2 ? 'MEDIUM' : 'LOW';
        generatedRisks.push({
          id: 'risk_stale_branches',
          severity: branchSeverity,
          title: `Git Branch Divergence & Hygiene`,
          description: `${staleBranches} unmerged git branches exhibit no recent commit activity on ${selectedRepo}.`,
          evidence: [
            `${staleBranches} branches exceeding 14 days without commit`,
            `Total active branches: ${bottlenecks.totalBranchesCount || 4}`,
          ],
          threshold: 'Dormant branches ≤ 2',
          whyRisk: `Long-lived stale branches diverge from mainline trunk, sharply escalating merge conflict frequency and rebasing friction.`,
        });

        setRisks(generatedRisks);
        setSelectedRisk(generatedRisks[0]);
      })
      .catch((err) => {
        console.warn('Could not load dynamic risks for RiskAnalysis:', err);
      });

    return () => { isMounted = false; };
  }, [projectId, selectedRepo]);

  const filteredRisks = risks.filter((r) => {
    if (filter === 'All') return true;
    return r.severity.toLowerCase() === filter.toLowerCase();
  });

  const highCount = risks.filter((r) => r.severity === 'HIGH').length;
  const mediumCount = risks.filter((r) => r.severity === 'MEDIUM').length;
  const lowCount = risks.filter((r) => r.severity === 'LOW').length;

  const activeRisk = selectedRisk || risks[0] || {
    id: 'placeholder',
    severity: 'LOW',
    title: 'Analyzing telemetry...',
    description: 'Scanning project repository for active risks.',
    evidence: [],
    threshold: 'Standard benchmarks',
    whyRisk: 'Telemetry scanning is active.',
  };

  return (
    <div className="p-6 md:p-8 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl md:text-3xl font-bold text-slate-900 tracking-tight">
          Risk Analysis
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          {risks.length} dynamic risks evaluated for <span className="font-semibold text-slate-700">{selectedRepo}</span> based on live telemetry.
        </p>
      </div>

      {/* Filter Tabs & Stat Boxes */}
      <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4">
        {/* Filter Pills */}
        <div className="inline-flex items-center gap-2 p-1.5 bg-slate-100 rounded-xl">
          {(['All', 'High', 'Medium', 'Low'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setFilter(tab)}
              className={`px-4 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                filter === tab
                  ? 'bg-white text-blue-600 shadow-sm'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              {tab}
            </button>
          ))}
        </div>

        {/* 3 Stat Boxes */}
        <div className="flex items-center gap-3">
          {/* HIGH */}
          <div className="bg-white rounded-xl px-5 py-3 border border-slate-200/90 shadow-sm text-center min-w-[100px]">
            <p className="text-[11px] font-extrabold uppercase text-rose-600 tracking-wider">
              HIGH
            </p>
            <p className="text-2xl font-bold text-slate-900 mt-0.5">
              {highCount}
            </p>
          </div>

          {/* MEDIUM */}
          <div className="bg-white rounded-xl px-5 py-3 border border-slate-200/90 shadow-sm text-center min-w-[100px]">
            <p className="text-[11px] font-extrabold uppercase text-amber-500 tracking-wider">
              MEDIUM
            </p>
            <p className="text-2xl font-bold text-slate-900 mt-0.5">
              {mediumCount}
            </p>
          </div>

          {/* LOW */}
          <div className="bg-white rounded-xl px-5 py-3 border border-slate-200/90 shadow-sm text-center min-w-[100px]">
            <p className="text-[11px] font-extrabold uppercase text-blue-600 tracking-wider">
              LOW
            </p>
            <p className="text-2xl font-bold text-slate-900 mt-0.5">
              {lowCount}
            </p>
          </div>
        </div>
      </div>

      {/* Risk Cards & Explainability Section */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Risks List (8 cols) */}
        <div className="lg:col-span-8 space-y-4">
          {filteredRisks.map((risk) => {
            const isSelected = activeRisk.id === risk.id;
            const badgeColor =
              risk.severity === 'HIGH'
                ? 'text-rose-600 bg-rose-50 border-rose-200'
                : risk.severity === 'MEDIUM'
                ? 'text-amber-600 bg-amber-50 border-amber-200'
                : 'text-blue-600 bg-blue-50 border-blue-200';

            return (
              <div
                key={risk.id}
                onClick={() => setSelectedRisk(risk)}
                className={`bg-white rounded-2xl p-6 border transition-all cursor-pointer ${
                  isSelected
                    ? 'border-indigo-500 ring-2 ring-indigo-50 shadow-md'
                    : 'border-slate-200/90 hover:border-slate-300 shadow-sm'
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold border ${badgeColor}`}>
                    <AlertTriangle className="w-3 h-3" />
                    <span>{risk.severity}</span>
                  </span>
                  <span className="text-xs text-slate-400 font-mono">
                    {risk.threshold}
                  </span>
                </div>

                <h3 className="text-lg font-bold text-slate-900 mt-2">
                  {risk.title}
                </h3>
                <p className="text-sm text-slate-600 mt-1">
                  {risk.description}
                </p>

                {/* Evidence items */}
                <div className="mt-4 pt-4 border-t border-slate-100">
                  <p className="text-xs font-bold text-slate-800 uppercase tracking-wider mb-2">
                    Evidence:
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {risk.evidence.map((ev, i) => (
                      <span
                        key={i}
                        className="px-2.5 py-1 rounded-lg bg-slate-100 text-slate-700 text-xs font-mono font-medium border border-slate-200"
                      >
                        {ev}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Explainable AI Risk Inspector Card (4 cols) */}
        <div className="lg:col-span-4 bg-white rounded-2xl p-6 border border-slate-200/90 shadow-sm sticky top-6 space-y-4">
          <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
            <Info className="w-5 h-5 text-indigo-600" />
            <h3 className="text-base font-bold text-slate-900">
              Why is this a risk?
            </h3>
          </div>

          <div>
            <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">
              Active Selection
            </p>
            <p className="text-sm font-bold text-slate-900 mt-0.5">
              {activeRisk.title}
            </p>
          </div>

          <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200/80 text-xs text-slate-600 leading-relaxed">
            <p className="font-semibold text-slate-800 mb-1">Explainable evidence & threshold comparison:</p>
            <p>{activeRisk.whyRisk}</p>
          </div>

          <div className="space-y-2 pt-2">
            <p className="text-xs font-bold text-slate-700">Recommended Resolution:</p>
            <ul className="text-xs text-slate-600 space-y-1.5 list-disc list-inside">
              <li>Assign senior reviewer to unblock aging pull requests</li>
              <li>Re-evaluate threshold configuration in project settings</li>
              <li>Schedule automatic reminder ping on Slack for stale items</li>
            </ul>
          </div>

          <button
            onClick={() => onNavigate('activity')}
            className="w-full mt-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold transition-colors flex items-center justify-center gap-1.5 cursor-pointer shadow-md shadow-indigo-600/20"
          >
            <span>Inspect in Activity Logs</span>
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
};
