# Object Design Document: Design Patterns & Structural Architecture

> **Course:** IT314: Software Engineering (Autumn 2026–27)  
> **Project:** AI Software Project Health & Risk Analyzer  
> **Document Type:** Object Design Specification  
> **Focus:** Architectural Design Patterns (Repository, Strategy, Publish-Subscribe)  

---

## 1. Executive Summary & Design Objectives

Object Design bridges high-level requirements (elicited in Epics E1–E5) and concrete class implementations. The system architecture addresses complex challenges:
- Ingesting heterogeneous telemetry (commits, PRs, issues, milestones) from external APIs.
- Evaluating deterministic risks across configurable project thresholds.
- Enforcing strict security boundaries for prompt injection and RBAC.
- Synthesizing grounded AI status reports and delivering them across multiple channels.

To maintain **high cohesion, low coupling, and extensible structure**, the system incorporates three foundational object-oriented design patterns:

```mermaid
graph TD
    subgraph "Architectural Design Patterns"
        A["Repository Pattern<br><i>Data Access & Persistence Isolation</i>"]
        B["Strategy Pattern<br><i>Configurable Risk & Metric Engines</i>"]
        C["Publish-Subscribe Pattern<br><i>Multi-Channel Report Delivery</i>"]
    end
    A -->|"Provides Ingested Telemetry"| B
    B -->|"Produces Calculated Health Indicators"| C
```

---

## 2. Pattern 1: Repository Pattern (Data Access Layer)

### 2.1. Intent & Problem Statement
Direct interaction between API route handlers and database queries creates tight coupling, leaks persistence technology details into the domain, and severely degrades unit testability. The **Repository Pattern** abstracts MongoDB queries behind a cohesive collection-level interface, managing database interactions, object serialization, and error wrapping.

### 2.2. Structure & UML Class Diagram

```mermaid
classDiagram
    class IRepository {
        <<interface>>
        +find_by_id(id: str) dict
        +find_all(query: dict) list
        +save(entity: dict) str
        +update(id: str, data: dict) bool
        +delete(id: str) bool
    }

    class UserRepository {
        +get_user(user_id: str) dict
        +get_user_by_email(email: str) dict
        +create_user(user: dict) str
        +update_user(user_id: str, data: dict) bool
        +deactivate_user(user_id: str) bool
    }

    class TelemetryRepository {
        +save_pull_requests(project_id: str, prs: list) int
        +get_pull_requests(project_id: str) list
        +save_issues(project_id: str, issues: list) int
        +get_issues(project_id: str) list
        +save_milestones(project_id: str, milestones: list) int
    }

    class ReportRepository {
        +save_report(project_id: str, report: dict) str
        +get_report(report_id: str) dict
        +list_reports(project_id: str) list
    }

    class DatabaseConnection {
        -client: MongoClient
        -db: Database
        +get_collection(name: str) Collection
        +ensure_indexes() void
    }

    IRepository <|.. UserRepository
    IRepository <|.. TelemetryRepository
    IRepository <|.. ReportRepository
    UserRepository --> DatabaseConnection : uses
    TelemetryRepository --> DatabaseConnection : uses
    ReportRepository --> DatabaseConnection : uses
```

### 2.3. Sequence Flow: Repository Data Access

```mermaid
sequenceDiagram
    autonumber
    actor Client
    participant Router as UserLifecycleRouter
    participant Repo as UserRepository
    participant DB as MongoDB (users_collection)

    Client->>Router: POST /api/users/{id}/deactivate
    Router->>Repo: get_user(user_id)
    Repo->>DB: find_one({"_id": ObjectId(user_id)})
    DB-->>Repo: BSON Document
    Repo-->>Router: Serialized User Entity
    Router->>Repo: update_user(user_id, {"is_active": false})
    Repo->>DB: update_one({"_id": ObjectId}, {"$set": ...})
    DB-->>Repo: UpdateResult (modified_count=1)
    Repo-->>Router: True (Success)
    Router-->>Client: 200 OK (Account Deactivated)
```

### 2.4. Implementation Highlights in Codebase
In `Backend/persistence.py`, `Backend/persistence_telemetry.py`, and `Backend/persistence_reports.py`:
- **Exception Encapsulation**: Low-level `PyMongoError`, `ServerSelectionTimeoutError`, and `ConnectionFailure` are caught and translated into domain-level `DatabaseError` exceptions, preventing database connection leaks into the presentation layer.
- **Compound Unique Indexing**: The repositories configure unique compound indexes (`projectId` + `githubId`) to enforce idempotency when recurring webhook syncs occur.
- **DTO Serialization**: MongoDB `ObjectId` types and datetimes are normalized into JSON-compliant dictionaries and Pydantic schemas.

---

## 3. Pattern 2: Strategy Pattern (Configurable Risk & Metric Engines)

