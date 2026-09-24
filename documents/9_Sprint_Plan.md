# Project Plan & Sprint Plan

> This file is the consolidated project plan. Requirements and acceptance criteria are defined in the companion files; story IDs in this plan must not be renumbered.

## 1. Project overview

The platform connects to a GitHub repository and configured sprint/task data, collects commits, pull requests, issues, and project activity, computes transparent health/risk indicators, and uses GenAI to explain findings and produce status reports and recommendations.

### Problem
Project activity is spread across repositories, PRs, issues, contributors, and sprint artifacts. Team leads and project managers must inspect these sources manually to understand bottlenecks, stale work, workload imbalance, and delivery risk.

### Objectives
- Consolidate relevant GitHub and sprint activity in a project dashboard.
- Identify potential bottlenecks, possible workload imbalance, stale issues, and indicative schedule risk.
- Provide explainable health indicators and advisory recommendations.
- Generate project status reports with dashboard access, scheduled email/Slack delivery, and PDF export.
- Protect individual data through authentication and role-based access, and maintain audit records.

## 2. Product scope

### Core product capabilities
- GitHub repository connection and commit, PR, and issue analysis.
- Sprint/task activity from configured GitHub Projects and/or milestones, where source data is sufficient.
- Bottleneck/blocker detection, possible workload imbalance, stale issue detection, schedule-risk indicator, and project-health evaluation.
- GenAI explanations, actionable advisory recommendations, and status reports.
- Project health dashboard.

### Supporting capabilities included in the project
- Authentication and role-based access control (RBAC).
- Audit logs (NFR-10).
- PDF report export.
- Scheduled report delivery through the dashboard, email, and Slack.
- Project/user administration, secure integration configuration, feedback/appeal workflow, and basic error handling.

### Product capabilities

The platform combines repository and sprint activity analysis, transparent health and risk indicators, AI-generated explanations and recommendations, status reports, and a unified dashboard. Supporting capabilities include authentication, role-based access, audit logging, PDF export, scheduled email/Slack report delivery, project/user administration, secure integration configuration, and feedback/appeal handling.

## 3. Stakeholders (six groups only)

| # | Stakeholder group | Primary use |
|---|---|---|
| 1 | Individual Developers | View own permitted flags, explanations, and appeal status. |
| 2 | Code Reviewers / Senior Engineers | Inspect PR review queues and review bottlenecks. |
| 3 | Engineering / Team Leads | Monitor health, activity indicators, and recommendations. |
| 4 | Scrum Masters / Agile Coaches | Review sprint progress, velocity, and schedule indicators. |
| 5 | Project Managers | Review project health, reports, delivery risks, and recommendations. |
| 6 | System Administrators / DevOps Engineers | Manage accounts, permissions, integrations, credentials, auditability, and lifecycle. |

Product Owner responsibilities are included under Project Managers; security/InfoSec responsibilities are included under System Administrators / DevOps Engineers.

## 4. Proposed technology architecture

The exact implementation may be adjusted to the team's skills and deployment constraints. The architecture should remain modular, practical for a student team, and suitable for the expected project workload.

| Layer | Proposed choice / responsibility |
|---|---|
| Frontend | Next.js/React dashboard and report screens |
| Backend | FastAPI service for project setup, data synchronization, metrics, permissions, and report APIs |
| Database | MongoDB for project configuration, normalized activity snapshots, indicators, reports, and audit events |
| Source integration | GitHub API (and webhooks if feasible) for repository, PR, issue, and project data |
| Analysis | Deterministic metric/rule layer for measurable indicators and risk thresholds |
| GenAI | Configured LLM provider for explanations, report narrative, and recommendations grounded in computed metrics |
| Workflow orchestration | Lightweight service flow; use LangChain/LangGraph only if it simplifies the bounded explanation/report workflow. They are implementation choices, not product features. |
| Delivery | Dashboard first; configured email/Slack report delivery; PDF generation |
| Hosting | Low-cost/free-tier deployment selected by the team; no GPU requirement |

## 5. High-level architecture and workflow

```text
User signs in
    ↓
Create / select project (role and permissions checked)
    ↓
Connect GitHub repository + configure sprint/task source
    ↓
Validate access and synchronize source data
    ↓
Store normalized snapshots + last-sync/error metadata
    ↓
Calculate metrics and rule-based indicators
    ↓
Evaluate bottlenecks, workload imbalance, stale issues, schedule risk, health summary
    ↓
Generate grounded explanations, recommendations, and status report
    ↓
Dashboard ── PDF export
    ├──────── Email delivery (if configured)
    └──────── Slack report delivery (if configured)
```

