# Functional Requirements Specification

## 1. Data Collection & Integration

| ID | Requirement | Description |
|---|---|---|
| FR-1 | Repository and commit analysis | Connect to a configured GitHub repository and retrieve commit history, including author, timestamp, and available change-size information. Analyze the default branch unless another branch is configured. |
| FR-2 | Pull request tracking | Retrieve PR opening time, author/reviewer metadata where available, open duration, and open/merged/closed status. |
| FR-3 | Issue tracking | Retrieve GitHub issue status, assignee, labels, and latest activity/update time. |
| FR-4 | Sprint activity monitoring | Use configured GitHub Projects and/or milestone/task data to display planned and completed work and sprint velocity where the source data supports it. |
| FR-5 | Project and team configuration | Allow an authorized user to create a project, associate repositories and sprint data, and map team members to GitHub usernames for attribution. |

## 2. Analysis & Risk Indicators

| ID | Requirement | Description |
|---|---|---|
| FR-6 | Bottleneck and blocker detection | Identify potential development bottlenecks from observable project activity, such as aging/unreviewed PR queues or work repeatedly remaining in a stage. Show supporting evidence where available. |
| FR-7 | Possible workload imbalance indicator | Compare available commit, PR, and task activity with a project/team baseline and flag configurable activity patterns that may indicate imbalance. Clearly state that GitHub activity is a proxy, not a direct measure of effort or capacity. |
| FR-8 | Stale issue detection | Identify issues whose latest activity exceeds the configured project-specific inactivity threshold. |
| FR-9 | Schedule-risk assessment | Present an indicative sprint/project schedule-risk level based on available velocity, completion-rate, remaining-work, and timeline data. Do not present it as a guaranteed prediction. |
| FR-10 | Threshold configuration | Allow authorized users to view and adjust supported thresholds, including stale-issue, bottleneck, and workload/risk thresholds. Validate values before saving. |
| FR-11 | Explainable flags | Provide a plain-language explanation for each generated flag, naming the supporting metrics/data and noting missing or incomplete inputs. |

## 3. Reporting & Recommendations

| ID | Requirement | Description |
|---|---|---|
| FR-12 | Automated status report | Generate a report summarizing project health, progress, detected risks, bottlenecks, and relevant metrics from the latest available data. |
| FR-13 | Actionable recommendations | Provide specific advisory recommendations linked to detected conditions. Recommendations do not automatically reassign work, change repository data, or perform actions on behalf of users. |
| FR-14 | Report scheduling and delivery | Allow daily, weekly, or end-of-sprint report scheduling and delivery to the in-app dashboard, email, or Slack. External delivery requires configured credentials/destination; dashboard access remains the primary channel. |
| FR-15 | Report export | Allow an authorized user to export a generated status report as a PDF containing the report's health, progress, risk, and recommendation information. |

## 4. Dashboard & User Interaction

| ID | Requirement | Description |
|---|---|---|
| FR-16 | Project health dashboard | Provide a unified project dashboard showing health summary, bottlenecks, possible workload imbalance, stale issues, schedule risk, and access to supporting details. |
| FR-17 | Feedback and appeal | Allow a user to view a flag concerning them and submit feedback/appeal. An authorized Team Lead or administrator can review and record a resolution visible to the affected user. |

## 5. Access Control & Administration

| ID | Requirement | Description |
|---|---|---|
| FR-18 | Role-based access control (RBAC) | Restrict project and individual-level metrics by role and project permissions. Users without permission must not access restricted individual data. |
| FR-19 | Integration configuration | Allow an administrator to configure GitHub and the selected GenAI/LLM provider connection. Store credentials securely and keep them out of client-side code and logs. |
| FR-20 | User authentication and roles | Support account creation/sign-in and assignment of a role that controls permitted actions and data. |
| FR-21 | Project/user lifecycle | Allow an administrator to archive or delete a project and deactivate a user account to revoke access. Clearly distinguish archiving from permanent deletion. |

## 6. Shared Interpretation Rules

- **Data availability:** Show last synchronization time and identify missing, inaccessible, or stale source data. Do not silently treat missing data as zero activity.
- **Workload:** Indicators describe observable activity patterns only; they are not performance ratings or direct measurements of effort, hours, capacity, or well-being.
- **Health and risk:** Display the metrics and rules contributing to any summary. If essential inputs are unavailable, show “insufficient data” rather than an unsupported score.
- **Human control:** All flags and recommendations are advisory. Decisions and actions remain with authorized people.
- **Integration boundary:** GitHub is the primary source. Email and Slack are report-delivery channels, not collaboration platforms managed by this product.

**Total: 21 functional requirements.**
