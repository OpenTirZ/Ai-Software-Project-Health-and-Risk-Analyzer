# Non-Functional Requirements

| ID | Category | Requirement |
|---|---|---|
| NFR-01 | Usability | The dashboard shall present health, risks, flags, and recommendations in clear language, with labels and explanations understandable without specialist training. |
| NFR-02 | Performance | Under the team's defined test environment and normal network conditions, dashboard views and standard API responses should complete within 3 seconds for the agreed demo dataset. Risk/report generation should complete within 60 seconds for the agreed dataset when the configured LLM service is available. Record measured results. |
| NFR-03 | Error handling | The system shall detect GitHub, LLM, email, or Slack integration failures and show a clear error/degraded state; a failure in an external service shall not silently fabricate or erase results. |
| NFR-04 | API efficiency | The system shall minimize and batch external API requests where practical, respect provider rate limits, and surface rate-limit or synchronization errors. |
| NFR-05 | Caching and freshness | Cached source data shall display its last-sync time. The implementation shall use a documented refresh interval and refresh/invalidation behavior after supported webhook events or manual synchronization. |
| NFR-06 | Security | Secrets and credentials shall be stored server-side using environment configuration or a secrets manager, protected at rest where supported, and never exposed in browser code or logs. Access tokens shall use least-privilege permissions and be revocable. |
| NFR-07 | Explainability | Each risk/health flag and recommendation shall identify contributing metrics and the relevant source period; uncertain or incomplete evidence shall be disclosed. |
| NFR-08 | Feedback and appeal | Affected users shall be able to submit feedback on a flag, and authorized reviewers shall be able to record a resolution and status. |
| NFR-09 | Fairness and context | The system shall not present activity-derived indicators as definitive judgments of individual performance. The team shall review thresholds and caveats for differing roles, part-time participation, and work not visible in GitHub. |
| NFR-10 | Auditability | The system shall record key security- and administration-relevant events, including sign-in/access events as feasible, integration/configuration changes, report generation/delivery outcomes, flag generation, and project/user lifecycle actions. Logs shall be access-restricted and have a documented retention policy. |
| NFR-11 | Resource constraints | The application shall be designed to operate within the team's selected free/low-cost hosting, database, and API quotas. The team shall document the selected service limits and avoid requiring GPU/model-training infrastructure. |