## 6. Metric and interpretation principles

1. **Transparent metrics first:** Calculate measurable values from source data before asking the LLM to explain them.
2. **No unsupported inference:** Do not infer uncommitted work, exact hours, personal capacity, or guaranteed delivery dates from GitHub activity.
3. **Visible freshness:** Show synchronization time and identify missing or stale data.
4. **Insufficient-data behavior:** If required inputs are missing, display “insufficient data” instead of manufacturing a score or risk result.
5. **Human decision-making:** Flags and recommendations are advisory. The system does not automatically reassign tasks, modify issues, or change repository contents.
6. **Health summary:** Use a documented, explainable summary of selected indicators and expose contributing factors and thresholds.

## 7. User-story and epic structure

| Epic | Stories | Capability |
|---|---|---|
| E1 — Data Collection & Project Setup | US-01–US-05 | Source data, project configuration, contributor mapping |
| E2 — Health & Risk Analysis | US-06–US-10 | Indicators and thresholds |
| E3 — Explanations, Reports & Recommendations | US-11–US-15 | Explainability, reports, recommendations, delivery, PDF |
| E4 — Dashboard & User Feedback | US-16–US-17 | Dashboard and appeals |
| E5 — Access Control & Administration | US-18–US-21 | RBAC, integrations, authentication, lifecycle |

See `6_User_Stories_and_Acceptance_Criteria.md` and `7_Product_Backlog_Story_Points_Priority.md` for canonical story definitions and estimates.

## 8. Sprint plan

The following is a proposed 5-sprint sequence. Story point capacity must be adjusted to the actual team's availability; the 110-point backlog is not a promise that all work fits a fixed calendar.

### Sprint 1 — Foundation and project access
**Goal:** Establish the secure project foundation and connect the source system.

**Candidate stories:** US-20, US-19, US-05, US-01.  
**Deliverables:** Authentication and role assignment; basic RBAC foundation; GitHub connection configuration; project creation and contributor mapping; initial commit ingestion; basic error/secret handling.  
**Exit checks:** Users can sign in; authorized user can configure a project and connect a repository; commit data can be retrieved with clear failure handling.

### Sprint 2 — Activity ingestion and sprint data
**Goal:** Complete the primary project activity data pipeline.

**Candidate stories:** US-02, US-03, US-04.  
**Deliverables:** PR and issue retrieval; sprint/task data ingestion from configured GitHub Projects/milestones; synchronization timestamps; basic activity views.  
**Exit checks:** Commit/PR/issue/sprint data is displayed for a test project; missing or unsupported source data is clearly labeled.

### Sprint 3 — Metrics, risks, and dashboard
**Goal:** Turn source activity into transparent project-health indicators.

**Candidate stories:** US-06, US-07, US-08, US-09, US-10, US-16.  
**Deliverables:** Bottleneck rules, activity-based workload imbalance indicator, stale-issue rules, indicative schedule-risk logic, configurable thresholds, dashboard summary.  
**Exit checks:** Each indicator can be traced to input metrics; thresholds can be adjusted by authorized users; insufficient data is handled; no automatic actions are taken.

### Sprint 4 — Explanations, recommendations, and reports
**Goal:** Add bounded GenAI assistance and report workflows.

**Candidate stories:** US-11, US-12, US-13, US-14, US-15.  
**Deliverables:** Grounded explanations; advisory recommendations; status report generation; scheduled dashboard/email/Slack delivery; PDF export.  
**Exit checks:** Generated content references computed evidence; failed external delivery is visible; report/export respects permissions; dashboard remains available when optional channels are not configured.

### Sprint 5 — Feedback, administration, hardening, and release
**Goal:** Complete user feedback and lifecycle controls, validate the integrated system, and prepare the demo.

**Candidate stories:** US-17, US-18, US-21; remaining integration and quality work.  
**Deliverables:** Feedback/appeal review flow; final RBAC checks; project archive/delete and user deactivation; audit logging; integration/system tests; deployment and documentation.  
**Exit checks:** Role-based access tests pass; affected users can view appeal status; deactivated users lose access; audit events are retrievable; end-to-end demo works within resource limits.

## 9. Sprint planning rules

