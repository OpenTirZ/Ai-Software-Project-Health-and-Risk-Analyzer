import React from 'react';
import { 
  ArrowRight, 
  CheckCircle2, 
  AlertTriangle, 
  TrendingUp, 
  Users, 
  Clock, 
  GitBranch, 
  ShieldCheck 
} from 'lucide-react';

/**
 * Advisory Recommendation Card
 * Displays actionable next steps with clear High/Medium/Low priority tags,
 * estimated impact, category classification, and direct navigation trigger.
 */
export const RecommendationCard = ({ recommendation, onAction, onNavigate }) => {
  if (!recommendation) return null;

  const {
    id,
    priority = 'Medium',
    category = 'General',
    title,
    description,
    rationale,
    estimatedImpact,
    actionLabel = 'Take Action',
    targetView,
  } = recommendation;

  // Category Icon Resolver
  const getCategoryIcon = () => {
    const cat = (category || '').toLowerCase();
    if (cat.includes('pr') || cat.includes('review') || cat.includes('turnaround')) {
      return <Clock className="w-4 h-4 text-indigo-500" />;
    }
    if (cat.includes('team') || cat.includes('bus') || cat.includes('workload')) {
      return <Users className="w-4 h-4 text-purple-500" />;
    }
    if (cat.includes('branch') || cat.includes('git')) {
      return <GitBranch className="w-4 h-4 text-blue-500" />;
    }
    if (cat.includes('backlog') || cat.includes('issue')) {
      return <AlertTriangle className="w-4 h-4 text-amber-500" />;
    }
    return <ShieldCheck className="w-4 h-4 text-emerald-500" />;
  };

  // Priority Badge Styling
  const getPriorityBadge = () => {
    switch (priority) {
      case 'High':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-rose-50 text-rose-700 border border-rose-200 shadow-xs">
            <span className="w-1.5 h-1.5 rounded-full bg-rose-500 animate-pulse" />
            HIGH PRIORITY
          </span>
        );
      case 'Medium':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-amber-50 text-amber-700 border border-amber-200">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
            MEDIUM PRIORITY
          </span>
        );
      case 'Low':
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-blue-50 text-blue-700 border border-blue-200">
            <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />
            LOW PRIORITY
          </span>
        );
    }
  };

  const handleCardClick = () => {
    if (onAction) {
      onAction(recommendation);
    } else if (onNavigate && targetView) {
      onNavigate(targetView);
    }
  };

  return (
    <div
      className={`bg-white rounded-2xl p-5 border transition-all duration-200 flex flex-col justify-between hover:shadow-md ${
        priority === 'High'
          ? 'border-rose-100 hover:border-rose-200 ring-1 ring-rose-50'
          : priority === 'Medium'
          ? 'border-amber-100 hover:border-amber-200'
          : 'border-slate-200/90 hover:border-slate-300'
      }`}
    >
      <div>
        {/* Top Header: Priority Tag & Category */}
        <div className="flex items-center justify-between gap-2 mb-3">
          {getPriorityBadge()}
          <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
            {getCategoryIcon()}
            <span>{category}</span>
          </span>
        </div>

        {/* Title */}
        <h3 className="text-base font-bold text-slate-900 tracking-tight leading-snug">
          {title}
        </h3>

        {/* Description */}
        <p className="text-xs text-slate-600 mt-2 leading-relaxed">
          {description}
        </p>

        {/* Rationale Quote */}
        {rationale && (
          <div className="mt-3 p-2.5 rounded-xl bg-slate-50/90 border border-slate-100 text-[11px] text-slate-600 leading-normal">
            <span className="font-semibold text-slate-700">Advisory Rationale: </span>
            {rationale}
          </div>
        )}
      </div>

      {/* Footer: Estimated Impact & Action Trigger */}
      <div className="mt-4 pt-3.5 border-t border-slate-100 flex items-center justify-between gap-3">
        {estimatedImpact ? (
          <span className="inline-flex items-center gap-1.5 text-xs font-bold text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded-lg border border-emerald-100">
            <TrendingUp className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
            <span>{estimatedImpact}</span>
          </span>
        ) : (
          <span className="text-xs text-slate-400 font-medium">Standard SLA</span>
        )}

        <button
          onClick={handleCardClick}
          className="inline-flex items-center gap-1.5 text-xs font-bold text-indigo-600 hover:text-indigo-800 transition-colors cursor-pointer group"
        >
          <span>{actionLabel}</span>
          <ArrowRight className="w-3.5 h-3.5 transition-transform group-hover:translate-x-0.5" />
        </button>
      </div>
    </div>
  );
};

export default RecommendationCard;
