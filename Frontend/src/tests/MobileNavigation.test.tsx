/**
 * MobileNavigation.test.tsx
 *
 * Tests for the mobile drawer navigation system (Issue #205).
 * Covers: TopBar hamburger, Sidebar backdrop/close, Layout Escape-key and
 * body-scroll-lock behaviours.
 *
 * NOTE: Does NOT import react-router-dom (not installed in local node_modules).
 * NotificationPanel is mocked to avoid async API calls.
 */

import React from 'react';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { TopBar } from '../components/TopBar';
import { Sidebar } from '../components/Sidebar';
import { Layout } from '../components/Layout';

/* ------------------------------------------------------------------ */
/*  Mocks                                                              */
/* ------------------------------------------------------------------ */

// NotificationPanel makes async API calls; mock it so TopBar renders cleanly.
vi.mock('../components/NotificationPanel', () => ({
  NotificationPanel: () => <div data-testid="notification-panel" />,
}));

/* ------------------------------------------------------------------ */
/*  Shared minimal props                                               */
/* ------------------------------------------------------------------ */

const noOp = () => {};

const minimalSidebarProps = {
  currentView: 'projects' as const,
  onNavigate: noOp,
  onLogout: noOp,
};

const minimalTopBarProps = {
  currentView: 'projects' as const,
  onNavigate: noOp,
};

const minimalLayoutProps = {
  currentView: 'projects' as const,
  onNavigate: noOp,
  onLogout: noOp,
  children: <div data-testid="page-content">Page content</div>,
};

/* ================================================================== */
/*  Test suite 1 — TopBar hamburger                                   */
/* ================================================================== */

describe('TopBar — hamburger button', () => {
  beforeEach(() => vi.clearAllMocks());

  it('calls onOpenMenu when the hamburger button is clicked', () => {
    const onOpenMenu = vi.fn();

    render(
      <TopBar
        {...minimalTopBarProps}
        onOpenMenu={onOpenMenu}
        isMenuOpen={false}
      />,
    );

    const hamburger = screen.getByRole('button', {
      name: /open navigation menu/i,
    });

    fireEvent.click(hamburger);

    expect(onOpenMenu).toHaveBeenCalledTimes(1);
  });

  it('sets aria-expanded correctly based on isMenuOpen prop', () => {
    const { rerender } = render(
      <TopBar
        {...minimalTopBarProps}
        onOpenMenu={noOp}
        isMenuOpen={false}
      />,
    );

    const hamburger = screen.getByRole('button', {
      name: /open navigation menu/i,
    });
    expect(hamburger).toHaveAttribute('aria-expanded', 'false');

    rerender(
      <TopBar
        {...minimalTopBarProps}
        onOpenMenu={noOp}
        isMenuOpen={true}
      />,
    );
    expect(hamburger).toHaveAttribute('aria-expanded', 'true');
  });
});

/* ================================================================== */
/*  Test suite 2 — Sidebar mobile drawer                              */
/* ================================================================== */

describe('Sidebar — mobile drawer', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders "Close navigation menu" buttons when isOpen is true', () => {
    render(
      <Sidebar
        {...minimalSidebarProps}
        isOpen={true}
        onClose={noOp}
      />,
    );

    // Both the backdrop and the X button have aria-label "Close navigation menu"
    const closeBtns = screen.getAllByRole('button', {
      name: /close navigation menu/i,
    });
    expect(closeBtns.length).toBeGreaterThanOrEqual(1);
  });

  it('calls onClose when the backdrop button is clicked', () => {
    const onClose = vi.fn();

    render(
      <Sidebar
        {...minimalSidebarProps}
        isOpen={true}
        onClose={onClose}
      />,
    );

    // The first "Close navigation menu" button in the DOM is the backdrop
    const [backdropBtn] = screen.getAllByRole('button', {
      name: /close navigation menu/i,
    });
    fireEvent.click(backdropBtn);

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('renders the dialog with role="dialog" when isOpen is true', () => {
    render(
      <Sidebar
        {...minimalSidebarProps}
        isOpen={true}
        onClose={noOp}
      />,
    );

    expect(
      screen.getByRole('dialog', { name: /navigation drawer/i }),
    ).toBeInTheDocument();
  });

  it('calls onClose when the X close button inside the drawer is clicked', () => {
    const onClose = vi.fn();

    render(
      <Sidebar
        {...minimalSidebarProps}
        isOpen={true}
        onClose={onClose}
      />,
    );

    // Both backdrop and X share "Close navigation menu"; click the second (X button inside drawer)
    const closeBtns = screen.getAllByRole('button', {
      name: /close navigation menu/i,
    });
    // The X close button is the last one (inside the dialog)
    const xBtn = closeBtns[closeBtns.length - 1];
    fireEvent.click(xBtn);

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('does NOT render the mobile dialog when isOpen is false', () => {
    render(
      <Sidebar
        {...minimalSidebarProps}
        isOpen={false}
        onClose={noOp}
      />,
    );

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('calls onClose when a nav item is clicked (drawer auto-close)', () => {
    const onClose = vi.fn();
    const onNavigate = vi.fn();

    render(
      <Sidebar
        {...minimalSidebarProps}
        isOpen={true}
        onClose={onClose}
        onNavigate={onNavigate}
      />,
    );

    // Find nav buttons inside the dialog (not close buttons)
    const dialog = screen.getByRole('dialog', { name: /navigation drawer/i });
    const allButtons = Array.from(dialog.querySelectorAll('button'));

    // Pick the first nav item that is not a close button
    const navItem = allButtons.find(
      (btn) =>
        !/(close navigation menu)/i.test(btn.getAttribute('aria-label') || ''),
    );

    expect(navItem).toBeDefined();
    if (navItem) fireEvent.click(navItem);

    // onClose must have been called (handleItemClick calls onClose?.())
    expect(onClose).toHaveBeenCalled();
  });
});

/* ================================================================== */
/*  Test suite 3 — Layout keyboard and scroll-lock                    */
/* ================================================================== */

describe('Layout — Escape key and body scroll lock', () => {
  afterEach(() => {
    document.body.style.overflow = '';
    vi.clearAllMocks();
  });

  it('closes the drawer when Escape is pressed while menu is open', () => {
    render(<Layout {...minimalLayoutProps} />);

    // Open drawer
    const hamburger = screen.getByRole('button', {
      name: /open navigation menu/i,
    });
    fireEvent.click(hamburger);

    expect(screen.getByRole('dialog', { name: /navigation drawer/i })).toBeInTheDocument();

    // Press Escape
    fireEvent.keyDown(window, { key: 'Escape', code: 'Escape' });

    expect(
      screen.queryByRole('dialog', { name: /navigation drawer/i }),
    ).not.toBeInTheDocument();
  });

  it('locks body scroll (overflow: hidden) when drawer is open', () => {
    render(<Layout {...minimalLayoutProps} />);

    expect(document.body.style.overflow).not.toBe('hidden');

    const hamburger = screen.getByRole('button', {
      name: /open navigation menu/i,
    });
    fireEvent.click(hamburger);

    expect(document.body.style.overflow).toBe('hidden');
  });

  it('restores body overflow when drawer is closed via Escape', () => {
    render(<Layout {...minimalLayoutProps} />);

    // Open
    const hamburger = screen.getByRole('button', {
      name: /open navigation menu/i,
    });
    fireEvent.click(hamburger);
    expect(document.body.style.overflow).toBe('hidden');

    // Close via Escape
    act(() => {
      fireEvent.keyDown(window, { key: 'Escape', code: 'Escape' });
    });

    expect(document.body.style.overflow).not.toBe('hidden');
  });
});
