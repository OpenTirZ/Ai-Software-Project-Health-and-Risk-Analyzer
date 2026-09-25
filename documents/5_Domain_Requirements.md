# Domain Requirements

| ID | Domain concept | Requirement / constraint |
|---|---|---|
| DR-01 | Repository | GitHub repository metadata defines the analyzed project boundary. Use the configured/default branch unless another branch is selected. |
| DR-02 | Commit activity | Commit data reflects work pushed to GitHub. Local, uncommitted, or otherwise unobservable work is not visible and must not be interpreted as no work. |
| DR-03 | Contributor and workload | GitHub does not provide a standardized workload/capacity measure. Workload flags are configurable activity-based indicators and must be described as possible imbalance, not a definitive overload judgment. |
| DR-04 | Issue staleness | Staleness has no universal threshold. Each project can configure an inactivity period; the system uses the latest available issue activity timestamp. |
| DR-05 | Pull request and review | Review duration depends on PR size, complexity, team norms, and metadata availability. Bottleneck thresholds are configurable and findings are indicative. |
| DR-06 | Sprint | Sprint definitions and task states vary. For the MVP, sprint/task data is sourced from configured GitHub Projects and/or milestones; unsupported or inconsistent structures must be disclosed. |
| DR-07 | Task and milestone | Milestones may not represent all tasks or estimates. Planned/completed counts and velocity can only be calculated when source data provides consistent task status and, where needed, estimates. |
| DR-08 | Schedule risk | Schedule-risk indicators are estimates from available historical and current activity, not guaranteed predictions. Insufficient history or missing sprint data must be shown. |
| DR-09 | Project health | Health is a transparent summary of selected indicators, not an objective universal measure. The dashboard/report must expose contributing metrics and avoid opaque unsupported scoring. |
| DR-10 | External integrations | GitHub, the selected LLM provider, email, and Slack have independent authentication, permissions, quotas, and availability. The system must handle provider limits and failures. |
| DR-11 | Report delivery | Email and Slack are optional configured delivery destinations for generated reports. The platform does not manage Slack workspaces/channels or replace team collaboration tools. |
| DR-12 | Privacy and access | Individual-level metrics and appeals are visible only to the affected user and authorized roles according to the access policy. Aggregated views must not expose restricted personal details. |