- Confirm story acceptance criteria and dependencies before committing work.
- Break stories into tasks and estimate based on team capacity and uncertainty.
- Keep one canonical story ID per backlog item; do not create duplicate IDs for the same capability.
- Review scope changes as a group and update the FR → US → Epic → Sprint mapping together.
- At sprint end, record completed work, carryover, tests, review outcomes, and retrospective actions.

## 10. GitHub development workflow

```text
Product Backlog → Sprint Backlog → GitHub Issue → Feature Branch
→ Implementation → Pull Request → Review → Tests → Merge → Sprint Review
```

Suggested branch naming: `feature/us-XX-short-description` or `fix/us-XX-short-description`.

Contribution practices:
- Use issues to track planned work and link PRs to issues.
- Commit work under the contributor who performed it.
- Use pull requests and reviews for integration.
- Keep acceptance criteria and test evidence attached to the issue/PR where practical.

## 11. Testing strategy

### Unit tests
- Repository validation and data normalization.
- Commit/PR/issue/sprint metric calculations.
- Stale-issue and bottleneck rules.
- Workload indicator and schedule-risk logic.
- Health-summary and threshold validation.
- Permission checks and report formatting.

### Integration tests
- Frontend ↔ backend.
- Backend ↔ GitHub API.
- Backend ↔ database.
- Backend ↔ configured LLM provider.
- Report service ↔ PDF generation, email, and Slack delivery adapters.

### System and acceptance tests
1. Sign in and create/select a project.
2. Connect and synchronize a test GitHub repository.
3. Inspect commit, PR, issue, and sprint data.
4. Calculate indicators and view explanations.
5. Generate a report and recommendations.
6. View dashboard, export PDF, and test configured delivery channels.
7. Verify role permissions, appeal flow, audit logs, and account/project lifecycle.

### Important edge cases
- Invalid or inaccessible repository; revoked token; rate limit; empty repository; no issues/PRs; incomplete sprint data; stale cache; partial sync; database unavailable; LLM unavailable or malformed output; email/Slack delivery failure; unauthorized access; deleted/deactivated user; and network interruption.

## 12. Security, privacy, and auditability

- Keep secrets on the server and never expose them in client bundles or logs.
- Use least-privilege GitHub scopes and document token revocation.
- Enforce authorization in backend endpoints, not only in the UI.
- Restrict individual-level metrics and appeal details to permitted roles.
- Record important configuration, access, analysis, report, and lifecycle events under NFR-10.
- Document audit-log access and retention policy; do not log credentials or sensitive token values.

## 13. Deployment and resource constraints

- Use the team's selected low-cost/free-tier frontend, backend, and database services.
- Store configuration/secrets in environment variables or a managed secret store.
- Document provider quotas, refresh frequency, dataset assumptions, and LLM usage limits.
- Provide graceful behavior when an external provider is unavailable.
- The implementation is designed for practical, low-cost hosting and standard application infrastructure.

## 14. Milestones

| Milestone | Expected output |
|---|---|
| M1 | Scope, six stakeholders, elicitation plan, requirements, stories, backlog, and epics aligned |
| M2 | Architecture and Sprint 1 foundation |
| M3 | GitHub and sprint-data ingestion pipeline |
| M4 | Metrics, risk indicators, and dashboard |
| M5 | Explanations, recommendations, reports, delivery, and PDF export |
| M6 | Access/appeal/audit completion, tests, and deployment |
| M7 | Final documentation, presentation, and end-to-end demonstration |

## 15. Final MVP checklist

### Core product
- [ ] GitHub repository connection, commit, PR, issue, and sprint activity.
- [ ] Bottleneck, workload imbalance, stale issue, and schedule-risk indicators.
- [ ] Transparent project-health summary.
- [ ] AI explanations, recommendations, and status reports.
- [ ] Unified dashboard.

### Supporting capabilities
- [ ] Authentication and RBAC.
- [ ] Audit logs and secure integration configuration.
- [ ] PDF report export.
- [ ] Scheduled dashboard/email/Slack report delivery.
- [ ] Feedback/appeal and project/user lifecycle management.

### Quality and delivery
- [ ] Error handling, freshness indicators, and insufficient-data behavior.
- [ ] Unit, integration, and end-to-end tests.
- [ ] Resource limits and secrets reviewed.
- [ ] Demo workflow and documentation completed.

## 16. Canonical project principle

> **Collect reliable source data → calculate transparent indicators → explain evidence with GenAI → present advisory recommendations and reports → keep decisions with people.**
