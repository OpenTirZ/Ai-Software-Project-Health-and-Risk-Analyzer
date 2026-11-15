import React, { useState } from 'react';
import type { PageView, RiskItem } from '../types';
import { risksData } from '../data/mockData';
import { AlertTriangle, Info, ChevronRight } from 'lucide-react';

interface RiskAnalysisProps {
  selectedRepo: string;
  onNavigate: (view: PageView) => void;
}

export const RiskAnalysis: React.FC<RiskAnalysisProps> = ({ selectedRepo, onNavigate }) => {
  const [filter, setFilter] = useState<'All' | 'High' | 'Medium' | 'Low'>('All');
  const [selectedRisk, setSelectedRisk] = useState<RiskItem>(risksData[0]);

  const filteredRisks = risksData.filter((r) => {
    if (filter === 'All') return true;
    return r.severity.toLowerCase() === filter.toLowerCase();
  });

  const highCount = risksData.filter((r) => r.severity === 'HIGH').length;
  const mediumCount = risksData.filter((r) => r.severity === 'MEDIUM').length;
  const lowCount = risksData.filter((r) => r.severity === 'LOW').length;

  return (
    <div className="p-6 md:p-8 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl md:text-3xl font-bold text-slate-900 tracking-tight">
          Risk Analysis
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          {risksData.length} potential risks identified for <span className="font-semibold text-slate-700">{selectedRepo}</span>.
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
            const isSelected = selectedRisk.id === risk.id;
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
              {selectedRisk.title}
            </p>
          </div>

          <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200/80 text-xs text-slate-600 leading-relaxed">
            <p className="font-semibold text-slate-800 mb-1">Explainable evidence & threshold comparison:</p>
            <p>{selectedRisk.whyRisk}</p>
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
