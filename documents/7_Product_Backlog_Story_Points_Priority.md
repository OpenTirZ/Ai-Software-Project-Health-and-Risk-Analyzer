# Product Backlog — Story Points, Priority & Dependencies

## 1. Estimation and priority

Story points estimate relative effort, complexity, uncertainty, integration, and testing—not hours. Priorities are High, Medium, or Low. Estimates are initial planning values and should be revisited after sprint retrospectives.

## 2. Complete backlog

| Story | FR | Summary | Primary stakeholder | Priority | Points | Dependencies |
|---|---|---|---|---|---:|---|
| US-01 | FR-1 | View Commit History | Team Lead | High | 5 | US-05, US-19, US-20 |
| US-02 | FR-2 | Track GitHub Pull Requests | Team Lead / Code Reviewer | High | 3 | US-05, US-19 |
| US-03 | FR-3 | View GitHub Issue Information | Team Lead | High | 3 | US-05, US-19 |
| US-04 | FR-4 | View Sprint Progress and Velocity | Scrum Master / Agile Coach | High | 5 | US-05 |
| US-05 | FR-5 | Create and Configure a Project | Team Lead / Project Manager | High | 5 | US-19, US-20 |
| US-06 | FR-6 | Identify Development Bottlenecks and Blockers | Team Lead / Scrum Master | High | 8 | US-02, US-03 |
| US-07 | FR-7 | Identify Possible Workload Imbalance | Team Lead | High | 5 | US-01, US-02, US-04 |
| US-08 | FR-8 | Identify Stale GitHub Issues | Team Lead | High | 3 | US-03 |
| US-09 | FR-9 | Identify Schedule Risk | Project Manager | High | 5 | US-04 |
| US-10 | FR-10 | Configure Analysis Thresholds | Team Lead / System Administrator | Medium | 3 | US-20 |
| US-11 | FR-11 | Explain Generated Flags | Developer / Team Lead | High | 8 | US-06–US-09 |
| US-12 | FR-12 | Generate Project Status Report | Project Manager | High | 8 | US-06–US-09, US-11 |
| US-13 | FR-13 | Provide Actionable Recommendations | Team Lead / Project Manager | High | 5 | US-12 |
| US-14 | FR-14 | Schedule and Deliver Status Reports | Project Manager | Medium | 5 | US-12 |
| US-15 | FR-15 | Export Project Status Report | Project Manager | Low | 3 | US-12 |
| US-16 | FR-16 | View Project Health Dashboard | Team Lead | High | 8 | US-06–US-09 |
| US-17 | FR-17 | Submit Feedback or Appeal on a Flag | Developer | Medium | 5 | US-11 |
| US-18 | FR-18 | Control Access to Individual Metrics | System Administrator / DevOps | High | 8 | US-20 |
| US-19 | FR-19 | Configure GitHub and GenAI Integrations | System Administrator / DevOps | High | 5 | US-20 |
| US-20 | FR-20 | Sign Up, Log In, and Receive a Role | All user roles | High | 5 | Foundational |
| US-21 | FR-21 | Archive or Delete Projects and Deactivate Users | System Administrator / DevOps | Low | 5 | US-05, US-18 |


## 3. Story-point distribution

| Points | Number of stories | Story IDs |
|---:|---:|---|
| 3 | 5 | US-02, US-03, US-08, US-10, US-15 |
| 5 | 11 | US-01, US-04, US-05, US-07, US-09, US-13, US-14, US-17, US-19, US-20, US-21 |
| 8 | 5 | US-06, US-11, US-12, US-16, US-18 |
| **Total** | **21** | **110 points** |

## 4. Priority distribution

| Priority | Count | Story IDs |
|---|---:|---|
| High | 16 | US-01–US-09, US-11–US-13, US-16, US-18–US-20 |
| Medium | 3 | US-10, US-14, US-17 |
| Low | 2 | US-15, US-21 |

## 5. Dependency guidance

- **Foundation:** US-20 (authentication), US-19 (integration configuration), and US-05 (project/team setup) enable data ingestion and role-gated workflows.
- **Data ingestion:** US-01–US-04 provide the source data for analysis.
- **Analysis:** US-06–US-09 depend on relevant source data; US-10 supplies configurable thresholds.
- **Explanation and reporting:** US-11 depends on detection; US-12 depends on health/analysis outputs; US-13–US-15 depend on report generation.
- **Dashboard and governance:** US-16 aggregates indicators; US-17 depends on flag explanations; US-18 and US-21 depend on authentication and project setup.