# User Stories & Acceptance Criteria

> Story IDs are canonical throughout all project documents. Supporting platform capabilities (authentication, RBAC, audit logs, PDF export, and report delivery) are included; out-of-scope AI/product expansions are excluded.

---

## US-01 — View Commit History

**Functional Requirement:** FR-1  
**Primary stakeholder:** Team Lead

**User Story**

As a Team Lead, I want to view commit history from the linked GitHub repository, including author, timestamp, and available change size, to track development activity.

**Acceptance Criteria**

1. The system retrieves commits from the configured repository/branch.
2. Each record shows author, timestamp, and available change-size data.
3. The default branch is used unless configured otherwise.
4. If access fails, the system shows a clear retrieval error.

---

## US-02 — Track GitHub Pull Requests

**Functional Requirement:** FR-2  
**Primary stakeholder:** Team Lead / Code Reviewer

**User Story**

As a Team Lead / Code Reviewer, I want to track PR opening time, reviewer metadata, open duration, and merge/close status to monitor review progress.

**Acceptance Criteria**

1. Each PR shows available opening time, reviewer(s), duration, and status.
2. Open, merged, and closed states are distinguished.
3. Open duration is shown for PRs that remain open.

---

## US-03 — View GitHub Issue Information

**Functional Requirement:** FR-3  
**Primary stakeholder:** Team Lead

**User Story**

As a Team Lead, I want to view issue status, assignee, labels, and last activity to monitor the issue queue.

**Acceptance Criteria**

1. Each issue shows available status, assignee, labels, and latest activity.
2. Last-activity time can be compared with the project stale threshold.
3. The display identifies the latest available synchronization.

---

## US-04 — View Sprint Progress and Velocity

**Functional Requirement:** FR-4  
**Primary stakeholder:** Scrum Master / Agile Coach

**User Story**

As a Scrum Master / Agile Coach, I want to view planned and completed tasks and sprint velocity where supported by configured GitHub Projects/milestones.

**Acceptance Criteria**

1. Planned and completed tasks are shown when source data supports them.
2. Velocity is shown only when completed-work data is sufficient.
3. The configured project task structure is used and limitations are disclosed.
4. Displayed data reflects the latest successful synchronization.

---

## US-05 — Create and Configure a Project

**Functional Requirement:** FR-5  
**Primary stakeholder:** Team Lead / Project Manager

**User Story**

As a Team Lead / Project Manager, I want to create a project, link repositories and sprint data, and map team members to GitHub usernames for attribution.

**Acceptance Criteria**

1. Authorized users can create and configure projects.
2. Repositories and sprint data can be associated.
3. Team members can be mapped to GitHub usernames.
4. Required repository details are validated.

---

## US-06 — Identify Development Bottlenecks and Blockers

**Functional Requirement:** FR-6  
**Primary stakeholder:** Team Lead / Scrum Master

**User Story**

As a Team Lead / Scrum Master, I want to identify potential bottlenecks such as aging unreviewed PRs or work remaining in a stage, so the team can investigate slowdowns.

**Acceptance Criteria**

1. Potential bottlenecks are identified from observable activity.
2. Findings link to supporting source items/metrics where available.
3. Findings are visible only to authorized users and are described as potential.

---

## US-07 — Identify Possible Workload Imbalance

**Functional Requirement:** FR-7  
**Primary stakeholder:** Team Lead

**User Story**

As a Team Lead, I want to identify activity patterns that may indicate an uneven workload, so the team can review work distribution.

**Acceptance Criteria**

1. Available commit, PR, and task activity is compared with a configured baseline.
2. A configurable threshold controls flags.
3. The flag lists contributing activity data.
4. The interface states that activity is a proxy, not a direct workload or performance measure.

---

## US-08 — Identify Stale GitHub Issues

**Functional Requirement:** FR-8  
**Primary stakeholder:** Team Lead

**User Story**

As a Team Lead, I want to identify issues with no activity beyond a configurable period so stale work is not overlooked.

**Acceptance Criteria**

1. Issues exceeding the project threshold are flagged.
2. The threshold is configurable per project.
3. Stale and active issues are distinguishable.
4. New activity clears or recalculates the stale flag.

---

## US-09 — Identify Schedule Risk

**Functional Requirement:** FR-9  
**Primary stakeholder:** Project Manager

**User Story**

As a Project Manager, I want to view an indicative sprint/project schedule-risk indicator based on available velocity, completion, remaining work, and timeline data.

**Acceptance Criteria**

1. Risk uses available configured sprint metrics.
2. The indicator is presented as an estimate, not a guaranteed prediction.
3. The latest data timestamp and missing inputs are visible.

---

## US-10 — Configure Analysis Thresholds

**Functional Requirement:** FR-10  
**Primary stakeholder:** Team Lead / System Administrator

**User Story**

As a Team Lead / System Administrator, I want to review and adjust supported project-health thresholds to fit team context.

**Acceptance Criteria**

1. Authorized users can view and update supported thresholds.
2. Updated thresholds affect subsequent evaluations.
3. Invalid values are rejected with a clear message.

