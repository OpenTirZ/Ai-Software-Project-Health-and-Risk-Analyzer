import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { PageView } from '../types';
import { metricsApi, type ProjectResponse } from '../services/api';
import {
  AlertCircle,
  AlertTriangle,
  Bell,
  BellOff,
  CheckCheck,
  Info,
  RefreshCw,
} from 'lucide-react';

interface NotificationPanelProps {
  projects: ProjectResponse[];
  userKey?: string;
  onSelectProject?: (projectId: string) => void;
  onNavigate: (view: PageView) => void;
}

type Severity = 'high' | 'medium' | 'low';

interface NotificationItem {
  key: string;
  projectId: string;
  projectName: string;
  severity: Severity;
  type: string;
  message: string;
  evaluatedAt: string | null;
}

type Filter = 'all' | 'unread';

const REFRESH_INTERVAL_MS = 120000;
const SEVERITY_ORDER: Record<Severity, number> = { high: 0, medium: 1, low: 2 };

const normalizeSeverity = (value: string | undefined): Severity => {
  const level = String(value || '').toLowerCase();
  if (level === 'high' || level === 'critical') return 'high';
  if (level === 'medium' || level === 'moderate') return 'medium';
  return 'low';
};

const formatType = (type: string) =>
  type
    .replace(/[_-]+/g, ' ')
    .trim()
    .replace(/\b\w/g, (char) => char.toUpperCase());

const formatRelativeTime = (iso: string | null) => {
  if (!iso) return '';
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return '';
  const minutes = Math.max(0, Math.floor((Date.now() - then) / 60000));
  if (minutes < 1) return 'Just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(iso).toLocaleDateString();
};

const readStorageKey = (userKey: string) => `aegis_read_notifications:${userKey}`;

const loadReadKeys = (userKey: string): Set<string> => {
  try {
    const raw = localStorage.getItem(readStorageKey(userKey));
    const parsed = raw ? JSON.parse(raw) : [];
    return new Set(Array.isArray(parsed) ? parsed.map(String) : []);
  } catch {
    return new Set();
  }
};

const persistReadKeys = (userKey: string, keys: Set<string>) => {
  try {
    localStorage.setItem(
      readStorageKey(userKey),
      JSON.stringify(Array.from(keys).slice(-500)),
    );
  } catch {
    return;
  }
};

const severityStyles: Record<
  Severity,
  { icon: React.ElementType; wrap: string; badge: string; label: string }
> = {
  high: {
    icon: AlertCircle,
    wrap: 'bg-[#FEE2E2] text-[#CC1F2E]',
    badge: 'border-[#F8A9A9] bg-[#FEE2E2] text-[#CC1F2E]',
    label: 'High',
  },
  medium: {
    icon: AlertTriangle,
    wrap: 'bg-amber-50 text-amber-700',
    badge: 'border-amber-200 bg-amber-50 text-amber-800',
    label: 'Medium',
  },
  low: {
    icon: Info,
    wrap: 'bg-[#CDEFE6] text-[#0B6B63]',
    badge: 'border-[#9ED4C8] bg-[#EAF8F3] text-[#0B6B63]',
    label: 'Low',
  },
};

