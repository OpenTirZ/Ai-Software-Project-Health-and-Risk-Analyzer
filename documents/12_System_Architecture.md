# System Design Document: Multi-Layer FastAPI Architecture

> **Course:** IT314: Software Engineering (Autumn 2026–27)  
> **Project:** AI Software Project Health & Risk Analyzer  
> **Document Type:** System Architecture & Technical Design Specification  
> **Scope:** Multi-Layer Backend Design, Security Boundary, and Cross-Sprint Integration (Sprints 1–4)  

---

## 1. Architectural Philosophy & Overview

The **AI Software Project Health & Risk Analyzer** backend is constructed using a **strict 5-layer clean architectural model** implemented in **FastAPI (Python 3.15)** and backed by **MongoDB**.

The architectural philosophy adheres to five core tenets:
1. **Separation of Concerns (SoC)**: Strict segregation between presentation, authentication, domain analytics, external integrations, and database persistence.
2. **Deterministic Metrics First**: Transparent mathematical calculations (PR age, commit concentration, issue inactivity) are computed deterministically before AI synthesis.
3. **No Hallucinated Scores / Data**: If telemetry is missing, the system dynamically re-weights or explicitly discloses "Insufficient Data" rather than manufacturing synthetic figures.
4. **Advisory AI Governance**: GenAI assists with plain-language explanations and non-prescriptive recommendations; all decisions remain with engineering leads.
5. **Defense-in-Depth Security**: Prompt injection guards, token masking in logs, role-based access control, and immediate session invalidation for deactivated users.

---

## 2. Multi-Layer Architecture Diagram

```mermaid
graph TD
    Client["Client Layer<br>(React 19 Frontend / External API Consumers)"]

    subgraph "Layer 1: Presentation & Routing Layer"
        R_Auth["auth_router<br><i>/auth/*</i>"]
        R_Life["user_lifecycle_router<br><i>/api/users/*</i>"]
        R_Proj["project_router<br><i>/api/projects/*</i>"]
        R_Repo["repository_router<br><i>/api/repositories/*</i>"]
        R_Sync["data_sync_router<br><i>/api/projects/:id/sync</i>"]
        R_Thresh["threshold_router<br><i>/api/projects/:id/thresholds</i>"]
        R_Metric["metric_router<br><i>/api/projects/:id/health-summary</i>"]
        R_Report["report_router<br><i>/api/projects/:id/reports</i>"]
    end

    subgraph "Layer 2: Security & Cross-Cutting Middleware"
        MW_CORS["CORSMiddleware<br><i>Allowed Origins</i>"]
        MW_Log["SecretMaskingFilter<br><i>Redacts Secrets in Logs</i>"]
        MW_Exc["Global Exception Handlers<br><i>DatabaseError (503), Unhandled (500)</i>"]
        DEP_Auth["get_current_user<br><i>Bearer JWT Token & Revocation Check</i>"]
        DEP_Role["require_role<br><i>Admin, Project Manager, Developer</i>"]
    end

    subgraph "Layer 3: Domain Service & Business Logic Layer"
        SRV_Health["HealthSummaryEngine<br><i>0-100 Composite Index</i>"]
        SRV_Risk["Risk Detection Engines<br><i>Bottlenecks, Workload, Stale Issues, Schedule</i>"]
        SRV_Guard["PromptGuard & Sanitizer<br><i>Jailbreak Detection, Delimiter Neutralization</i>"]
        SRV_Schem["Strict Output Schemas<br><i>ExplanationSchema, ReportResponseSchema</i>"]
        SRV_Rec["Advisory Recommendation Engine<br><i>Actionable Suggestions</i>"]
        SRV_Graph["LangGraph V2 Orchestration<br><i>Full Telemetry State Graph</i>"]
    end

    subgraph "Layer 4: External Integration & Delivery Layer"
        EXT_GitHub["GitHub REST API Adapter<br><i>Rate-limiting, Token rotation</i>"]
        EXT_LLM["LLM Client<br><i>Gemini / OpenRouter API</i>"]
        EXT_PDF["PDF Report Engine<br><i>Jinja2 Templates & xhtml2pdf</i>"]
        EXT_Email["SMTP Email Delivery<br><i>HTML Summaries + PDF Attachment</i>"]
        EXT_Slack["Slack Delivery Service<br><i>Block Kit Webhook Cards</i>"]
    end

    subgraph "Layer 5: Persistence & Data Access Layer"
        DAO_Main["persistence.py<br><i>Users, Projects, Members</i>"]
        DAO_Telem["persistence_telemetry.py<br><i>Commits, PRs, Issues, Milestones</i>"]
        DAO_Report["persistence_reports.py<br><i>Reports, Schedules, Audit Logs</i>"]
        DB_Mongo[(MongoDB<br><i>Compound Unique Indexes & TLS</i>)]
    end

    Client -->|HTTPS / JSON| MW_CORS
    MW_CORS --> DEP_Auth
    DEP_Auth --> DEP_Role
    DEP_Role --> R_Auth & R_Life & R_Proj & R_Repo & R_Sync & R_Thresh & R_Metric & R_Report
    
    R_Thresh & R_Metric --> SRV_Health & SRV_Risk
    R_Report --> SRV_Graph & SRV_Guard & SRV_Rec
    SRV_Graph --> SRV_Schem & EXT_LLM
    
    R_Sync --> EXT_GitHub
    R_Report --> EXT_PDF & EXT_Email & EXT_Slack
    
    SRV_Risk & SRV_Health --> DAO_Telem & DAO_Main
    R_Report & EXT_PDF --> DAO_Report
    R_Life & R_Auth --> DAO_Main
    
    DAO_Main & DAO_Telem & DAO_Report --> DB_Mongo
```