---

## US-11 — Explain Generated Flags

**Functional Requirement:** FR-11  
**Primary stakeholder:** Developer / Team Lead

**User Story**

As a Developer / Team Lead, I want to read a plain-language explanation of each flag and the data behind it.

**Acceptance Criteria**

1. Each supported flag includes an explanation.
2. The explanation names contributing metrics and source period.
3. Missing data and uncertainty are disclosed.
4. Access follows the role permissions.

---

## US-12 — Generate Project Status Report

**Functional Requirement:** FR-12  
**Primary stakeholder:** Project Manager

**User Story**

As a Project Manager, I want to generate a status report summarizing project health, progress, risks, and bottlenecks without manual compilation.

**Acceptance Criteria**

1. Report includes health summary, progress, risks, and bottlenecks.
2. Content matches the data available at generation time.
3. Report generation identifies data freshness and unavailable inputs.

---

## US-13 — Provide Actionable Recommendations

**Functional Requirement:** FR-13  
**Primary stakeholder:** Team Lead / Project Manager

**User Story**

As a Team Lead / Project Manager, I want to receive specific recommendations related to detected project conditions.

**Acceptance Criteria**

1. Recommendations address relevant active flags/risks.
2. Each recommendation explains the condition and suggested action.
3. Recommendations are advisory; the system does not automatically change assignments or repository data.

---

## US-14 — Schedule and Deliver Status Reports

**Functional Requirement:** FR-14  
**Primary stakeholder:** Project Manager

**User Story**

As a Project Manager, I want to choose report frequency and delivery destination to receive reports in the team’s workflow.

**Acceptance Criteria**

1. Daily, weekly, and end-of-sprint options are supported.
2. Dashboard, email, and Slack destinations can be selected when configured.
3. Delivery failures are recorded and shown; dashboard remains the in-app destination.

---

## US-15 — Export Project Status Report

**Functional Requirement:** FR-15  
**Primary stakeholder:** Project Manager

**User Story**

As a Project Manager, I want to export a generated report as PDF for sharing.

**Acceptance Criteria**

1. A generated report can be exported as PDF.
2. Export includes health, progress, risks, bottlenecks, and recommendations present in the report.
3. Export respects access permissions.

---

## US-16 — View Project Health Dashboard

**Functional Requirement:** FR-16  
**Primary stakeholder:** Team Lead

**User Story**

As a Team Lead, I want to view a unified dashboard of project health and its supporting indicators.

**Acceptance Criteria**

1. Dashboard presents health, bottlenecks, workload indicators, stale issues, and schedule risk.
2. The latest successful data timestamp is visible.
3. Authorized users can open supporting details.
4. Insufficient data is clearly labeled.

---

## US-17 — Submit Feedback or Appeal on a Flag

**Functional Requirement:** FR-17  
**Primary stakeholder:** Developer

**User Story**

As a Developer, I want to submit feedback or appeal a flag concerning me so relevant context can be reviewed.

**Acceptance Criteria**

1. Affected user can view the flag and explanation.
2. User can submit feedback/appeal for the flag.
3. Authorized Team Lead/admin can review and record resolution.
4. Resolution status is visible to the affected user.

---

## US-18 — Control Access to Individual Metrics

**Functional Requirement:** FR-18  
**Primary stakeholder:** System Administrator / DevOps

**User Story**

As a System Administrator / DevOps, I want to manage role-based access to individual-level project metrics.

**Acceptance Criteria**

1. Authorized roles can view permitted project and individual data.
2. Other users see only permitted aggregated information.
3. Unauthorized access is denied.

---

## US-19 — Configure GitHub and GenAI Integrations

**Functional Requirement:** FR-19  
**Primary stakeholder:** System Administrator / DevOps

**User Story**

As a System Administrator / DevOps, I want to configure the GitHub and GenAI provider connections used by the platform.

**Acceptance Criteria**

1. Authorized admin can configure and validate connections.
2. Credentials are stored server-side securely.
3. Secrets are not exposed in logs or client-side code.
4. Integration errors are surfaced clearly.

---

## US-20 — Sign Up, Log In, and Receive a Role

**Functional Requirement:** FR-20  
**Primary stakeholder:** All user roles

**User Story**

As a All user roles, I want to create an account, sign in, and receive permissions associated with an assigned role.

**Acceptance Criteria**

1. A user can create an account using the supported flow.
2. Valid credentials allow sign-in and invalid credentials are rejected.
3. Each account has a role.
4. Access is enforced according to role and project permissions.

---

## US-21 — Archive or Delete Projects and Deactivate Users

**Functional Requirement:** FR-21  
**Primary stakeholder:** System Administrator / DevOps

**User Story**

As a System Administrator / DevOps, I want to archive/delete projects and deactivate accounts to manage access and lifecycle.

**Acceptance Criteria**

1. Authorized admin can archive a project and it is no longer active.
2. Permanent deletion is distinguished from archive and requires confirmation.
3. Deactivated users cannot sign in or access project data.