export const NotificationPanel: React.FC<NotificationPanelProps> = ({
  projects,
  userKey = 'default',
  onSelectProject,
  onNavigate,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [hasError, setHasError] = useState(false);
  const [filter, setFilter] = useState<Filter>('all');
  const [readKeys, setReadKeys] = useState<Set<string>>(() =>
    loadReadKeys(userKey),
  );

  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const requestIdRef = useRef(0);

  const monitoredProjects = useMemo(
    () => projects.filter((project) => Boolean(project.repo_url)),
    [projects],
  );

  const projectSignature = monitoredProjects.map((project) => project.id).join('|');

  useEffect(() => {
    setReadKeys(loadReadKeys(userKey));
  }, [userKey]);

  const loadNotifications = useCallback(async () => {
    const requestId = ++requestIdRef.current;

    if (monitoredProjects.length === 0) {
      setItems([]);
      setHasError(false);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);

    const results = await Promise.allSettled(
      monitoredProjects.map((project) =>
        metricsApi.getHealthSummary(project.id).then((summary) => ({
          project,
          summary,
        })),
      ),
    );

    if (requestId !== requestIdRef.current) return;

    const collected: NotificationItem[] = [];
    let failures = 0;

    results.forEach((result) => {
      if (result.status === 'rejected') {
        failures += 1;
        return;
      }
      const { project, summary } = result.value;
      (summary.active_flags || []).forEach((flag) => {
        collected.push({
          key: `${project.id}:${flag.type}:${flag.message}`,
          projectId: project.id,
          projectName: project.name,
          severity: normalizeSeverity(flag.severity),
          type: flag.type,
          message: flag.message,
          evaluatedAt: summary.evaluated_at || summary.last_synced_at || null,
        });
      });
    });

    collected.sort(
      (a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity],
    );

    setItems(collected);
    setHasError(failures > 0 && failures === results.length);
    setIsLoading(false);
  }, [monitoredProjects]);

  useEffect(() => {
    loadNotifications();
    const timer = window.setInterval(loadNotifications, REFRESH_INTERVAL_MS);
    return () => {
      window.clearInterval(timer);
      requestIdRef.current += 1;
    };
  }, [projectSignature, loadNotifications]);

  useEffect(() => {
    if (!isOpen) return;

    const handlePointerDown = (event: MouseEvent | TouchEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setIsOpen(false);
        triggerRef.current?.focus();
      }
    };

    document.addEventListener('mousedown', handlePointerDown);
    document.addEventListener('touchstart', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);

    return () => {
      document.removeEventListener('mousedown', handlePointerDown);
      document.removeEventListener('touchstart', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen]);

  const unreadCount = useMemo(
    () => items.filter((item) => !readKeys.has(item.key)).length,
    [items, readKeys],
  );

  const visibleItems = useMemo(
    () =>
      filter === 'unread'
        ? items.filter((item) => !readKeys.has(item.key))
        : items,
    [items, readKeys, filter],
  );

  const markRead = (keys: string[]) => {
    setReadKeys((prev) => {
      const next = new Set(prev);
      keys.forEach((key) => next.add(key));
      persistReadKeys(userKey, next);
      return next;
    });
  };

  const handleToggle = () => {
    const willOpen = !isOpen;
    setIsOpen(willOpen);
    if (willOpen) loadNotifications();
  };

  const handleOpenItem = (item: NotificationItem) => {
    markRead([item.key]);
    onSelectProject?.(item.projectId);
    setIsOpen(false);
    onNavigate('risk-analysis');
  };

  const handleViewAll = () => {
    setIsOpen(false);
    onNavigate('risk-analysis');
  };

  const badgeLabel = unreadCount > 9 ? '9+' : String(unreadCount);

  return (
    <div ref={containerRef} className="relative">
      <button
        ref={triggerRef}
        type="button"
        onClick={handleToggle}
        title="Notifications"
        aria-label={
          unreadCount > 0
            ? `Notifications, ${unreadCount} unread`
            : 'Notifications'
        }
        aria-haspopup="dialog"
        aria-expanded={isOpen}
        className={`relative flex h-8 w-8 items-center justify-center rounded-md hover:bg-[#CDEFE6] hover:text-[#0B6B63] ${
          isOpen ? 'bg-[#CDEFE6] text-[#0B6B63]' : 'text-slate-500'
        }`}
      >
        <Bell className="h-[17px] w-[17px]" />

        {unreadCount > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-[#CC1F2E] px-1 text-[9px] font-bold leading-none text-white ring-2 ring-white">
            {badgeLabel}
          </span>
        )}
      </button>

      {isOpen && (
        <div
          role="dialog"
          aria-label="Notifications"
          className="fixed inset-x-3 top-[76px] z-50 flex max-h-[min(560px,calc(100vh-96px))] flex-col overflow-hidden rounded-xl border border-[#9ED4C8] bg-white shadow-xl sm:absolute sm:inset-x-auto sm:right-0 sm:top-full sm:mt-2 sm:w-[400px]"
        >
          <div className="flex items-center justify-between gap-3 border-b border-[#9ED4C8] px-4 py-3">
            <div className="min-w-0">
              <h2 className="text-sm font-semibold text-[#0E2A2A]">
                Notifications
              </h2>
              <p className="text-[11px] text-slate-500">
                {unreadCount > 0
                  ? `${unreadCount} unread risk alert${unreadCount === 1 ? '' : 's'}`
                  : 'You are all caught up'}
              </p>
            </div>

            <div className="flex shrink-0 items-center gap-1">
              <button
                type="button"
                onClick={loadNotifications}
                disabled={isLoading}
                aria-label="Refresh notifications"
                title="Refresh"
                className="flex h-7 w-7 items-center justify-center rounded-md text-slate-500 hover:bg-[#CDEFE6] hover:text-[#0B6B63] disabled:opacity-50"
              >
                <RefreshCw
                  className={`h-3.5 w-3.5 ${isLoading ? 'animate-spin' : ''}`}
                />
              </button>

              <button
                type="button"
                onClick={() => markRead(items.map((item) => item.key))}
                disabled={unreadCount === 0}
                className="inline-flex items-center gap-1 rounded-md px-2 py-1.5 text-[11px] font-semibold text-[#0B6B63] hover:bg-[#CDEFE6] disabled:cursor-not-allowed disabled:text-slate-400 disabled:hover:bg-transparent"
              >
                <CheckCheck className="h-3.5 w-3.5" />
                Mark all read
              </button>
            </div>
          </div>

          <div className="flex gap-1 border-b border-[#CDEFE6] bg-[#EAF8F3] px-3 py-2">
            {(['all', 'unread'] as const).map((tab) => (
              <button
                key={tab}
                type="button"
                onClick={() => setFilter(tab)}
                aria-pressed={filter === tab}
                className={`rounded-md px-3 py-1 text-xs font-semibold capitalize ${
                  filter === tab
                    ? 'bg-[#0B6B63] text-white'
                    : 'text-slate-600 hover:bg-[#CDEFE6]'
                }`}
              >
                {tab}
                {tab === 'unread' && unreadCount > 0 ? ` (${unreadCount})` : ''}
              </button>
            ))}
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto">
            {isLoading && items.length === 0 ? (
              <div className="flex items-center justify-center gap-2 px-4 py-10 text-xs text-slate-500">
                <RefreshCw className="h-4 w-4 animate-spin text-[#0B6B63]" />
                Loading notifications...
              </div>
            ) : hasError && items.length === 0 ? (
              <div className="flex flex-col items-center gap-2 px-6 py-10 text-center">
                <AlertCircle className="h-6 w-6 text-[#CC1F2E]" />
                <p className="text-sm font-semibold text-[#0E2A2A]">
                  Could not load notifications
                </p>
                <button
                  type="button"
                  onClick={loadNotifications}
                  className="rounded-md border border-[#0B6B63] px-3 py-1.5 text-xs font-semibold text-[#0B6B63] hover:bg-[#CDEFE6]"
                >
                  Try again
                </button>
              </div>
            ) : visibleItems.length === 0 ? (
              <div className="flex flex-col items-center gap-2 px-6 py-10 text-center">
                <span className="flex h-10 w-10 items-center justify-center rounded-full bg-[#CDEFE6] text-[#0B6B63]">
                  <BellOff className="h-5 w-5" />
                </span>
                <p className="text-sm font-semibold text-[#0E2A2A]">
                  {filter === 'unread'
                    ? 'No unread notifications'
                    : 'No notifications'}
                </p>
                <p className="max-w-[260px] text-xs text-slate-500">
                  {monitoredProjects.length === 0
                    ? 'Connect a repository to start receiving risk alerts.'
                    : 'Active risk alerts from your projects will appear here.'}
                </p>
              </div>
            ) : (
              <ul className="divide-y divide-[#CDEFE6]">
                {visibleItems.map((item) => {
                  const style = severityStyles[item.severity];
                  const Icon = style.icon;
                  const isRead = readKeys.has(item.key);

                  return (
                    <li key={item.key}>
                      <button
                        type="button"
                        onClick={() => handleOpenItem(item)}
                        className={`flex w-full items-start gap-3 px-4 py-3 text-left hover:bg-[#EAF8F3] ${
                          isRead ? '' : 'bg-[#EAF8F3]/60'
                        }`}
                      >
                        <span
                          className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${style.wrap}`}
                        >
                          <Icon className="h-4 w-4" />
                        </span>

                        <span className="min-w-0 flex-1">
                          <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
                            <span
                              className={`rounded border px-1.5 py-0.5 text-[10px] font-semibold ${style.badge}`}
                            >
                              {style.label}
                            </span>
                            <span className="truncate text-[11px] font-medium text-slate-500">
                              {formatType(item.type)}
                            </span>
                          </span>

                          <span
                            className={`mt-1 block break-words text-[13px] leading-snug text-[#0E2A2A] ${
                              isRead ? 'font-normal' : 'font-semibold'
                            }`}
                          >
                            {item.message}
                          </span>

                          <span className="mt-1 flex items-center gap-2 text-[11px] text-slate-500">
                            <span className="truncate">{item.projectName}</span>
                            {item.evaluatedAt && (
                              <>
                                <span aria-hidden="true">•</span>
                                <span className="shrink-0">
                                  {formatRelativeTime(item.evaluatedAt)}
                                </span>
                              </>
                            )}
                          </span>
                        </span>

                        {!isRead && (
                          <span
                            className="mt-2 h-2 w-2 shrink-0 rounded-full bg-[#CC1F2E]"
                            aria-label="Unread"
                          />
                        )}
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>

          <div className="border-t border-[#9ED4C8] bg-[#EAF8F3] px-4 py-2.5">
            <button
              type="button"
              onClick={handleViewAll}
              className="w-full rounded-md py-1.5 text-center text-xs font-semibold text-[#0B6B63] hover:bg-[#CDEFE6]"
            >
              View risk analysis
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