---

## 3. Layer-by-Layer Architectural Specification

### 3.1. Layer 1: Presentation & Routing Layer
- **Responsibility**: Expose RESTful HTTP contracts, validate request bodies, deserialize path/query parameters, and serialize standardized responses.
- **Components**:
  - `Backend/auth/router.py`: Handles `/auth/signup`, `/auth/login`, `/auth/logout`, `/auth/me`.
  - `Backend/auth/lifecycle.py`: Handles `/api/users/{id}/deactivate` (restricted to Admin).
  - `Backend/routers/project_router.py`: Full CRUD for projects and member role assignment.
  - `Backend/routers/repository_router.py`: Connects GitHub repositories and proxies branch queries using the server `GITHUB_TOKEN` to eliminate client-side rate limits.
  - `Backend/routers/threshold_router.py`: Configures project-specific risk boundaries (`stale_pr_hours`, `stale_issue_days`, `workload_imbalance_ratio`, `bus_factor_threshold`).
  - `Backend/routers/metric_router.py`: Endpoints for composite health, PR bottlenecks, workload distribution, and stale issue lists.
  - `Backend/routers/report_router.py`: On-demand report synthesis, PDF streaming download, and multi-channel dispatch triggers.
- **Schema Validation**: Built with Pydantic v2 models using `ConfigDict(extra="forbid", str_strip_whitespace=True)`. Boundary validators reject out-of-bounds parameters before business execution, returning clean `422 Unprocessable Entity` errors.

### 3.2. Layer 2: Security & Cross-Cutting Middleware Layer
- **Responsibility**: Authenticate requests, enforce access boundaries, sanitize logs, and handle infrastructure failures gracefully.
- **Components**:
  1. **Authentication Dependency (`get_current_user`)**:
     - Extracts and verifies Bearer JWT tokens using cryptographic SHA-256 signatures.
     - Resolves user document from database.
     - **Session Revocation**: Immediately checks `if user.get("is_active") is False: raise 401 Unauthorized`, revoking access across all existing JWT sessions upon administrative deactivation.
  2. **Role-Based Authorization (`require_role`)**:
     - Enforces permissions using system roles (`admin`, `project_manager`, `developer`).
     - Rejects unauthorized callers with `403 Forbidden`.
  3. **Secret-Masking Log Filter (`_SecretMaskingFilter`)**:
     - Intercepts Python logging streams. Regex matches and replaces any sensitive token, secret, password, or MongoDB URI strings with `<REDACTED>` before emission to stdout or log files.
  4. **Global Exception Handlers**:
     - Translates all internal `DatabaseError` exceptions into `503 Service Unavailable`.
     - Catches unhandled exceptions, logs the full trace server-side, and returns an opaque `500 Internal Server Error` to prevent leaking internals to attackers.
  5. **CORS Middleware**:
     - Configurable origins via environment variables, defaulting to authorized frontend ports (`3000`, `5000`, `5173`).

