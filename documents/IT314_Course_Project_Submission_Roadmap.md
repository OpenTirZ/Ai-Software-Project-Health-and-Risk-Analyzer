# IT314: Software Engineering — Final Course Project Submission & Work Bifurcation Master Plan
**Project Name:** कVaच (KAVACH) — AI Software Project Health & Risk Analyzer  
**Course:** IT314: Software Engineering (Autumn 2026–27)  
**Instructor:** Prof. Saurabh Tiwari  
**Strict Deadlines:**
1. **Physical Hardcopy Submission (Contribution Document):** **03/12/2026 by 05:00 PM** (FB-1 Letterbox or in-person to Prof. Saurabh Tiwari)
2. **Online Submission (Google Form & Drive ZIP):** **03/12/2026 by 11:59 PM** (Firm Deadline via [Google Form](https://forms.gle/vu1kaqJUeqWYhPPa8))
3. **GitHub Code Freeze:** **03/12/2026 at 11:59 PM** (Strictly zero commits permitted after deadline)

---

## 1. Executive Summary & Grading Architecture

### 1.1 Course Weightage & Breakdown
* **Total Course Weight:** 25% of the overall course grade.
* **Evaluation Formula:**
  $$\text{Final Project Score} = (20\% \times \text{Group Evaluation}) + (80\% \times \text{Individual Evaluation})$$
* **Group Evaluation Component (100% Group Breakdown):**
  * User Stories, Requirements & Design Documents: **30%**
  * GIT Repository Management: **15%**
  * Live Project Demonstration: **15%**
  * Teamwork & Collaboration Proof: **15%**
  * Testing Artifacts (Unit, System, GUI, Mutation, NFR): **10%**
  * Slack Collaboration: **10%**
  * Presentation Slides (Strict 10 slides): **5%**
* **Individual Evaluation Component (80% Total Weight):**
  * Viva Voce & Individual Code Contribution.
  * *Warning from Guidelines:* "If you have not contributed to the project and have also been confirmed by the team leader / evidence from the GitHub repository, ZERO marks will be assigned to the project component."

---

## 2. Complete Deliverables Inventory (What Must Be Produced)

The final submission must be compiled into a single archive: `<group_No>.zip` uploaded to Google Drive with public/view access, containing separate, dedicated PDF/Markdown files for each requirement:

```
<group_No>.zip
├── 01_Requirements_Specification/
│   ├── Functional_Requirements.pdf
│   ├── Non_Functional_Requirements.pdf
│   ├── Use_Cases_Specification.pdf
│   └── User_Stories_and_Acceptance_Criteria.pdf
├── 02_Sprint_Documentation/
│   ├── Sprint_1_Details_with_Class_and_Sequence_Diagrams.pdf
│   ├── Sprint_2_Details_with_Class_and_Sequence_Diagrams.pdf
│   ├── Sprint_3_Details_with_Class_and_Sequence_Diagrams.pdf
│   └── Sprint_4_Details_with_Class_and_Sequence_Diagrams.pdf
├── 03_System_and_Object_Design/
│   ├── System_Design_Document_Combined.pdf
│   ├── Object_Design_Document.pdf
│   ├── GenAI_LangGraph_Architecture_Document.pdf
│   └── Comprehensive_UML_Diagrams_Class_Seq_Activity_State.pdf
├── 04_Testing_Artifacts/
│   ├── 01_Unit_Testing_WhiteBox_and_Coverage_Report.pdf
│   ├── 02_System_and_Acceptance_Testing_BlackBox.pdf
│   ├── 03_GUI_Testing_Report.pdf
│   ├── 04_Mutation_Testing_Report.pdf
│   └── 05_Non_Functional_Testing_Performance_Security.pdf
├── 05_Traceability_and_Scope/
│   ├── Requirements_Traceability_Matrix_RTM.pdf
│   └── Unimplemented_Requirements_and_Future_Scope.pdf
├── 06_Project_Management_and_Artifacts/
│   ├── UI_UX_Design_Wireframes_and_StyleGuide.pdf
│   ├── GitHub_Repository_Workflow_Report.pdf
│   ├── Slack_Communication_and_Teamwork_Evidence.pdf
│   └── CI_CD_Pipeline_and_Deployment_Architecture.pdf
├── 07_Presentation_and_Demo/
│   ├── Presentation_Slides_S1_to_S10.pptx (and .pdf)
│   └── Live_Deployment_URL_Access_Credentials.pdf
├── 08_Contribution_Document/
│   └── Formal_Contribution_Document_Signed.pdf
└── Source_Code/
    └── [Full clean snapshot of repository at deadline]
```

---

## 3. Detailed Breakdown of Deliverables & Requirements

### Deliverable 1: Complete Requirements Specification
* **What's needed:**
  1. **Functional Requirements (FRs):** Unambiguous, numbered (`FR-1` to `FR-N`), with inputs, execution flow, outputs, and edge cases.
  2. **Non-Functional Requirements (NFRs):** Specific, measurable criteria (response latency < 500ms, secret masking, 99.9% uptime, RBAC security, data privacy standards).
  3. **Use Cases:** Formal use case specifications including Actors, Preconditions, Trigger, Main Flow, Alternative Flows, and Postconditions.
  4. **User Stories:** Standard Agile format: `"As a <stakeholder>, I want <goal>, so that <benefit>"`, with INVEST criteria and explicit Gherkin-style Acceptance Criteria (`Given-When-Then`).

### Deliverable 2: Sprint Details with Sequence & Class Diagrams *(Explicit Guideline Rule)*
* **Requirement:** Each sprint MUST have its own dedicated:
  * Goal and Backlog items addressed
  * Burndown / Velocity summary
  * **Class Diagram** (specific to models and services altered/added in that sprint)
  * **Sequence Diagram** (for the core interaction implemented in that sprint)
* **Sprint Breakdown for कVaच:**
  * **Sprint 1:** Repository Onboarding, GitHub API Connector, Commit/PR Ingestion, Database Indexing.
  * **Sprint 2:** Telemetry Hardening, Workload Imbalance & Bottleneck Detection Engine, Health Score Calculator.
  * **Sprint 3:** GenAI LangGraph Risk Pipeline, Explainability & Mitigation Engine, Scheduled Email/Slack Dispatcher.
  * **Sprint 4:** Interactive Dashboard UI, Responsive Hero Theme, Role-Based Access Control, PDF Telemetry Export, Multi-stage Docker & Cloud Deployment.

### Deliverable 3: System Design, Object Design & LangGraph Specs
* **System Design (Combined for all Sprints):**
  * Architectural Style: Micro-modular Layered Architecture (Presentation Layer, FastAPI Gateway, Business Engine Layer, Persistence Layer, Asynchronous Workers).
  * Component Communication: RESTful JSON APIs, Webhook receivers, background cron worker daemon.
  * Deployment Architecture: Multi-stage Dockerized containers, MongoDB Atlas, Render Web Service & Static Hosting.
* **Object Design:**
  * Class structure, method signatures, design patterns applied:
    * *Repository Pattern* (data persistence decoupling)
    * *Strategy Pattern* (health metric calculation algorithms)
    * *Observer / Pub-Sub Pattern* (alert & notification dispatchers)
    * *Pipeline Pattern* (LangGraph multi-step risk synthesis)
    * *Singleton / Factory Pattern* (Database connection management & encryption handlers)
* **GenAI LangGraph Architecture:**
  * State graph modeling, prompt engineering with secret masking, hallucination mitigation, deterministic fallback modes.

### Deliverable 4: Comprehensive UML Diagrams Document
Must include high-resolution, industry-standard diagrams:
1. **Class Diagram:** Complete entity and service model (User, Project, Repository, MetricSnapshot, HealthReport, RiskFlag, AlertConfig, AuditLog).
2. **Sequence Diagrams:**
   * User Authentication & RBAC verification
   * Repository Sync & Webhook Ingestion
   * Health Score Evaluation & Bottleneck Detection
   * GenAI LangGraph Synthesis & Grounding
   * Automated Scheduled Report Dispatch (Email & Slack)
3. **Activity Diagrams:**
   * End-to-end telemetry calculation pipeline
   * AI grounding and fallback validation workflow
4. **State Machine / State Transition Diagrams:**
   * Project Health State Machine (`EXCELLENT` $\leftrightarrow$ `GOOD` $\leftrightarrow$ `AT_RISK` $\leftrightarrow$ `CRITICAL`)
   * Scheduled Report Worker State Machine (`IDLE` $\rightarrow$ `FETCHING` $\rightarrow$ `COMPUTING` $\rightarrow$ `DISPATCHED` $\rightarrow$ `LOGGED`)
   * User Account Lifecycle (`INVITED` $\rightarrow$ `ACTIVE` $\rightarrow$ `DEACTIVATED`)

### Deliverable 5: Complete Testing Portfolio (10% Group Grade)
The course guidelines demand 5 distinct testing dimensions:
1. **Unit Testing & White-Box Coverage:**
   * Backend: PyTest test suite (1,241 unit/integration tests currently passing!).
   * Frontend: Vitest + React Testing Library test suite.
   * Coverage: Coverage report via `pytest-cov` and Vitest coverage showing line, branch, and function coverage percentages.
2. **System Testing (Black-Box & Acceptance Testing):**
   * Functional test cases based on Equivalence Partitioning and Boundary Value Analysis.
   * End-to-end acceptance test matrices mapping User Stories to pass/fail criteria.
3. **GUI / Frontend Testing:**
   * Component rendering and interaction tests.
   * Responsive layout checks across desktop, tablet, and mobile breakpoints.
   * Error state validation (invalid logins, network timeouts, invalid GitHub tokens).
4. **Mutation Testing:**
   * Automated mutation testing execution (using `mutmut` for Python or `Stryker` for TypeScript).
   * Mutation score calculation:
     $$\text{Mutation Score} = \frac{\text{Killed Mutants}}{\text{Total Mutants Generated}} \times 100$$
   * Analysis of surviving vs killed mutants to demonstrate test assertion strength.
5. **Non-Functional Testing:**
   * Performance & Latency: Response time measurements for sync and calculation endpoints (< 500ms).
   * Security Testing: Secret masking audit (redacting GitHub tokens/passwords from logs), JWT expiration tests, SQL/NoSQL injection prevention.
   * Stress & Concurrency: Multiple concurrent report generations and background daemon polling stability.

### Deliverable 6: Requirements Traceability Matrix & Unimplemented Requirements
* **Requirements Traceability Matrix (RTM):**
  * Bidirectional matrix linking:
    $$\text{User Story ID} \longleftrightarrow \text{FR/NFR ID} \longleftrightarrow \text{Design Module} \longleftrightarrow \text{Source Code File} \longleftrightarrow \text{Test Case ID}$$
* **Unimplemented Requirements Document:**
  * Honest academic documentation of out-of-scope or deferred capabilities:
    1. Direct automatic GitHub PR auto-remediation (deferred to prevent unintended repository mutations; advisory recommendations provided instead).
    2. Self-hosted on-premise LLM inference (external Gemini/OpenAI API used due to student compute constraints).
    3. Bidirectional Slack conversation bot (Slack used strictly for unidirectional dispatch due to OAuth scope constraints).

### Deliverable 7: Presentation Slides (Strict 10-Slide Template)
The evaluation strictly allocates 5 minutes for presentation across 10 defined slides:
* **Slide 1:** Title Slide (Project Name: कVaच, Group Number, Team Members & IDs, Date)
* **Slide 2:** Group Leader & Detailed Assignments of Tasks to each team member
* **Slide 3:** Objectives (Problem statement, key value proposition, high-level solution)
* **Slide 4:** Milestones (Sprint 1 to Sprint 4 planned dates vs actual completion, key milestones achieved)
* **Slide 5:** Use Case Diagram & Sprint Backlog Details
* **Slide 6:** Lessons Learnt (Technical learnings: LangGraph state machines, Docker multi-stage builds, MongoDB aggregation pipelines, Scrum processes)
* **Slide 7:** Achievements (1,241 automated tests, 100% cloud deployment, 0 security leaks, sub-second telemetry engine)
* **Slide 8:** Mistakes & Retrospective (Merge conflicts during UI theming, NPM lockfile version corruption, Docker caching gotchas, and how they were resolved)
* **Slide 9:** Rating of Software Artefacts (Self-evaluation 0 to 5 for requirements, design, code, tests, CI/CD with justifications)
* **Slide 10:** Overall Project Rating (Out of 10) with technical defense

### Deliverable 8: Physical Contribution Document
* **Format:** Formal printed document, signed by Group Leader and all team members.
* **Content:**
  * Member names, student IDs, assigned modules, exact PR numbers, lines of code, test cases authored, and percentage contribution.
* **Delivery:** Must be dropped in Prof. Saurabh Tiwari's FB-1 letter box or handed to him in his office before **3rd December 2026, 05:00 PM**.

### Deliverable 9: Live Deployment (Mandatory)
* **Live Deployment:**
  * Functional production URL on Render with pre-seeded demo data so evaluators can test immediately without setup.

---

## 4. Team Work Bifurcation Matrix (10-Member Plan)

To ensure zero overlap, maximum accountability, and strong individual Git/Viva evidence, the work is bifurcated across 10 specialized functional tracks:

| Team Member | Primary Role | Assigned Submission Deliverables | Specific Action Items |
| :--- | :--- | :--- | :--- |
| **Shah Varshil** | **DevOps, CI/CD & Deployment Lead** *(Group Leader)* | • CI/CD Architecture Document<br>• Docker & Live Cloud Deployment<br>• Physical Contribution Document Coordination | 1. Finalize Render backend & frontend live production URLs.<br>2. Seed live demo repository with realistic sample data.<br>3. Compile the master physical Contribution Document for Prof. Tiwari.<br>4. Submit the final Google Form and manage GitHub code freeze. |
| **Ramit** | **Backend Architecture & System Design Lead** | • System Design Document (Combined)<br>• Object Design Document<br>• API Reference Specification | 1. Document the multi-layer FastAPI architecture.<br>2. Write the Object Design document covering design patterns (Repository, Strategy, Pub-Sub).<br>3. Generate OpenAPI / Swagger documentation export.<br>4. Prepare Git Repository management demonstration for Viva. |
| **Tirth Patel** | **AI Pipeline & LangGraph Analytics Lead** | • GenAI LangGraph Architecture Doc<br>• Risk & Bottleneck Engine Spec<br>• Slide S6 & S7 (Learnings & Achievements) | 1. Document LangGraph state-graph pipeline, prompt templates, and grounding validators.<br>2. Document health score mathematical formulas and bottleneck heuristic rules.<br>3. Author presentation slides on technical achievements. |
| **Darpan** | **Frontend UI/UX & Client Architecture Lead** | • UI/UX Design & Wireframes Document<br>• Client Architecture Specification<br>• Live Demo Co-presenter | 1. Compile Figma wireframes, design system, and color token documentation (`#004643`, `#990011`, `#F0FDE5`).<br>2. Document React component hierarchy and state management.<br>3. Polish all user flows for the live 10-minute demo. |
| **Om Patel** | **Database, Milestones & Sprint Details Lead** | • Sprint 1–4 Details Documentation<br>• MongoDB Database Design<br>• Slide S4 (Milestones) | 1. Document Sprint 1 through 4 backlogs, user stories, and velocity.<br>2. Document MongoDB schemas, indexing strategies, and collection relationships.<br>3. Author Slide S4 on milestone delivery timelines. |
| **Shivani** | **UML Modeling & Architecture Diagrams Lead** | • Comprehensive UML Diagrams Document<br>• Per-Sprint Class & Sequence Diagrams | 1. Create formal Class & Sequence diagrams for Sprint 1, 2, 3, and 4.<br>2. Create system-wide Class Diagram, Activity Diagrams (AI workflow), and State Machine Diagrams (Health status).<br>3. Export all diagrams in high-resolution vector/PNG formats. |
| **Prince Savaliya** | **QA & White-Box/Mutation Testing Lead** | • Unit Testing & Code Coverage Report<br>• Mutation Testing Report (`mutmut`)<br>• Slide S9 (Artefacts Rating) | 1. Run full `pytest --cov` and Vitest coverage to export HTML/LCOV reports.<br>2. Execute mutation testing with `mutmut` and write the mutation analysis report.<br>3. Document white-box test design methodologies. |
| **Gaurav Rathod** | **Requirements & Traceability Lead** | • Complete Requirements Specification (FR/NFR/Use Cases)<br>• Requirements Traceability Matrix (RTM)<br>• Unimplemented Requirements Doc | 1. Consolidate and format FRs, NFRs, and detailed Use Case specifications.<br>2. Construct the end-to-end Requirements Traceability Matrix (RTM).<br>3. Write the Unimplemented Requirements & Justification document. |
| **Yagnik N.** | **Testing, Verification & Presentation Lead** | • Presentation PPT (Strict 10 Slides S1–S10)<br>• Non-Functional Testing Report (Perf/Security)<br>• System & Acceptance Black-Box Testing Matrix<br>• Presentation Timekeeper | 1. Create the official PPT adhering strictly to slides S1 through S10.<br>2. Execute performance benchmarks (latency, throughput) and security tests.<br>3. Document black-box system test matrices and acceptance criteria validation.<br>4. Rehearse the strict 5-minute presentation timing with the team. |
| **Vandit** | **Slack Collaboration & Teamwork Evidence Lead** | • Slack Communication & Teamwork Evidence Document | 1. Curate Slack channel logs, team discussions, and standup evidence.<br>2. Collect screenshots of technical coordination and PR reviews.<br>3. Package collaboration evidence for the submission archive. |

---

## 5. Master Testing Framework & Peer Cross-Testing Matrix

### 5.1 Testing Strategy: Simultaneous vs. Sequential

To achieve an exceptional grade in software engineering, testing cannot be haphazard. It is executed in two complementary dimensions:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        SIMULTANEOUS TESTING (Continuous in CI/CD)                       │
│  • Developer commits code ➔ Automated PyTest & Vitest suites trigger on GitHub Actions │
│  • Linting & static type checking (Ruff / TypeScript) executed on every PR             │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                       SEQUENTIAL TESTING PIPELINE (Staged Rollout)                      │
│                                                                                        │
│   [Stage 1: Unit & Component Testing (White-Box)]                                      │
│   Ensures individual functions, routers, and React components execute cleanly (100% cov)│
│                                           │                                            │
│                                           ▼                                            │
│   [Stage 2: Integration & Contract Testing]                                            │
│   Verifies FastAPI endpoints ⟷ MongoDB collections ⟷ GitHub API sync                    │
│                                           │                                            │
│                                           ▼                                            │
│   [Stage 3: GUI & Frontend Interaction Testing]                                        │
│   Verifies form validation, auth redirects, responsive cards, and error state displays │
│                                           │                                            │
│                                           ▼                                            │
│   [Stage 4: System & User Acceptance Testing (Black-Box)]                               │
│   End-to-end testing of full user journeys against documented Use Cases (EP & BVA)     │
│                                           │                                            │
│                                           ▼                                            │
│   [Stage 5: Non-Functional & Security Testing]                                         │
│   API response latency (<500ms), secret-masking filter verification, RBAC penetration  │
│                                           │                                            │
│                                           ▼                                            │
│   [Stage 6: Mutation Testing (Fault Injection)]                                        │
│   Injects artificial code mutations via mutmut to measure test-suite kill rate         │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

1. **Simultaneous (Continuous during development):**
   * Unit tests (PyTest and Vitest) run continuously on every push and pull request via GitHub Actions CI.
   * This guarantees that new commits never break existing baseline logic.
2. **Sequential (Staged pre-submission verification):**
   * *Stage 1 $\rightarrow$ Stage 6* must be carried out in exact chronological order before packaging the final submission:
     * **Do NOT run System Testing** before Unit Testing is 100% green.
     * **Do NOT run Mutation Testing** before the full test suite has been established, or mutant generation will fail.
     * **Do NOT run Non-Functional / Latency Testing** until the service is fully deployed to the production environment on Render.

---

### 5.2 Peer Cross-Testing Matrix (Independent Verification & Validation - "Who Tests Whom")

Under formal Software Engineering principles (IEEE 1012 / CMMI), **developers must never exclusively test their own modules**. An independent peer tester must verify the deliverables:

| Target Module & Source Code | Module Author | Designated Peer Tester(s) | Testing Type to Perform | Specific Verification Target |
| :--- | :--- | :--- | :--- | :--- |
| **Backend Core APIs & Authentication**<br>`Backend/auth/*`, `Backend/routers/*` | **Ramit** | **Prince Savaliya** & **Yagnik N.** | • Unit & White-Box Testing<br>• Black-Box API Boundary Testing | • JWT token issuance, refresh, and expiration.<br>• RBAC unauthorized access (403 Forbidden).<br>• Edge-case query parameters & invalid JSON payloads. |
| **GenAI LangGraph Risk Pipeline**<br>`Backend/externalservies/LangGraph/*` | **Tirth Patel** | **Ramit** & **Prince Savaliya** | • White-Box Integration Testing<br>• Fallback & Grounding Verification | • Deterministic fallback when Gemini API key is missing.<br>• Zero hallucination of repository metrics.<br>• Extreme telemetry inputs (0 commits, 10,000 commits). |
| **Frontend UI Dashboard & Theming**<br>`Frontend/src/pages/*`, `Frontend/src/components/*` | **Darpan** | **Yagnik N.** & **Om Patel** | • GUI / Interaction Testing<br>• Responsive & Cross-Browser Testing | • Form validation on Login, SignUp, Create Project.<br>• Responsive layout on Mobile (375px), Tablet, Desktop.<br>• Correct `#004643` & `#FF8A95` theme rendering. |
| **Database Schemas & Sync Queries**<br>`Backend/database.py`, `Backend/persistence.py` | **Om Patel** | **Ramit** & **Shah Varshil** | • Persistence Parity Testing<br>• Index & Query Performance Testing | • Parity between `mongomock` and live MongoDB 7.0.<br>• Unique index constraints on user emails and repo URLs.<br>• Aggregation pipeline speed for project telemetry. |
| **Docker, Multi-Stage & Cloud Deployment**<br>`Dockerfile`, `render.yaml`, `docker-compose.yml` | **Shah Varshil** | **Prince Savaliya** & **Yagnik N.** | • Deployment & Smoke Testing<br>• Environment & Port Binding Testing | • Dynamic `$PORT` binding on Render.<br>• Container restart stability (`unless-stopped`).<br>• Multi-stage image size minimization (<250MB). |
| **Non-Functional Performance & Security**<br>Entire Deployed System | **Yagnik N.** | **Shah Varshil** & **Tirth Patel** | • Non-Functional Testing (NFR)<br>• Security & Secret Penetration | • API response latency < 500ms on Render.<br>• Log sanitization (verify tokens/keys are masked with `<REDACTED>`).<br>• 50 concurrent requests stress test. |
| **Mutation Testing Suite**<br>`Backend/routers/threshold_router.py`, `Backend/reporting/*` | **Prince Savaliya** | **Ramit** & **Tirth Patel** | • Mutation Testing (`mutmut`) | • Inject mutant operators (e.g. `>` to `>=`, `+` to `-`).<br>• Measure mutation score (Target: $\ge 80\%$ mutants killed).<br>• Document surviving mutants and add missing assertions. |
| **System & Acceptance Testing (UAT)**<br>All 6 Stakeholder User Stories | **Gaurav Rathod** | **Darpan** & **Om Patel** | • System Black-Box Testing (UAT) | • Trace each User Story from input to expected output.<br>• Validate acceptance criteria (Gherkin scenarios).<br>• Compile Black-Box Equivalence Partitioning matrix. |
| **UML & Runtime Dynamic Verification**<br>System Architecture & Diagrams | **Shivani** | **Ramit** & **Darpan** | • Architectural Conformance Testing | • Verify that API call sequences match Sequence Diagrams.<br>• Verify Project Health State transitions match State Machine. |
| **Bug & Incident Coordination**<br>Slack `#testing-bugs` Channel | **Vandit** | **All Team Members** | • Defect Logging & Traceability Proof | • Log every bug raised during peer testing into Slack.<br>• Record resolution commit SHA and verify bug closure.<br>• Export defect log as teamwork and testing evidence. |

---

### 5.3 Concrete Testing Execution Commands & Toolchain

To ensure your team can run these tests immediately without confusion:

```bash
# 1. Backend Unit Testing & Coverage Report (Prince Savaliya)
uv run --with-requirements requirements.txt --with mongomock pytest Backend/tests/ --cov=Backend --cov-report=html --cov-report=term

# 2. Frontend Unit & Component Testing (Yagnik N. / Prince Savaliya)
npm --prefix Frontend test -- --run

# 3. Frontend Build & Static Typecheck (Darpan / Yagnik N.)
npm --prefix Frontend run build

# 4. Mutation Testing Execution (Prince Savaliya)
# Run mutmut on critical business logic modules
uv run mutmut run --paths-to-mutate=Backend/routers/threshold_router.py
uv run mutmut results
uv run mutmut show <mutant_id>

# 5. Non-Functional Latency & Health Check Benchmark (Yagnik N.)
# Measure live Render production response time
curl -o /dev/null -s -w 'HTTP: %{http_code} | Total Time: %{time_total}s | Connect: %{time_connect}s\n' https://kavach-backend.onrender.com/api/health
```

---

## 6. Master Timeline & Daily Milestones (Leading to Dec 3 Deadline)

```
[Today: Nov 23] ───────► [Nov 24 - 26] ───────► [Nov 27 - 29] ───────► [Nov 30 - Dec 1] ──────► [Dec 2 - 3]
  • Work Allocation       • Doc Drafts (FR,        • UML Diagrams          • Mutation & NFR        • Physical Submission
  • Git Tracks Created      Design, DB, Tests)       Finalized               Testing Complete        (Dec 3, 5:00 PM)
  • Template Setup        • Coverage Reports       • PPT 10-Slides Draft   • Live Rehearsal        • Final ZIP & Google Form
                          • Live URL Live Check    • Traceability Matrix   • Demo Polish             (Dec 3, 11:59 PM)
```

| Date | Target Milestone | Responsible Tracks |
| :--- | :--- | :--- |
| **Nov 23 – 24** | **Kickoff & Testing Setup:** Set up folders in Git, establish Slack `#testing-bugs` channel, verify live deployment on Render. | All Team Members |
| **Nov 25 – 26** | **Requirements, System Design & Stage 1 Testing:** Finalize FR/NFR/Use Cases (Gaurav), System & Object Design (Ramit), LangGraph Architecture (Tirth), Unit Test Coverage reports (Prince). | Gaurav, Ramit, Tirth, Prince |
| **Nov 27 – 28** | **UML Diagrams & Stage 2/3 GUI Testing:** Produce all Class, Sequence, Activity, and State diagrams (Shivani, Om). Run GUI & cross-browser tests (Yagnik, Om). Document UI/UX wireframes (Darpan). | Shivani, Om, Darpan, Yagnik |
| **Nov 29 – 30** | **Stage 4/5/6 Testing (Mutation, NFR, System):** Complete mutation testing (Prince), NFR security/latency reports & Black-box matrices (Yagnik), RTM (Gaurav), Slack defect logs (Vandit). | Prince, Yagnik, Gaurav, Vandit |
| **Dec 01** | **Slides & Demo Polish:** Finalize strict 10-slide PPT (Yagnik). Rehearse live demonstration (Darpan, Varshil). Compile Contribution Document (Varshil). | Yagnik, Darpan, Varshil, Team |
| **Dec 02** | **Full Team Dry Run:** Full team 20-minute rehearsal (5 min PPT + 10 min Demo + 5 min Viva). Package `<group_No>.zip` and test Google Drive link permissions. | All Team Members |
| **Dec 03 (05:00 PM)** | **FIRM DEADLINE 1:** Submit printed, signed Contribution Document to Prof. Saurabh Tiwari's FB-1 letter box or office. | **Shah Varshil (Group Leader)** |
| **Dec 03 (11:59 PM)** | **FIRM DEADLINE 2:** Submit Google Form (ZIP link, Live Deployment URL). Apply GitHub repository code freeze. | **Shah Varshil (Group Leader)** |

---

## 7. Pre-Submission Verification Checklist

- [ ] **Physical Contribution Document** delivered to Prof. Saurabh Tiwari's FB-1 letter box before **Dec 3, 5:00 PM**.
- [ ] **Single ZIP File** named `<group_No>.zip` created with every document as a separate file.
- [ ] **Google Drive Link** set to *"Anyone with the link can view"* (test in Incognito mode!).
- [ ] **Live Deployment URL** verified working without crashes, with pre-loaded demo project.
- [ ] **Strict 10-Slide PPT** matches exactly S1 through S10 structure.
- [ ] **Per-Sprint Diagrams:** Class and Sequence diagrams included for each of Sprint 1, 2, 3, and 4.
- [ ] **All 5 Testing Reports Included:**
  - [ ] Unit Testing Report with code coverage % (PyTest + Vitest).
  - [ ] System Testing Report with Black-Box Equivalence Partitioning matrix.
  - [ ] GUI Testing Report with responsive layout & form interaction results.
  - [ ] Mutation Testing Report with calculated mutation score and mutant analysis.
  - [ ] Non-Functional Testing Report with latency benchmarks and security tests.
- [ ] **Peer Cross-Testing Matrix** verified with bug logs in Slack `#testing-bugs`.
- [ ] **Slack Evidence Document** finalized with screenshots proving teamwork.
- [ ] **All 10 Team Members** prepared for in-person presentation and individual Viva.
- [ ] **Zero Commits** pushed to GitHub after **Dec 3, 11:59 PM**.
