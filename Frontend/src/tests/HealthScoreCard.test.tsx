import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { HealthScoreCard } from '../components/dashboard/HealthScoreCard';
import type { HealthGaugeData } from '../services/metricService';

const mockData: HealthGaugeData = {
  score: 82,
  status: 'Good',
  summaryStatement: 'Project health is currently in good standing across all metrics.',
  lastSyncedAt: '2026-11-25T00:00:00Z',
  dataFreshness: 'fresh',
  factors: [
    { label: 'Review Latency', score: 85, weight: 0.3, status: 'Good' },
    { label: 'Workload Balance', score: 78, weight: 0.25, status: 'Good' },
  ],
  flags: { total: 1, high: 0, medium: 1, low: 0 },
};

describe('HealthScoreCard — Gauge Layout & Separate Vertical Flow', () => {
  it('renders score, status, factors, and summary statement', () => {
    render(<HealthScoreCard data={mockData} isLoading={false} error={null} />);

    // Header and status badge
    expect(screen.getByText('Overall Health Score')).toBeInTheDocument();
    expect(screen.getByText('Good')).toBeInTheDocument();

    // Score display inside gauge
    expect(screen.getByText('82')).toBeInTheDocument();
    expect(screen.getByText('/ 100')).toBeInTheDocument();

    // Explanatory paragraph
    expect(
      screen.getByText('Project health is currently in good standing across all metrics.')
    ).toBeInTheDocument();

    // Contributing factors
    expect(screen.getByText('Review Latency')).toBeInTheDocument();
    expect(screen.getByText('Workload Balance')).toBeInTheDocument();
  });

  it('gauge container has matching dimensions and does not overflow into explanatory text', () => {
    const { container } = render(
      <HealthScoreCard data={mockData} isLoading={false} error={null} />
    );

    // Gauge container
    const gaugeContainer = container.querySelector('.max-w-\\[180px\\]');
    expect(gaugeContainer).toBeInTheDocument();
    expect(gaugeContainer).toHaveClass('relative');
    expect(gaugeContainer).toHaveClass('mx-auto');
    expect(gaugeContainer).toHaveClass('w-full');
    expect(gaugeContainer).toHaveClass('h-[110px]');

    // ResponsiveContainer style height must match container height (110px) to prevent 180px overflow
    const rechartsContainer = gaugeContainer?.querySelector('.recharts-responsive-container');
    expect(rechartsContainer).toBeInTheDocument();
    expect(rechartsContainer).toHaveStyle({ height: '110px' });

    // Score label overlay is positioned at bottom of the arch with pointer-events-none
    const scoreLabel = gaugeContainer?.querySelector('.absolute.inset-x-0.bottom-0');
    expect(scoreLabel).toBeInTheDocument();
    expect(scoreLabel).toHaveClass('pointer-events-none');

    // Explanatory paragraph follows gauge container in separate vertical flow with mt-3 spacing
    const summary = screen.getByText(
      'Project health is currently in good standing across all metrics.'
    );
    expect(summary).toHaveClass('mt-3');
    expect(summary.tagName.toLowerCase()).toBe('p');
  });

  it('renders loading skeleton when isLoading is true', () => {
    const { container } = render(
      <HealthScoreCard data={null} isLoading={true} error={null} />
    );

    expect(container.querySelector('.animate-pulse')).toBeInTheDocument();
    expect(screen.queryByText('Overall Health Score')).not.toBeInTheDocument();
  });

  it('renders error message when error is provided', () => {
    render(
      <HealthScoreCard data={null} isLoading={false} error="Failed to fetch health score" />
    );

    expect(screen.getByText('Failed to load health score')).toBeInTheDocument();
    expect(screen.getByText('Failed to fetch health score')).toBeInTheDocument();
  });
});