### 3.1. Intent & Problem Statement
Project health evaluation requires analyzing disparate metrics with differing thresholds (e.g. PR latency, issue age, commit concentration, schedule slippage). Hardcoding these calculations into a monolithic analyzer violates the **Open/Closed Principle (OCP)**. 

The **Strategy Pattern** encapsulates each risk detection algorithm into an independent strategy object conforming to a common contract. The `HealthSummaryEngine` acts as the context, dynamically applying active strategies and re-weighting indicators when telemetry sources are missing.

### 3.2. Structure & UML Class Diagram

```mermaid
classDiagram
    class IRiskStrategy {
        <<interface>>
        +evaluate(telemetry_data: dict, thresholds: dict) RiskResult
    }

    class BottleneckStrategy {
        +evaluate(telemetry_data: dict, thresholds: dict) RiskResult
        -check_aging_prs(prs: list, threshold_hours: int) list
        -check_review_latency(prs: list) float
    }

    class WorkloadImbalanceStrategy {
        +evaluate(telemetry_data: dict, thresholds: dict) RiskResult
        -calculate_bus_factor(commits: list) float
        -calculate_contributor_skew(commits: list) float
    }

    class StaleIssueStrategy {
        +evaluate(telemetry_data: dict, thresholds: dict) RiskResult
        -filter_inactive_issues(issues: list, days: int) list
    }

    class ScheduleRiskStrategy {
        +evaluate(telemetry_data: dict, thresholds: dict) RiskResult
        -calculate_velocity_slippage(milestones: list) float
    }

    class HealthSummaryEngine {
        -strategies: List~IRiskStrategy~
        +register_strategy(strategy: IRiskStrategy) void
        +compute_composite_score(project_id: str) CompositeHealthReport
        -reweight_indicators(available_metrics: list) dict
    }

    class RiskResult {
        +indicator_name: str
        +score: float
        +severity: str
        +contributing_factors: dict
        +is_insufficient_data: bool
    }

    IRiskStrategy <|.. BottleneckStrategy
    IRiskStrategy <|.. WorkloadImbalanceStrategy
    IRiskStrategy <|.. StaleIssueStrategy
    IRiskStrategy <|.. ScheduleRiskStrategy
    HealthSummaryEngine o-- IRiskStrategy : executes
    IRiskStrategy ..> RiskResult : returns
```

### 3.3. Sequence Flow: Dynamic Risk Evaluation

```mermaid
sequenceDiagram
    autonumber
    actor Client
    participant Engine as HealthSummaryEngine (Context)
    participant BStrategy as BottleneckStrategy
    participant WStrategy as WorkloadImbalanceStrategy
    participant SStrategy as StaleIssueStrategy

    Client->>Engine: GET /api/projects/{id}/health-summary
    Engine->>Engine: Fetch Project Telemetry & Thresholds
    
    par Parallel Risk Evaluation
        Engine->>BStrategy: evaluate(PRs, stale_pr_hours=48)
        BStrategy-->>Engine: RiskResult(score=70, severity="Caution")
    and
        Engine->>WStrategy: evaluate(Commits, bus_factor=0.60)
        WStrategy-->>Engine: RiskResult(score=90, severity="Good")
    and
        Engine->>SStrategy: evaluate(Issues, stale_issue_days=14)
        SStrategy-->>Engine: RiskResult(score=85, severity="Good")
    end

    Engine->>Engine: Dynamic Re-weighting & Score Aggregation
    Engine-->>Client: 200 OK (Composite Health Index = 81.6 / 100)
```

### 3.4. Concrete Benefits in the Analyzer
1. **Dynamic Re-weighting for Insufficient Data**: If milestone data is absent, `ScheduleRiskStrategy` returns `is_insufficient_data=True`. Rather than penalizing the score to zero, `HealthSummaryEngine` dynamically reallocates weights across the remaining three active strategies.
2. **Threshold Pluggability**: Strategy thresholds (`stale_pr_hours`, `stale_issue_days`, `bus_factor_threshold`) are injected per project, allowing teams to adjust strictness without altering evaluation logic.

---

## 4. Pattern 3: Publish-Subscribe / Observer Pattern (Multi-Channel Delivery)

### 4.1. Intent & Problem Statement
When a project status report is compiled (by the LLM service or on a scheduled timer), stakeholders require delivery to different channels:
1. In-App Dashboard (MongoDB persistent storage)
2. Slack (Block Kit webhook formatted alert)
3. Email (SMTP dispatch with generated PDF report attached)

Coupling the report synthesizer directly to Slack and SMTP APIs violates Single Responsibility and risks cascading failures (e.g. an expired Slack webhook causing the entire report generation job to fail). The **Publish-Subscribe (Observer) Pattern** decouples event generation from delivery channels.

### 4.2. Structure & UML Class Diagram

