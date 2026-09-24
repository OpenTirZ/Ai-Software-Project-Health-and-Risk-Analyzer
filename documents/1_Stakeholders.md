# Stakeholders

## 1. Purpose
This document defines the six stakeholder groups used consistently across requirements, user stories, and planning. Other responsibilities are represented within these groups rather than creating additional stakeholder categories.

## 2. Stakeholder Groups

| # | Stakeholder group | Main interest in the system |
|---|---|---|
| 1 | Individual Developers | Understand activity-based indicators, see permitted personal flags, and provide feedback or appeals. |
| 2 | Code Reviewers / Senior Engineers | Monitor pull-request queues, review turnaround, and review-related bottlenecks. |
| 3 | Engineering / Team Leads | Monitor project health, workload indicators, blockers, and recommendations; configure team thresholds where authorized. |
| 4 | Scrum Masters / Agile Coaches | Review sprint progress, task completion, velocity, and schedule-risk indicators. |
| 5 | Project Managers | Review project-level health, schedule risk, status reports, recommendations, and report delivery/export. Product-owner/backlog-priority concerns are included here. |
| 6 | System Administrators / DevOps Engineers | Configure and maintain authentication, role permissions, GitHub/LLM connections, secrets, audit records, deployment, and account/project lifecycle. Security and InfoSec responsibilities are included here. |

## 3. Stakeholder Details

### 3.1 Individual Developers
Their GitHub commits, pull requests, and assigned issue/task activity are among the system's input data. Developers need understandable explanations for flags that concern them and a feedback/appeal mechanism. Indicators must be described as activity-based signals, not definitive judgments about effort or performance.

### 3.2 Code Reviewers / Senior Engineers
They use PR queue and review-duration information to identify review bottlenecks and understand review flow. Review time should be interpreted in context, including PR age and available metadata.

### 3.3 Engineering / Team Leads
They use the dashboard to inspect health indicators, investigate bottlenecks, review possible workload imbalance, and consider recommendations. The system does not automatically reassign work or modify repositories.

### 3.4 Scrum Masters / Agile Coaches
They use configured sprint/task data to review planned versus completed work, sprint velocity where available, blockers, and indicative schedule risk.

### 3.5 Project Managers
They review consolidated project status, health, schedule-risk indicators, reports, and recommendations. Product scope and priority context may inform their interpretation, but the platform is not a full product/backlog management replacement.

### 3.6 System Administrators / DevOps Engineers
They configure and maintain accounts, role-based access, GitHub and GenAI connections, credential security, audit logs, and project/user lifecycle actions. Email and Slack are report-delivery channels only; Slack collaboration management is outside the product.

