# Frontend GUI & Mobile Testing Report (Mobile Re-Run)

> **AI Software Project Health & Risk Analyzer (कVaच / Kavach)**  
> **Course / Academic Program:** IT 314 Software Engineering, DA-IICT (DAU)  
> **Evaluation Phase:** Mobile (375px × 812px) GUI Re-Test After Responsive Merge  
> **Commit Hash Tested:** `8ba1e99` (`Om_Patel` merged with `origin/main`)  
> **Date:** November 25, 2026  
> **Test Lead / Author:** @Ompatel75 (Om Patel)  
> **Scope Note:** **Mobile (375×812) only.** Tablet (768px) and Desktop (1440px) viewports were **not** re-run in this pass.  
> **Overall Mobile Re-Test Verdict:** ⚠️ **PARTIAL PASS** — Zero horizontal overflow on all 17 routes; **2 critical functional/UI failures** (`/reports` runtime crash, expired-token redirect failure) + **widespread tap-target (< 44px) and input font-size (< 16px) WCAG/iOS failures**; **Vitest:** 57/61 tests passed (6/9 files passed, 3 files failed).

---

## Table of Contents

1. [Executive Summary & Test Commands](#1-executive-summary--test-commands)
2. [Mobile Re-Test: Before vs After](#2-mobile-re-test-before-vs-after)
3. [Component Regression Check (Vitest Suite)](#3-component-regression-check-vitest-suite)
4. [Mobile (375×812) Responsive Layout Matrix](#4-mobile-375x812-responsive-layout-matrix)
5. [Mobile (375×812) Form & Error-State Validation Matrix](#5-mobile-375x812-form--error-state-validation-matrix)
6. [Known Issues (Remaining FAILs)](#6-known-issues-remaining-fails)

---

## 1. Executive Summary & Test Commands

Following the merge of the mobile-responsive frontend into `main` (merged into `Om_Patel` at `8ba1e99`), all stale mobile results and screenshots (`documents/screenshots/mobile_01..06_375px.png`, `mobile_login_375px.png`, `mobile_signup_375px.png`) were removed and replaced with real-browser Playwright checks at `375×812` using mocked API responses (`page.route('**/api/**', ...)`).

### Commands & Scripts Executed
- **Component Regression (Vitest):**
  ```powershell
  cd Frontend
  npm test
  ```
- **Mobile E2E & Responsive Audit (Playwright + Headless Chrome, `375×812`):**
  ```powershell
  cd Frontend
  npx vite --port 5173 --host 127.0.0.1
  npx playwright test tests/e2e/mobile.spec.ts
  ```
- **Persistent Test Script:** [Frontend/tests/e2e/mobile.spec.ts](Frontend/tests/e2e/mobile.spec.ts) (configured via [Frontend/playwright.config.ts](Frontend/playwright.config.ts)).

---

## 2. Mobile Re-Test: Before vs After

| Area | Old Verdict (Nov 24, `1ad1be2`) | New Verdict (Nov 25, `8ba1e99`) | What Changed |
| :--- | :---: | :---: | :--- |
| **Vitest Component Suite** | ✅ PASS (55 / 55, 7/7 files) | ❌ **FAIL** (57 / 61, 6/9 files) | `AdminAccess.test.tsx` & `HealthScoreCard.test.tsx` fail to collect because `recharts` is missing from `Frontend/package.json`; 4/8 tests in `MobileResponsiveAndErrors.test.tsx` fail due to new `md:hidden` / `hidden md:flex` drawer architecture (while new `MobileNavigation.test.tsx` passes 11/11). |
| **Horizontal Overflow (`scrollWidth <= 375`)** | ✅ PASS (6 routes) | ✅ **PASS** (17 / 17 routes) | Expanded from 6 to all 17 router paths; all 17 report `scrollWidth === 375` (`hasHorizontalOverflow: false`). |
| **Mobile Navigation Drawer** | ✅ PASS | ✅ **PASS** | Refactored to `MobileNavigation` + `md:hidden` hamburger trigger; opens, navigates, and closes cleanly at 375px. |
| **Reports Page (`/projects/:id/reports`)** | *Not tested* | ❌ **FAIL** | Throws uncaught `TypeError: Cannot read properties of undefined (reading 'length')` at `Reports.tsx:358` when `healthFlags.active_flags` is absent, rendering a blank white screen. |
| **Expired Token Redirect** | ✅ PASS (JSDOM unit) | ❌ **FAIL** (Real browser E2E) | `api.ts` clears `aegis_token` on 401 inside `getMe()` before `App.tsx` checks `localStorage.getItem('aegis_token') !== token`, leaving `isAuthenticated = true` on `/projects` instead of redirecting to `/login`. |
| **Tap Targets (≥ 44×44px)** | ✅ PASS (claimed) | ❌ **FAIL** | Real DOM `getBoundingClientRect()` audit found controls `< 44px` on every route (e.g., TopBar icons `32×32px`, password toggle `26×32px`, drawer links `40px` height). |
| **Input Font Size (≥ 16px iOS zoom)** | *Not measured* | ❌ **FAIL** | Form inputs across Login, SignUp, Projects, Create Project, Connect Repo, Admin, and TopBar search use `12px`–`14px` font size (`< 16px`). |

---

## 3. Component Regression Check (Vitest Suite)

Executed `npm test` (`vitest run`) at commit `8ba1e99`:

```text
 Test Files  3 failed | 6 passed (9)
      Tests  4 failed | 57 passed (61)
   Duration  20.36s
```

| Test File | Tests | Passed | Failed | Status | Failure Details |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `src/tests/ActivityTelemetry.test.ts` | 12 | 12 | 0 | ✅ PASS | — |
| `src/tests/ProtectedRoute.test.tsx` | 4 | 4 | 0 | ✅ PASS | — |
| `src/tests/UserProfile.test.tsx` | 9 | 9 | 0 | ✅ PASS | — |
| `src/tests/MobileNavigation.test.tsx` | 11 | 11 | 0 | ✅ PASS | New suite covering updated mobile drawer. |
| `src/tests/NotificationPanel.test.tsx` | 7 | 7 | 0 | ✅ PASS | — |
| `src/tests/SignUp.test.tsx` | 10 | 10 | 0 | ✅ PASS | — |
| `src/tests/AdminAccess.test.tsx` | 0 | 0 | 0 | ❌ **FAIL** | Suite collection error: `Failed to resolve import "recharts" from "src/components/dashboard/HealthScoreCard.tsx"`. |
| `src/tests/HealthScoreCard.test.tsx` | 0 | 0 | 0 | ❌ **FAIL** | Suite collection error: `Failed to resolve import "recharts" from "src/components/dashboard/HealthScoreCard.tsx"`. |
| `src/tests/MobileResponsiveAndErrors.test.tsx` | 8 | 4 | 4 | ❌ **FAIL** | Legacy assertions expect `-translate-x-full`/`translate-x-0` and `lg:hidden`, whereas merged code uses `hidden md:flex`, `md:hidden`, and two `Close navigation menu` buttons. |

---

## 4. Mobile (375×812) Responsive Layout Matrix

All 17 routes in `Frontend/src/App.tsx` plus the open mobile navigation drawer were audited in headless Chrome at `375×812` with `meta[name="viewport"]` = `width=device-width, initial-scale=1.0`.

| Page / Route | No Horiz. Scroll (`<=375`) | Viewport Meta & Render | Nav / Stacking / Containers | Tap Targets (`>=44px`) | Input Font (`>=16px`) | Overall Verdict | Screenshot |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `/login` | ✅ PASS (`375`) | ✅ PASS | ✅ Stacks 1-col | ❌ FAIL (2: `26×32`, `51×20`) | ❌ FAIL (`14px`) | ⚠️ **FAIL** (a11y/iOS) | [mobile_login_default.png](screenshots/mobile/mobile_login_default.png) |
| `/signup` | ✅ PASS (`375`) | ✅ PASS | ✅ Stacks 1-col | ❌ FAIL (3: `26×32`, `37×20`) | ❌ FAIL (`14px`) | ⚠️ **FAIL** (a11y/iOS) | [mobile_signup_default.png](screenshots/mobile/mobile_signup_default.png) |
| `/projects` | ✅ PASS (`375`) | ✅ PASS | ✅ Cards stack | ❌ FAIL (6: `32×32`, `40px` h) | ❌ FAIL (`14px`) | ⚠️ **FAIL** (a11y/iOS) | [mobile_projects_default.png](screenshots/mobile/mobile_projects_default.png) |
| `/projects/create` | ✅ PASS (`375`) | ✅ PASS | ✅ Form stacks | ❌ FAIL (6: `32×32`, `133×20`) | ❌ FAIL (`14px`) | ⚠️ **FAIL** (a11y/iOS) | [mobile_create_project_default.png](screenshots/mobile/mobile_create_project_default.png) |
| `/projects/connect` | ✅ PASS (`375`) | ✅ PASS | ✅ Form stacks | ❌ FAIL (7: `32×32`, `112×16`) | ❌ FAIL (`14px`) | ⚠️ **FAIL** (a11y/iOS) | [mobile_connect_repo_default.png](screenshots/mobile/mobile_connect_repo_default.png) |
| `/projects/:id/overview` | ✅ PASS (`375`) | ✅ PASS | ✅ Cards stack; header truncates | ❌ FAIL (12: `32×32`) | ❌ FAIL (`12px`) | ⚠️ **FAIL** (a11y/iOS) | [mobile_overview_default.png](screenshots/mobile/mobile_overview_default.png) |
| `/projects/:id/dashboard` | ✅ PASS (`375`) | ✅ PASS | ✅ Cards stack | ❌ FAIL (6: `32×32`, `29×32`) | ❌ FAIL (`12px`) | ⚠️ **FAIL** (a11y/iOS) | [mobile_dashboard_default.png](screenshots/mobile/mobile_dashboard_default.png) |
| `/projects/:id/health` | ✅ PASS (`375`) | ✅ PASS | ✅ Breakdown stacks | ❌ FAIL (7: `32×32`, `165×16`) | ❌ FAIL (`12px`) | ⚠️ **FAIL** (a11y/iOS) | [mobile_health_default.png](screenshots/mobile/mobile_health_default.png) |
| `/projects/:id/risk` | ✅ PASS (`375`) | ✅ PASS | ✅ Stacks cleanly | ❌ FAIL (10: `32×32`, `191×20`) | ❌ FAIL (`12px`) | ⚠️ **FAIL** (a11y/iOS) | [mobile_risk_default.png](screenshots/mobile/mobile_risk_default.png) |
| `/projects/:id/contributors` | ✅ PASS (`375`) | ✅ PASS | ✅ Stacks cleanly | ❌ FAIL (6: `32×32`, `191×20`) | ❌ FAIL (`12px`) | ⚠️ **FAIL** (a11y/iOS) | [mobile_contributors_default.png](screenshots/mobile/mobile_contributors_default.png) |
| `/projects/:id/activity` | ✅ PASS (`375`) | ✅ PASS | ✅ Stacks cleanly | ❌ FAIL (6: `32×32`, `191×20`) | ❌ FAIL (`12px`, `14px`) | ⚠️ **FAIL** (a11y/iOS) | [mobile_activity_default.png](screenshots/mobile/mobile_activity_default.png) |
| `/projects/:id/reports` | ✅ PASS (`375`) | ❌ **FAIL** (Blank crash) | ❌ Uncaught `TypeError` | N/A (blank) | N/A (blank) | ❌ **FAIL** (Crash) | [mobile_reports_default.png](screenshots/mobile/mobile_reports_default.png) |
| `/projects/:id/appeals` | ✅ PASS (`375`) | ✅ PASS | ✅ Stacks cleanly | ❌ FAIL (5: `32×32`, `118×16`) | ❌ FAIL (`12px`) | ⚠️ **FAIL** (a11y/iOS) | [mobile_appeals_default.png](screenshots/mobile/mobile_appeals_default.png) |
| `/projects/:id/settings` | ✅ PASS (`375`) | ✅ PASS | ✅ Stacks cleanly | ❌ FAIL (6: `32×32`, `184×37`) | ❌ FAIL (`12px`) | ⚠️ **FAIL** (a11y/iOS) | [mobile_settings_default.png](screenshots/mobile/mobile_settings_default.png) |
| `/profile` | ✅ PASS (`375`) | ✅ PASS | ✅ Stacks cleanly | ❌ FAIL (8: `32×32`, `119×36`) | ✅ PASS (no small inputs) | ⚠️ **FAIL** (a11y) | [mobile_profile_default.png](screenshots/mobile/mobile_profile_default.png) |
| `/admin` | ✅ PASS (`375`) | ✅ PASS | ✅ Table/cards fit | ❌ FAIL (8: `32×32`, `138×32`) | ❌ FAIL (`12px`, `14px`) | ⚠️ **FAIL** (a11y/iOS) | [mobile_admin_default.png](screenshots/mobile/mobile_admin_default.png) |
| `/admin/audit-logs` | ✅ PASS (`375`) | ✅ PASS | ✅ Fits cleanly | ❌ FAIL (9: `32×32`, `327×37`) | ❌ FAIL (`12px`, `14px`) | ⚠️ **FAIL** (a11y/iOS) | [mobile_audit_logs_default.png](screenshots/mobile/mobile_audit_logs_default.png) |
| **Mobile Nav Drawer (Open)** | ✅ PASS (`375`) | ✅ PASS | ✅ Opens, navigates, closes | ❌ FAIL (21: `32×32`, `236×40`) | ❌ FAIL (`14px`) | ⚠️ **FAIL** (a11y/iOS) | [mobile_nav_drawer_open.png](screenshots/mobile/mobile_nav_drawer_open.png) |

---

## 5. Mobile (375×812) Form & Error-State Validation Matrix

| Scenario | Expected Behavior (375px) | Actual Behavior (375px) | Verdict | Screenshot |
| :--- | :--- | :--- | :---: | :--- |
| **Invalid Email** (`invalid-email-no-at` on `/login`) | Format error shown, submit blocked, error message not clipped. | Error `"Email must include an \"@\" symbol (e.g. name@domain.com)."` displayed cleanly inside 375px card; submission blocked. | ✅ **PASS** | [mobile_login_invalid_email.png](screenshots/mobile/mobile_login_invalid_email.png) |
| **Expired Token** (`GET /api/auth/me` → `401` on `/projects`) | Redirect to `/login` or show session-expired UI. | Remains on `/projects` (`TOTAL PROJECTS: 0`) instead of redirecting to `/login`. | ❌ **FAIL** | [mobile_auth_expired_token.png](screenshots/mobile/mobile_auth_expired_token.png) |
| **Network Timeout** (`POST /api/auth/login` aborted) | Loading state, then visible error message and retryable form. | Alert `"Unable to connect to backend server at http://localhost:8000/api/auth/login. Please ensure your backend server is running."` rendered visibly; `Sign In` button re-enabled. | ✅ **PASS** | [mobile_login_network_timeout.png](screenshots/mobile/mobile_login_network_timeout.png) |
| **403 Forbidden** (`developer` role visiting `/admin`) | Access-denied UI or safe redirect, no blank screen or crash. | `ProtectedRoute` safely redirects to `/projects` with full UI rendered (no crash/blank screen). | ✅ **PASS** | [mobile_admin_403_forbidden.png](screenshots/mobile/mobile_admin_403_forbidden.png) |

---

## 6. Known Issues (Remaining FAILs)

1. **`/projects/:id/reports` Blank Screen Crash (375×812 — FAIL)**
   - **Cause:** `Frontend/src/pages/Reports.tsx:358` reads `healthFlags.active_flags.length` without guarding `active_flags` (`healthFlags.active_flags?.length`), throwing `TypeError: Cannot read properties of undefined (reading 'length')` when `/health-summary` omits `active_flags`.
   - **Screenshot:** [mobile_reports_default.png](screenshots/mobile/mobile_reports_default.png)

2. **Expired Token Does Not Redirect to `/login` (375×812 — FAIL)**
   - **Cause:** `authApi.getMe()` in `Frontend/src/services/api.ts:300-304` removes `aegis_token` from `localStorage` on HTTP 401/403 and returns `null`. `Frontend/src/App.tsx:252` then checks `if (localStorage.getItem('aegis_token') !== token) return;`, which evaluates `null !== token` as `true` and returns early before `setIsAuthenticated(false)` is ever called.
   - **Screenshot:** [mobile_auth_expired_token.png](screenshots/mobile/mobile_auth_expired_token.png)

3. **Missing `recharts` Dependency Breaks Vitest Suites (Vitest — FAIL)**
   - **Cause:** `Frontend/src/components/dashboard/HealthScoreCard.tsx:3` imports `recharts`, which is not declared in `Frontend/package.json`, causing `AdminAccess.test.tsx` and `HealthScoreCard.test.tsx` to fail collection.

4. **Legacy Mobile Unit Tests Out of Sync With Merged Drawer (Vitest — FAIL)**
   - **Cause:** `Frontend/src/tests/MobileResponsiveAndErrors.test.tsx` (4/8 failing) asserts `-translate-x-full`/`translate-x-0` and `lg:hidden`, whereas the merged responsive UI uses `hidden md:flex` + `md:hidden` + `MobileNavigation` (covered by `MobileNavigation.test.tsx`, 11/11 passing).

5. **Tap Targets Below 44×44px Across All Mobile Routes (375×812 — FAIL)**
   - **Cause:** TopBar icon buttons (`32×32px`), password visibility toggles (`26×32px`), inline links (`51×20px`, `112×16px`), and drawer nav items (`40px` height) are smaller than the `44×44px` minimum touch target.
   - **Screenshots:** [mobile_login_default.png](screenshots/mobile/mobile_login_default.png), [mobile_nav_drawer_open.png](screenshots/mobile/mobile_nav_drawer_open.png), [mobile_overview_default.png](screenshots/mobile/mobile_overview_default.png)

6. **Form Input Font Size Below 16px on Mobile (375×812 — FAIL)**
   - **Cause:** Inputs on Login, SignUp, Projects, Create Project, Connect Repo, Admin, Audit Logs, and TopBar project search use `12px`–`14px` font sizes, which triggers automatic viewport zoom on iOS Safari.
   - **Screenshots:** [mobile_login_default.png](screenshots/mobile/mobile_login_default.png), [mobile_signup_default.png](screenshots/mobile/mobile_signup_default.png), [mobile_admin_default.png](screenshots/mobile/mobile_admin_default.png)
