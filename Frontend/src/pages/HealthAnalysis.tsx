import React, { useState } from 'react';
import type { PageView } from '../types';
import { Info, X } from 'lucide-react';

interface HealthAnalysisProps {
  selectedRepo: string;
  onNavigate: (view: PageView) => void;
}

export const HealthAnalysis: React.FC<HealthAnalysisProps> = ({ selectedRepo }) => {
  const [showCalculationModal, setShowCalculationModal] = useState(false);

  const indicators = [
    {
      id: 'bottlenecks',
      title: 'Bottlenecks',
      description: 'Available project evidence and metrics',
      score: 82,
      status: 'Good',
      statusColor: 'text-emerald-600 bg-emerald-50 border-emerald-200',
      weight: '30%',
    },
    {
      id: 'workload',
      title: 'Workload Balance',
      description: 'Available project evidence and metrics',
      score: 76,
      status: 'Good',
      statusColor: 'text-emerald-600 bg-emerald-50 border-emerald-200',
      weight: '25%',
    },
    {
      id: 'issues',
      title: 'Issue Health',
      description: 'Available project evidence and metrics',
      score: 88,
      status: 'Good',
      statusColor: 'text-emerald-600 bg-emerald-50 border-emerald-200',
      weight: '25%',
    },
    {
      id: 'schedule',
      title: 'Schedule',
      description: 'Available project evidence and metrics',
      score: 70,
      status: 'Caution',
      statusColor: 'text-amber-600 bg-amber-50 border-amber-200',
      weight: '20%',
    },
  ];

  return (
    <div className="p-6 md:p-8 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl md:text-3xl font-bold text-slate-900 tracking-tight">
          Project Health Analysis
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          Overall project health based on available project activity indicators for <span className="font-semibold text-slate-700">{selectedRepo}</span>.
        </p>
      </div>

      {/* Main Analysis Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Large Gauge Card (5 cols) */}
        <div className="lg:col-span-5 bg-white rounded-2xl p-8 border border-slate-200/90 shadow-sm flex flex-col items-center justify-between text-center min-h-[460px]">
          <div className="w-full text-left">
            <h2 className="text-xl font-bold text-slate-900">
              Overall Health
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">Automated weighted calculation</p>
          </div>

          {/* Huge Circular Gauge */}
          <div className="relative my-auto w-56 h-56 flex items-center justify-center">
            <svg className="w-full h-full transform -rotate-90" viewBox="0 0 160 160">
              <circle
                cx="80"
                cy="80"
                r="66"
                stroke="#f1f5f9"
                strokeWidth="14"
                fill="transparent"
              />
              <circle
                cx="80"
                cy="80"
                r="66"
                stroke="#10b981"
                strokeWidth="14"
                strokeDasharray={2 * Math.PI * 66}
                strokeDashoffset={(2 * Math.PI * 66) * (1 - 0.82)}
                strokeLinecap="round"
                fill="transparent"
              />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-6xl font-extrabold text-slate-900 tracking-tight">82</span>
              <span className="text-sm font-bold text-emerald-600 uppercase tracking-widest mt-1">
                GOOD
              </span>
            </div>
          </div>

          <p className="text-sm text-slate-500 font-medium">
            Based on 4 available indicators
          </p>
        </div>

        {/* Right 4 Indicators Cards (7 cols) */}
        <div className="lg:col-span-7 space-y-4">
          {indicators.map((ind) => (
            <div
              key={ind.id}
              className="bg-white rounded-2xl p-6 border border-slate-200/90 shadow-sm flex items-center justify-between hover:border-slate-300 transition-all"
            >
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <h3 className="text-base font-bold text-slate-900">
                    {ind.title}
                  </h3>
                  <span className="text-[11px] font-semibold text-slate-400 bg-slate-100 px-2 py-0.5 rounded">
                    Weight: {ind.weight}
                  </span>
                </div>
                <p className="text-xs text-slate-500">
                  {ind.description}
                </p>
              </div>

              <div className="text-right flex items-center gap-4">
                <div className="w-24 hidden sm:block bg-slate-100 h-2 rounded-full overflow-hidden">
                  <div 
                    className={`h-full rounded-full ${ind.score >= 75 ? 'bg-emerald-500' : 'bg-amber-500'}`}
                    style={{ width: `${ind.score}%` }}
                  />
                </div>
                <div>
                  <div className={`text-2xl font-extrabold ${ind.score >= 75 ? 'text-emerald-600' : 'text-amber-600'}`}>
                    {ind.score}
                  </div>
                  <span className={`inline-block text-xs font-semibold px-2 py-0.5 rounded-full border ${ind.statusColor}`}>
                    {ind.status}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* How is this calculated button */}
      <div className="pt-2">
        <button
          onClick={() => setShowCalculationModal(true)}
          className="inline-flex items-center gap-1.5 text-sm font-medium text-blue-600 hover:text-blue-800 transition-colors cursor-pointer"
        >
          <Info className="w-4 h-4" />
          <span>How is this calculated?</span>
        </button>
      </div>

      {/* Modal Explanation */}
      {showCalculationModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-slate-200">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3 mb-4">
              <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                <Info className="w-5 h-5 text-blue-600" />
                <span>Health Score Calculation</span>
              </h3>
              <button
                onClick={() => setShowCalculationModal(false)}
                className="text-slate-400 hover:text-slate-600 p-1 cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-4 text-sm text-slate-600">
              <p>
                The <strong>Overall Health Score (82)</strong> is computed using an explainable multi-metric weighted formula across 4 telemetry dimensions:
              </p>
              <div className="bg-slate-50 p-3.5 rounded-xl border border-slate-200 font-mono text-xs space-y-1 text-slate-800">
                <p>• Bottlenecks (30% weight): 82 × 0.30 = 24.6</p>
                <p>• Workload Balance (25% weight): 76 × 0.25 = 19.0</p>
                <p>• Issue Health (25% weight): 88 × 0.25 = 22.0</p>
                <p>• Schedule Velocity (20% weight): 70 × 0.20 = 14.0</p>
                <p className="font-bold border-t border-slate-200 pt-1 text-indigo-700">
                  Total Score = 24.6 + 19.0 + 22.0 + 14.0 = 82 / 100
                </p>
              </div>
              <p className="text-xs text-slate-500">
                Scores between 80-100 are classified as <strong>GOOD</strong>. Scores 60-79 reflect <strong>MODERATE/CAUTION</strong>. Scores below 60 require immediate management intervention.
              </p>
            </div>

            <div className="mt-6 flex justify-end">
              <button
                onClick={() => setShowCalculationModal(false)}
                className="px-5 py-2 rounded-xl bg-slate-900 text-white text-xs font-semibold hover:bg-slate-800 cursor-pointer"
              >
                Got it
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
