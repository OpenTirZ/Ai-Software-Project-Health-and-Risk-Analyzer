# Requirement Elicitation Techniques

## 1. Approach
Elicitation focuses on the six stakeholder groups defined in `1_Stakeholders.md`. Techniques are proposed methods for validating requirements; they are not claims that interviews or surveys have already been conducted. Findings should be recorded and used to refine thresholds, data definitions, and acceptance criteria.

## 2. Stakeholder-wise Techniques

### 2.1 Individual Developers
- **Techniques:** Interviews, short questionnaire, form.
- **Purpose:** Understand how developers interpret workload indicators, what context may be missing from GitHub activity, and what explanation/appeal workflow is understandable and fair.

### 2.2 Code Reviewers / Senior Engineers
- **Techniques:** Observation, workflow walkthrough.
- **Purpose:** Identify useful PR review metrics, review-queue bottlenecks, and context that affects turnaround time.

### 2.3 Engineering / Team Leads
- **Techniques:** Interviews, scenario-based discussion.
- **Purpose:** Validate project-health indicators, overload/bottleneck thresholds, dashboard needs, and the usefulness of recommendations.

### 2.4 Scrum Masters / Agile Coaches
- **Techniques:** Interviews, sprint-artifact analysis, brainstorming.
- **Purpose:** Clarify how the team represents sprints, planned/completed tasks, velocity, blockers, and schedule risk in GitHub Projects or milestones.

### 2.5 Project Managers
- **Techniques:** Interviews, questionnaire, report review.
- **Purpose:** Validate status-report contents, health/risk presentation, report frequency, delivery channels (dashboard/email/Slack), PDF export, and project-level priorities.

### 2.6 System Administrators / DevOps Engineers
- **Techniques:** Technical interviews, document analysis.
- **Purpose:** Validate authentication, role permissions, GitHub and LLM credentials, API limits, auditability, deployment constraints, and account/project deactivation.

## 3. Elicitation Outputs

| Output | What to record |
|---|---|
| Data definitions | Source, meaning, refresh time, and limitations of each metric. |
| Threshold decisions | Initial defaults, who can change them, and project-specific values. |
| Workflow decisions | Project setup, GitHub connection, report generation, and appeal review. |
| Constraints | API limits, access permissions, free-tier limits, and unavailable data. |
| Validation evidence | Interview notes, questionnaire summaries, reviewed artifacts, and decisions. |