### 3.3. Layer 3: Domain Service & Business Logic Layer
- **Responsibility**: Execute core deterministic algorithms, enforce AI guardrails, and coordinate synthesis workflows.
- **Components**:
  1. **Composite Health Score Engine (`Backend/analysis/health_summary.py`)**:
     - Aggregates PR bottlenecks, workload skew, stale issues, and schedule velocity into a 0–100 index:
       - Score $\ge 75$: **Good** (Green)
       - $50 \le$ Score $< 75$: **Caution** (Yellow)
       - Score $< 50$: **At Risk** (Red)
     - **Dynamic Re-Weighting**: Automatically reallocates weights among available sources when a data source is empty, avoiding artificial score penalties.
  2. **Prompt Injection Guard (`Backend/ai/prompt_guard.py`)**:
     - Sanitizes external GitHub text (commit messages, PR titles, issue descriptions) to prevent prompt hijacking.
     - Strips Unicode Bidi overrides (`\u202E`), zero-width evasion characters, and ASCII control characters.
     - Neutralizes LLM delimiter tokens (`<|im_start|>`, `[INST]`, `<<SYS>>`, `<system>`).
     - Detects jailbreaks (DAN mode, roleplay escapes, system prompt extraction).
     - Encapsulates untrusted external text in `<untrusted_external_content>` tags.
     - Strictly validates LLM JSON responses with Pydantic schemas, rejecting hallucinated extra keys.
  3. **Advisory Recommendations Engine (`Backend/ai/recommendation_service.py`)**:
     - Synthesizes targeted suggestions for active risk flags. Enforces `is_advisory = True` and explicit non-prescriptive governance disclaimers.
  4. **LangGraph V2 Pipeline (`Backend/externalservies/LangGraph/`)**:
     - Orchestrates telemetry normalization, metric analysis, grounded executive summary generation, and structured report compilation into a cohesive state machine.

### 3.4. Layer 4: External Integration & Delivery Layer
- **Responsibility**: Interface with third-party cloud services, APIs, and export renderers.
- **Components**:
  1. **GitHub REST API Client**: Ingests commits, PR reviews, issues, and milestones using authenticated requests under the server `GITHUB_TOKEN` (5,000 requests/hour quota).
  2. **LLM Provider Gateway**: Connects via OpenRouter / Google Gemini API using structured system prompts and deterministic temperature settings.
  3. **PDF Generation Service**: Renders HTML status reports with health score badges and action checklists into downloadable PDF binaries using Jinja2 and `xhtml2pdf`.
  4. **Email Delivery Service**: Dispatches automated multipart emails over SMTP with HTML body and attached PDF report.
  5. **Slack Delivery Service**: Translates status reports into interactive Slack Block Kit cards and posts to configured project webhooks.

### 3.5. Layer 5: Persistence & Data Access Layer
- **Responsibility**: Abstract physical storage, maintain database connections, and enforce storage integrity.
- **Components**:
  - `Backend/persistence.py`: Manages `users` and `projects` collections.
  - `Backend/persistence_telemetry.py`: Manages `commits`, `pull_requests`, `issues`, and `milestones` collections.
  - `Backend/persistence_reports.py`: Manages `reports`, `report_schedules`, and `audit_logs` collections.
  - **Database Connection Management**: Handles MongoClient lifecycle with Atlas SRV TLS, timeout limits (`serverSelectionTimeoutMS=10000`), and connection pooling.
  - **Compound Unique Indexes**:
    - `pull_requests`: `{ projectId: 1, number: 1 }`
    - `issues`: `{ projectId: 1, number: 1 }`
    - `commits`: `{ projectId: 1, sha: 1 }`
    - `milestones`: `{ projectId: 1, milestoneId: 1 }`
    - Guarantees data idempotency during repeated synchronizations.