```mermaid
classDiagram
    class ReportGeneratedEvent {
        +project_id: str
        +report_id: str
        +executive_summary: str
        +health_score: float
        +pdf_bytes: bytes
        +timestamp: datetime
    }

    class IReportSubscriber {
        <<interface>>
        +handle(event: ReportGeneratedEvent) DeliveryResult
    }

    class DashboardChannelSubscriber {
        +handle(event: ReportGeneratedEvent) DeliveryResult
        -persist_to_mongodb(report_doc: dict) void
    }

    class SlackDeliverySubscriber {
        -webhook_url: str
        +handle(event: ReportGeneratedEvent) DeliveryResult
        -build_block_kit_payload(event: ReportGeneratedEvent) dict
    }

    class EmailDeliverySubscriber {
        -smtp_config: dict
        +handle(event: ReportGeneratedEvent) DeliveryResult
        -render_html_body(event: ReportGeneratedEvent) str
        -attach_pdf_document(msg: MIMEMultipart, pdf: bytes) void
    }

    class ReportDispatchManager {
        -subscribers: List~IReportSubscriber~
        +subscribe(subscriber: IReportSubscriber) void
        +unsubscribe(subscriber: IReportSubscriber) void
        +publish(event: ReportGeneratedEvent) dict
    }

    IReportSubscriber <|.. DashboardChannelSubscriber
    IReportSubscriber <|.. SlackDeliverySubscriber
    IReportSubscriber <|.. EmailDeliverySubscriber
    ReportDispatchManager o-- IReportSubscriber : broadcasts to
    ReportDispatchManager ..> ReportGeneratedEvent : dispatches
```

### 4.3. Sequence Flow: Multi-Channel Broadcast with Fault Isolation

```mermaid
sequenceDiagram
    autonumber
    participant Scheduler as BackgroundReportScheduler
    participant Dispatcher as ReportDispatchManager (Publisher)
    participant DashboardSub as DashboardChannelSubscriber
    participant SlackSub as SlackDeliverySubscriber
    participant EmailSub as EmailDeliverySubscriber

    Scheduler->>Dispatcher: publish(ReportGeneratedEvent)
    
    Dispatcher->>DashboardSub: handle(event)
    DashboardSub->>DashboardSub: Save report to MongoDB
    DashboardSub-->>Dispatcher: DeliveryResult(status="Success")

    Dispatcher->>SlackSub: handle(event)
    SlackSub->>SlackSub: POST to Slack Incoming Webhook
    Note over SlackSub: Slack Webhook returns 500 error!
    SlackSub-->>Dispatcher: DeliveryResult(status="Failed", reason="Slack 500")

    Dispatcher->>EmailSub: handle(event)
    EmailSub->>EmailSub: Send SMTP email with PDF attachment
    EmailSub-->>Dispatcher: DeliveryResult(status="Success")

    Dispatcher-->>Scheduler: DispatchSummary(Dashboard=OK, Email=OK, Slack=FAILED)
    Note over Scheduler: Graceful degradation: Report is safe and email sent!
```

### 4.4. Concrete Benefits in the System
- **Fault Tolerance & Graceful Degradation**: As shown in the sequence diagram, an external network failure on Slack does not impede in-app dashboard persistence or email delivery.
- **Channel Extensibility**: Adding future integration adapters (e.g. Microsoft Teams, Discord, Jira) requires creating a new subscriber implementing `IReportSubscriber` without modifying existing report logic.

---

## 5. Architectural Quality Attributes & SOLID Principles Mapping

The object design adheres strictly to the SOLID engineering guidelines:

| Principle | Implementation in Codebase | Concrete Example |
|---|---|---|
| **Single Responsibility (SRP)** | Modular separation between routers, risk engines, persistence, and delivery. | `Backend/ai/prompt_guard.py` only handles prompt sanitization and response parsing; it does not connect to the database or format HTTP responses. |
| **Open/Closed (OCP)** | New analysis metrics and delivery channels extend base contracts without modifying caller code. | `IRiskStrategy` allows adding sprint burndown or PR review queue strategies without editing `HealthSummaryEngine`. |
| **Liskov Substitution (LSP)** | All delivery channels conform to `IReportSubscriber` and can be substituted transparently. | `SlackDeliverySubscriber` and `EmailDeliverySubscriber` return consistent `DeliveryResult` structures. |
| **Interface Segregation (ISP)** | Granular, focused schemas and contracts. | Pydantic models define discrete contracts: `ExplanationSchema`, `RecommendationSchema`, `ReportResponseSchema` using `extra="forbid"`. |
| **Dependency Inversion (DIP)** | High-level business modules depend on abstractions, injected via FastAPI `Depends`. | Routers depend on `get_current_user` and DAO functions, mocked in tests with zero database requirements. |

---

## 6. Summary

By systematically applying the **Repository**, **Strategy**, and **Publish-Subscribe** patterns, the AI Software Project Health & Risk Analyzer achieves clean modularity, resilient error isolation, high code coverage (>90% unit test success), and compliance with the IT314 course evaluation criteria.