---

## 4. End-to-End Request-Response Lifecycle

The sequence diagram below illustrates the complete traversal through all five architectural layers for a protected analytical request:

```mermaid
sequenceDiagram
    autonumber
    actor User as Client (Frontend)
    participant MW as Middleware & CORS
    participant Auth as Auth Dependency (Layer 2)
    participant Router as MetricRouter (Layer 1)
    participant Engine as HealthSummaryEngine (Layer 3)
    participant Repo as TelemetryRepository (Layer 5)
    participant DB as MongoDB Instance

    User->>MW: GET /api/projects/{id}/health-summary<br>[Header: Bearer Token]
    MW->>Auth: Validate Credentials
    Auth->>Auth: Decode JWT Signature
    Auth->>DB: Fetch user by ID
    DB-->>Auth: User record (is_active: true)
    Auth-->>MW: Authenticated User Principal
    MW->>Router: Dispatch Endpoint Handler
    
    Router->>Router: Check Project Membership (RBAC)
    Router->>Engine: compute_composite_health(project_id)
    
    Engine->>Repo: get_pull_requests(project_id)
    Engine->>Repo: get_commits(project_id)
    Engine->>Repo: get_issues(project_id)
    Repo->>DB: Query Telemetry Collections
    DB-->>Repo: BSON Documents
    Repo-->>Engine: Normalized Activity Records
    
    Engine->>Engine: Run Bottleneck Strategy
    Engine->>Engine: Run Workload Imbalance Strategy
    Engine->>Engine: Run Stale Issues Strategy
    Engine->>Engine: Dynamic Weight Normalization
    Engine-->>Router: Composite Health Model (Score: 84.5, Good)
    
    Router-->>User: 200 OK [JSON HealthSummaryResponse]
```

---

## 5. Non-Functional Quality Attribute Verification

| Category | Requirement | Architectural Enforcement |
|---|---|---|
| **Performance (NFR-02)** | API responses $<3$s, report synthesis $<60$s. | Database indexed queries, asynchronous FastAPI worker pool, lightweight Jinja2 PDF generation. |
| **Error Handling (NFR-03)** | External failures must not fabricate data or crash server. | Graceful degradation across delivery channels; explicit "Insufficient Data" indicators; global 503/500 handlers. |
| **API Efficiency (NFR-04)** | Minimize external requests, respect rate limits. | Server-side `GITHUB_TOKEN` proxying (5,000 req/hr), client branch caching, compound unique DB indexing. |
| **Security & Privacy (NFR-06)** | Secrets protected at rest, never logged. | Environment-variable injection, secret-masking log filter, bcrypt password hashing, prompt injection guardrails. |
| **Fairness & Governance (NFR-09)** | Activity not treated as personal performance. | Advisory disclaimers on all recommendations; activity treated explicitly as workflow proxies rather than individual productivity. |
| **Auditability (NFR-10)** | Record key administrative and security events. | Comprehensive audit logging for project updates, user deactivations, threshold adjustments, and report dispatches. |

---

## 6. Sprint Integration Summary

The architecture represents the unified realization of all four project sprints:
- **Sprint 1 (Foundation)**: Authentication, RBAC, project management, and base repository layer.
- **Sprint 2 (Telemetry & Risk Engines)**: PR/Issue/Milestone ingestion, threshold management, bottleneck and workload strategies, composite health index.
- **Sprint 3 (AI Synthesis & Multi-Channel Delivery)**: Prompt injection protection, strict Pydantic schemas, LangGraph v2 workflow, PDF generation, Email SMTP, and Slack Block Kit integration.
- **Sprint 4 (Governance & Lifecycle)**: Account deactivation API, immediate JWT session invalidation, OpenAPI documentation export, and object design artifacts.
