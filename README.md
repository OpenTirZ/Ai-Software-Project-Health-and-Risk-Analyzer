# AI Software Project Health & Risk Analyzer

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![MongoDB Atlas](https://img.shields.io/badge/MongoDB_Atlas-Cloud_DB-47A248?style=for-the-badge&logo=mongodb&logoColor=white)](https://www.mongodb.com/atlas)
[![Tests Passing](https://img.shields.io/badge/Tests-227%20Passed%20(100%25)-brightgreen?style=for-the-badge&logo=pytest&logoColor=white)](https://docs.pytest.org/)
[![Agile Scrum](https://img.shields.io/badge/Agile-SCRUM%20Process-orange?style=for-the-badge)](./documents/9_Sprint_Plan.md)
[![Milestone](https://img.shields.io/badge/Milestone-Sprint%201%20%26%202%20Delivered-blueviolet?style=for-the-badge)](#milestone-status-sprints-1--2-complete)

> **An intelligent, data-driven platform that connects with software development workflows (GitHub repositories, commits, pull requests, issues, and sprint artifacts) to evaluate project health, detect delivery bottlenecks and workload imbalances, and generate grounded GenAI risk intelligence and actionable executive recommendations.**

---

## 📌 Milestone Status (Sprints 1 & 2 Complete)

> **Evaluation Phase:** Sprint 1 & Sprint 2 Core Telemetry & Health Engine Complete  
> **Backend Architecture:** Production-Ready FastAPI with Microservice and Sub-DAO Separation  
> **Test Status:** ✅ **227 / 227 Tests Passing (100% Pass Rate)**  
> **Containerization:** ✅ **Fully Dockerized & Validated with Compose**  
> **Database:** ✅ **MongoDB Atlas with Compound Unique Indexing** across 6 Collections  
> **Live API Documentation:** Interactive Swagger UI at `http://localhost:8000/docs`

### Deliverable Summary (Sprint 1 Foundation & Sprint 2 Engine Delivered)

| Milestone Area | Status | Verification & Evidence |
| :--- | :---: | :--- |
| **Requirements & Elicitation** | ✅ **Done** | [10 Elicitation & Planning Specs](./documents/) across 6 Stakeholder groups |
| **Authentication & Security** | ✅ **Done** | JWT authentication, bcrypt hashing, stateless token management (`/auth/*`) |
| **Role-Based Access Control (RBAC)**| ✅ **Done** | Granular roles (`admin`, `project_manager`, `developer`) with route guards |
| **Project Management Service** | ✅ **Done** | Full CRUD for project lifecycle & repository association (`/api/projects`) |
| **GitHub Data Synchronization** | ✅ **Done** | Live commit & contributor ingestion, pagination, rate-limit handling |
| **Telemetry Persistence Sub-DAO** | ✅ **Done** | Isolated DAO layer (`Backend/persistence_telemetry.py`) for PRs, issues, and milestones |
| **Cloud Persistence & Indexing** | ✅ **Done** | MongoDB Atlas compound unique keys on commits, contributors, PRs, issues, and milestones |
| **Deterministic Health Engine** | ✅ **Done** | Composite 0–100 index (`Backend/analysis/health_summary.py`) with dynamic re-weighting |
| **Project Health & Metrics API** | ✅ **Done** | Summary (`/api/projects/{id}/health-summary`) & breakdown (`/api/projects/{id}/metrics/breakdown`) |
| **LangGraph Workflow V1 Pipeline**| ✅ **Done** | StateGraph architecture (`Backend/externalservies/LangGraph/pipeline.py`) for GenAI insights |
| **Data Redaction & Sanitization**| ✅ **Done** | Production logging filter masking tokens, passwords, secrets, and Mongo URIs |
| **Containerization & CI/CD** | ✅ **Done** | Multi-stage `Dockerfile`, `docker-compose.yml`, non-root execution |
| **Automated Testing Suite** | ✅ **Done** | **227 automated tests** across 7 test suites with 100% mocked external dependencies |

---

## 📖 Table of Contents

- [Problem Statement & Vision](#-problem-statement--vision)
- [System Architecture](#-system-architecture)
- [Demonstrable Features](#-demonstrable-features)
- [API Endpoints Directory](#-api-endpoints-directory)
- [Software Engineering & Agile Process](#-software-engineering--agile-process)
- [Quick Start & Setup Guide](#-quick-start--setup-guide)
- [Test Suite & Quality Verification](#-test-suite--quality-verification)
- [Database Schema & Design](#-database-schema--design)
- [Sprint Roadmap & Milestone Progress](#-sprint-roadmap--milestone-progress)
- [Project Directory Structure](#-project-directory-structure)
- [Team Members & Contributions](#-team-members--contributions)

---

## 🎯 Problem Statement & Vision

### The Problem
Modern software development generates immense operational telemetry scattered across disparate platforms—commits, branch activities, code reviews, issue discussions, and sprint boards. Engineering leads and project managers struggle to synthesize this raw data:
- **Invisible Delivery Bottlenecks:** Pull requests languish in review queues undetected.
- **Workload Imbalances & Burnout:** Commit velocity and issue volume disproportionately fall on a few core contributors without management awareness.
- **Schedule Slippage:** Stale milestones and drift between sprint commitments and repository activity trigger unexpected release delays.
- **Superficial Metrics:** Existing dashboards calculate vanity metrics (lines of code, commit counts) without providing explainable reasons or remediation paths.

### Our Solution
The **AI Software Project Health & Risk Analyzer** combines deterministic metric computation with grounded GenAI reasoning:
1. **Connect & Synchronize:** Ingests live telemetry from GitHub repositories without cloning entire codebases.
2. **Deterministic Metric Engine:** Computes transparent, explainable health scores (bus factor risk, review latency, commit volatility).
3. **GenAI Advisory Layer:** Uses bounded LLM workflows (LangGraph V1) to translate quantitative thresholds into human-understandable risk narratives and prescriptive actions.
4. **Role-Tailored Dashboards:** Provides appropriate views for individual developers, team leads, scrum masters, and executive stakeholders.

---

## 🏗 System Architecture

```text
                                  ┌─────────────────────────┐
                                  │   Frontend Application   │
                                  │   (React.js / Swagger)  │
                                  └────────────┬────────────┘
                                               │ HTTP / JSON
                                               ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                FastAPI Backend Service                                 │
│                                                                                        │
│  ┌────────────────────────────┐  ┌────────────────────────────┐  ┌──────────────────┐  │
│  │   Authentication & RBAC    │  │ Project Lifecycle Service  │  │  Secret Masking  │  │
│  │  (JWT / Bcrypt / 3 Roles)  │  │   (CRUD / Ownership Valid) │  │  Logging Filter  │  │
│  └─────────────┬──────────────┘  └─────────────┬──────────────┘  └─────────┬────────┘  │
│                │                               │                           │           │
│                └───────────────────────┬───────┴───────────────────────────┘           │
│                                        ▼                                               │
│                         ┌─────────────────────────────┐                                │
│                         │  GitHub Data Ingestion Bus  │                                │
│                         │ (Commits, Contribs, Issues) │                                │
│                         └──────────────┬──────────────┘                                │
│                                        ▼                                               │
│                         ┌─────────────────────────────┐                                │
│                         │  Deterministic Risk Engine  │                                │
│                         │  & Dynamic Re-weighting     │                                │
│                         └──────────────┬──────────────┘                                │
└────────────────────────────────────────┼───────────────────────────────────────────────┘
                                         │
                    ┌────────────────────┴────────────────────┐
                    ▼                                         ▼
     ┌─────────────────────────────┐           ┌─────────────────────────────┐
     │      GitHub REST API        │           │    MongoDB Atlas Cluster    │
     │  - Rate-limiting handler    │           │  - Users & Projects         │
     │  - Token authentication     │           │  - Commits & Contributors   │
     │  - Pagination traversal     │           │  - PRs, Issues & Milestones │
     └─────────────────────────────┘           └─────────────────────────────┘
                    │                                         │
                    └────────────────────┬────────────────────┘
                                         │
                                         ▼
                         ┌───────────────────────────────┐
                         │   LangGraph Workflow V1       │
                         │   Multi-Node StateGraph AI    │
                         └───────────────────────────────┘
```

---

## ⚡ Demonstrable Features

### 1. Robust Authentication & User Management (`/auth`)
- **Self-Service Registration:** `/auth/signup` with validation, bcrypt password hashing, and duplicate email prevention.
- **Secure Token Generation:** `/auth/login` issuing HMAC-SHA256 JWT bearer tokens.
- **Identity Introspection:** `/auth/me` providing authenticated user session data and system role assignments.

### 2. Role-Based Access Control (RBAC)
- Distinct system roles: `admin`, `project_manager`, and `developer`.
- Declarative route-level authorization dependencies (`require_role(...)`).
- Comprehensive permission boundary enforcement preventing unauthorized data modifications.

### 3. Project Lifecycle Management (`/api/projects`)
- Multi-project creation and tracking linked to authenticated creator accounts.
- Configuration of target GitHub repositories (`githubRepoUrl`, default branches, sprint settings).
- Access control validation: Projects can only be accessed by owners or assigned team members.
- Configurable update endpoints allowing owners to modify tracking settings.

### 4. GitHub Telemetry & Data Ingestion Engine
- **Live Commit Synchronization (`/api/projects/{id}/sync-commits`):** Connects to GitHub API, extracts SHA, author, date, message, and branch, deduplicating via `(projectId, sha)`.
- **Live Contributor Synchronization (`/api/projects/{id}/sync-contributors`):** Fetches repository contributors with pagination and deduplicates via `(projectId, github_username)`.

### 5. Deterministic Composite Health & Risk Engine (`/api/projects/{id}/health-summary`, `breakdown`)
- **Composite 0–100 Health Index:** Dynamically aggregates dimensional health scores across bottlenecks, workload concentration, stale issues, and schedule risk:
  - `Good` (Score $\ge$ 75)
  - `Caution` (50 $\le$ Score < 75)
  - `At Risk` (Score < 50)
- **Dynamic Re-weighting & "Insufficient Data" Handling:** When optional telemetry (such as sprint milestones or PRs) is not configured, the system marks the indicator as `insufficient_data` and re-normalizes weights across available data rather than manufacturing false penalties.
- **Actionable Risk Flags:** Flags aging PRs (>48h), workload concentration (Bus Factor > 70%), and stale issues (>14d) with traceable evidence.
- **Dimensional Breakdown:** Exposes underlying metrics, normalized weights, and supporting records.

### 6. LangGraph Workflow V1 Pipeline (`Backend/externalservies/LangGraph`)
- **StateGraph Architecture:** Sequential multi-node pipeline tracking `ProjectHealthState` (input validation, contributor analysis, commit analysis, heuristic risk calculation, GenAI insights, JSON reporting).
- **Grounded LLM Integration:** Interfaces with chat-capable OpenRouter / OpenAI models with local fallbacks.

### 7. Modular Telemetry Persistence Sub-DAO (`Backend/persistence_telemetry.py`)
- **Decoupled Data Access:** Independent DAO routines for PRs, issues, milestones, and metric snapshots preventing `persistence.py` chokepoints.
- **Compound Unique Indexing:** Atlas uniqueness enforced on `(projectId, number)` and `(projectId, milestone_id)`.

### 8. Enterprise Security & Hardening
- **Automated Secret Redaction:** Custom logging filter intercepts and masks tokens, passwords, API keys, and connection strings from console output.
- **Centralized Exception Handling:** Standardized RFC-compliant JSON error responses across database failures, validation errors, and upstream GitHub outages.
- **CORS Configuration:** Safe cross-origin resource sharing configured for development and production origins.

---

## 🔌 API Endpoints Directory

All endpoints are demonstrable in real-time via the interactive Swagger interface at `http://localhost:8000/docs`:

| Tag | Method | Endpoint | Auth | Description |
| :--- | :---: | :--- | :---: | :--- |
| **System** | `GET` | `/api/health` | Public | System status, version info, and environment sanity check |
| **Auth** | `POST` | `/auth/signup` | Public | Register new user account with hashed credentials |
| **Auth** | `POST` | `/auth/login` | Public | Authenticate user and receive JWT access token |
| **Auth** | `POST` | `/auth/logout` | Public | Stateless session logout |
| **Auth** | `GET` | `/auth/me` | Bearer | Retrieve profile information and role of authenticated user |
| **Projects** | `POST` | `/api/projects` | Bearer | Create a new project and assign caller as owner |
| **Projects** | `GET` | `/api/projects` | Bearer | List all projects belonging to or shared with current user |
| **Projects** | `GET` | `/api/projects/{id}` | Bearer | Retrieve project metadata and GitHub integration settings |
| **Projects** | `PATCH` | `/api/projects/{id}` | Bearer (Owner) | Update project name, description, or repository target |
| **Data Sync**| `GET` | `/api/projects/{id}/contributors` | Bearer | Retrieve ingested contributors for a project |
| **Data Sync**| `POST` | `/api/projects/{id}/sync-contributors` | Bearer | Trigger live GitHub API sync for repository contributors |
| **Data Sync**| `GET` | `/api/projects/{id}/commits` | Bearer | Retrieve paginated list of ingested repository commits |
| **Data Sync**| `POST` | `/api/projects/{id}/sync-commits` | Bearer | Trigger live GitHub API ingestion for repository commits |
| **Metrics** | `GET` | `/api/projects/{id}/health-summary` | Bearer | Composite 0–100 health index, status (Good/Caution/At Risk), active flags, and summary narrative |
| **Metrics** | `GET` | `/api/projects/{id}/metrics/breakdown` | Bearer | Granular 4-dimensional breakdown with normalized weights and supporting telemetry evidence |

---

## 📋 Software Engineering & Agile Process

This project is developed strictly adhering to **Agile (SCRUM)** methodology and Software Engineering best practices. Complete documentation is maintained in the [`documents/`](./documents/) directory:

```
documents/
├── 1_Stakeholders.md                         # 6 Key Stakeholder Groups & Personas
├── 2_Elicitation_Tech.md                     # Elicitation Techniques (Interviews, Prototyping)
├── 3_Functional_Requirements.md              # FR Specifications (FR-01 through FR-21)
├── 4_NFR_Requirements.md                     # Non-Functional Requirements (Security, Performance)
├── 5_Domain_Requirements.md                  # Software Engineering & Git Domain Rules
├── 6_User_Stories_and_Acceptance_Criteria.md # Complete Backlog with INVEST Criteria
├── 7_Product_Backlog_Story_Points_Priority.md# Sizing & Story Point Estimations (110 pts total)
├── 8_Product_Epics.md                        # Epic Breakdown (E1 through E5)
├── 9_Sprint_Plan.md                          # 4-Sprint Cadence & Milestone Schedule
├── Final_Elicitation.md                      # Consolidated Requirement Elicitation Record
└── contributor_feature_report.md             # Contributor Feature Implementation & Testing
```

---

## 🚀 Quick Start & Setup Guide

### Option 1: Running with Docker (Recommended)

1. **Clone the repository:**
   ```bash
   git clone https://github.com/OpenTirZ/Ai-Software-Project-Health-and-Risk-Analyzer.git
   cd Ai-Software-Project-Health-and-Risk-Analyzer
   ```

2. **Configure environment variables:**
   Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
   Ensure your `.env` contains:
   ```env
   MONGO_URI=mongodb+srv://<username>:<password>@<cluster>.mongodb.net/?retryWrites=true&w=majority
   MONGO_DATABASE=project_health
   JWT_SECRET_KEY=your-secure-random-secret-key-at-least-32-chars
   JWT_ALGORITHM=HS256
   ACCESS_TOKEN_EXPIRE_MINUTES=1440
   GITHUB_TOKEN=your_github_personal_access_token
   OPENROUTER_API_KEY=your_openrouter_api_key
   ```

3. **Start the application container:**
   ```bash
   docker compose up --build
   ```

4. **Access the application:**
   - Interactive Swagger API: [http://localhost:8000/docs](http://localhost:8000/docs)
   - Alternative ReDoc API: [http://localhost:8000/redoc](http://localhost:8000/redoc)
   - Healthcheck: [http://localhost:8000/api/health](http://localhost:8000/api/health)

---

### Option 2: Running Locally with Python 3.12+

1. **Set up virtual environment:**
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On Linux / macOS:
   source venv/bin/activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the FastAPI server:**
   ```bash
   uvicorn Backend.main:app --reload --host 0.0.0.0 --port 8000
   ```

---

## 🧪 Test Suite & Quality Verification

Quality is enforced via an extensive **pytest** test suite with **100% mocked external dependencies** (no live GitHub API quota consumption or un-mocked cloud writes during testing).

### Running Tests
```bash
# In Docker:
docker compose run --rm backend pytest -v

# Locally with uv or pytest:
uv run --with-requirements requirements.txt --with pytest --with pytest-mock pytest -v
```

### Test Results Breakdown (227 Passing Tests)

```text
============================= test session starts =============================
platform win32 / linux -- Python 3.12+ / 3.13+, pytest-9.1.1, pluggy-1.6.0
collected 227 items

Backend/auth/test_auth.py .................................... [ 26%]
Backend/auth/test_roles.py .....                               [ 28%]
Backend/test_contributor_service.py .......................... [ 49%]
Backend/test_github_commits.py ............................... [ 66%]
Backend/tests/test_project_management.py ..................... [ 80%]
Backend/tests/test_health_summary.py ......................    [ 90%]
Backend/tests/test_persistence_telemetry.py .................. [100%]

============================= 227 passed in 26.4s =============================
```

- `test_auth.py` (60 tests): Signup, login, password hashing, token expiration, authorization header verification.
- `test_roles.py` (5 tests): Role hierarchy, permission matrix, forbidden role restrictions.
- `test_contributor_service.py` (47 tests): Contributor synchronization, duplicate prevention, GitHub error translations.
- `test_github_commits.py` (39 tests): Commit parsing, author resolution, pagination handling, network timeout resilience.
- `test_project_management.py` (32 tests): Project CRUD, ownership validation, tenant isolation, invalid ID protection.
- `test_health_summary.py` (22 tests): Composite health scoring, dynamic indicator re-weighting, PR bottlenecks, workload concentration, stale issues, and router endpoints.
- `test_persistence_telemetry.py` (22 tests): Sub-DAO CRUD for PRs, issues, milestones, metric snapshots, duplicate prevention, and compound index enforcement.

---

## 🗄 Database Schema & Design

The system utilizes **MongoDB Atlas** with pre-configured compound unique indexing to guarantee data integrity across asynchronous ingestions:

```text
Database: project_health
├── users
│   ├── _id (ObjectId), name, email (unique), password_hash, role
│   └── createdAt, updatedAt
├── projects
│   ├── _id (ObjectId), name, description, githubRepoUrl
│   ├── ownerId, members (array of user IDs)
│   └── syncStatus, lastSyncedAt, createdAt
├── commits
│   ├── _id (ObjectId), projectId (Ref -> projects._id), sha
│   ├── author, timestamp, message, branch, additions, deletions
│   └── ⚠️ Compound Index: (projectId: 1, sha: 1) [UNIQUE]
├── contributors
│   ├── _id (ObjectId), projectId (Ref -> projects._id), github_username
│   ├── avatar_url, profile_url, contributions, last_synced_at
│   └── ⚠️ Compound Index: (projectId: 1, github_username: 1) [UNIQUE]
├── pull_requests
│   ├── _id (ObjectId), projectId (Ref -> projects._id), number
│   ├── title, state (open/closed/merged), open_duration_hours, reviewers
│   └── ⚠️ Compound Index: (projectId: 1, number: 1) [UNIQUE]
├── issues
│   ├── _id (ObjectId), projectId (Ref -> projects._id), number
│   ├── title, state (open/closed), assignees, labels, comments_count
│   └── ⚠️ Compound Index: (projectId: 1, number: 1) [UNIQUE]
├── milestones
│   ├── _id (ObjectId), projectId (Ref -> projects._id), milestone_id
│   ├── title, state, due_on, open_issues, closed_issues
│   └── ⚠️ Compound Index: (projectId: 1, milestone_id: 1) [UNIQUE]
└── metric_snapshots
    ├── _id (ObjectId), projectId (Ref -> projects._id), calculatedAt
    ├── health_score, status, indicators, flags_count, weights_used
    └── ⚠️ Compound Index: (projectId: 1, calculatedAt: 1)
```

---

## 🗺 Sprint Roadmap & Milestone Progress

```text
Sprint 1: System Foundation & Security      [████████████████████] 100% (Completed)
Sprint 2: Activity Telemetry & Risk Engine  [████████████████████] 100% (Completed)
  ├── Live Commit Ingestion                 ✅ Done
  ├── Live Contributor Ingestion            ✅ Done
  ├── Telemetry Persistence & Atlas Indexes ✅ Done
  ├── Deterministic Health & Risk Engine    ✅ Done
  ├── Metric Router (/api/projects/{id}/*)  ✅ Done
  └── LangGraph Workflow V1 Pipeline        ✅ Done
Sprint 3: AI Reporting & Multi-Channel Delivery [░░░░░░░░░░░░░░░░░░░░]   0% (Upcoming)
  ├── LangGraph V2 Full Telemetry Expansion 🔄 Scheduled
  ├── Grounded GenAI Report Generation      🔄 Scheduled
  ├── PDF Export (Branded Multi-page)       🔄 Scheduled
  └── Slack & Email Automated Delivery      🔄 Scheduled
Sprint 4: UI Dashboard & Final Deployment   [░░░░░░░░░░░░░░░░░░░░]   0% (Upcoming)
  ├── React.js Interactive Dashboard        🔄 Planned
  ├── User Appeals & Flag Resolution Flow   🔄 Planned
  └── Production Cloud Deployment           🔄 Planned
```

---

## 📁 Project Directory Structure

```text
Ai-Software-Project-Health-and-Risk-Analyzer/
├── Backend/
│   ├── analysis/                    # Deterministic Analysis & Metric Engines
│   │   ├── __init__.py
│   │   └── health_summary.py        # Composite 0-100 Health Index & dynamic re-weighting
│   ├── auth/                        # JWT & RBAC Authentication Module
│   │   ├── dependencies.py          # FastAPI get_current_user injection
│   │   ├── roles.py                 # RBAC definitions & permission checkers
│   │   ├── router.py                # /auth/* endpoint definitions
│   │   ├── schemas.py               # Pydantic auth validation models
│   │   ├── security.py              # Bcrypt hashing & JWT encoding/decoding
│   │   ├── test_auth.py             # Auth test suite (60 tests)
│   │   └── test_roles.py            # RBAC test suite (5 tests)
│   ├── externalservies/             # Third-Party Integrations & AI Workflows
│   │   ├── LangGraph/               # LangGraph Workflow V1 Implementation
│   │   │   ├── pipeline.py          # Multi-node StateGraph telemetry pipeline
│   │   │   ├── README.md            # Pipeline documentation
│   │   │   └── Versions/            # Architecture diagrams (V1)
│   │   ├── commit_service.py        # Commit business logic & sync
│   │   ├── contributor_service.py   # Contributor aggregation & sync
│   │   └── github_commits.py        # GitHub REST client with pagination
│   ├── routers/                     # Core Business API Routers
│   │   ├── data_sync_router.py      # /api/projects/{id}/sync-commits | contributors
│   │   ├── metric_router.py         # /api/projects/{id}/health-summary | breakdown
│   │   └── project_router.py        # /api/projects CRUD endpoints
│   ├── schemas/                     # Shared Pydantic Models
│   │   └── project_schemas.py       # Project payload schemas
│   ├── tests/                       # Integration & End-to-End Tests
│   │   ├── test_health_summary.py   # Health engine & metric router tests (22 tests)
│   │   ├── test_persistence_telemetry.py # Sub-DAO & index tests (22 tests)
│   │   └── test_project_management.py # Project CRUD tests (32 tests)
│   ├── database.py                  # PyMongo connection & index management
│   ├── persistence.py               # Core repository data access layer (DAO)
│   ├── persistence_telemetry.py     # Isolated telemetry DAO (PRs, issues, milestones)
│   ├── test_contributor_service.py  # Contributor service unit tests (47 tests)
│   ├── test_github_commits.py       # GitHub ingestion unit tests (39 tests)
│   └── main.py                      # FastAPI App initialization & middleware
├── documents/                       # Software Engineering & Agile Documentation
│   ├── 1_Stakeholders.md
│   ├── 2_Elicitation_Tech.md
│   ├── 3_Functional_Requirements.md
│   ├── 4_NFR_Requirements.md
│   ├── 5_Domain_Requirements.md
│   ├── 6_User_Stories_and_Acceptance_Criteria.md
│   ├── 7_Product_Backlog_Story_Points_Priority.md
│   ├── 8_Product_Epics.md
│   ├── 9_Sprint_Plan.md
│   └── contributor_feature_report.md
├── Phases/                          # Phase-Wise Project Specifications
│   └── README.md
├── DOCKER_SETUP_GUIDE.md            # Comprehensive Docker & Atlas Setup Guide
├── Dockerfile                       # Multi-stage container specification
├── docker-compose.yml               # Container orchestration configuration
├── requirements.txt                 # Python project dependencies
├── .env.example                     # Environment configuration template
└── README.md                        # Master Project Documentation (This File)
```

---

## 👥 Team Members & Contributions

Developed by **Team OpenTirZ** for the Software Engineering Practicum:

| Member | Engineering Role | Core Contributions |
| :--- | :--- | :--- |
| **Shah Varshil** (`svarshil56`) | **Backend Lead & DevOps Engineer** | System architecture, Docker containerization & Compose orchestration, Composite Health Score Engine (`health_summary.py`), Metric Router (`/api/projects/{id}/health-summary`), Data Sync Router (`/sync-*`), and deployment pipelines. |
| **Vandit** | **Frontend Lead Developer** | Frontend architecture & user interface design using **React.js** (Authentication UI, Project Management Dashboard, Repository Connection, and Health telemetry views). |
| **Tirth Patel** (`Tirth9978`) | **Database Architect & LangGraph AI Engineer** | MongoDB Atlas cluster design, schema modeling, Telemetry Sub-DAO (`persistence_telemetry.py`), compound indexing strategy across 6 collections, and **LangGraph Workflow V1** implementation (`pipeline.py`) orchestrating commit/contributor telemetry into grounded GenAI insights. |
| **Ramit** (`ramit7707`) | **Authentication & Security Engineer** | Core JWT authentication system (`/auth/signup`, `/auth/login`, `/auth/me`), password hashing (Bcrypt), stateless session security, and 60+ automated test cases suite. |
| **Shivani Chaudhary** (`shivani`) | **Security & Quality Assurance Engineer** | Enterprise hardening, automated secret masking and token redaction filter in logging, centralized exception handling, and error response sanitization. |
| **Darpan Sherathiya** (`Darpan0610`) | **Backend Engineer (Git Analytics)** | Git commit ingestion pipeline, SHA-level deduplication logic, commit author parsing, and repository branch tracking. |
| **Gaurav Rathod** (`Gaurav Rathod`) | **Backend Engineer (Project Management & Metrics)** | Project lifecycle CRUD APIs (`/api/projects`), Pydantic schema validation, member ownership enforcement, and project management test suite. |
| **Prince Savaliya** (`Prince Savaliya`) | **Backend Engineer (GitHub Services)** | Contributor retrieval service, GitHub REST API client with pagination & rate-limiting, and contributor-to-project mapping. |
| **Yagnik N.** (`Yagnik N.`) | **Security, RBAC & Agile Process Lead** | Role-Based Access Control (RBAC) implementation, authorization route guards, stakeholder elicitation, user stories, and agile sprint documentation. |
| **Om Patel** (`ommalvaniya007@gmail.com`) | **Backend Engineer (Data Integration & Pipelines)** | GitHub commit history with dotenv auth, environment token resolution, issue telemetry ingestion pipeline, and background sync services. |

---

## 📜 License & Academic Integrity

This project is submitted for academic evaluation under the Software Engineering Curriculum. All rights reserved by the project authors. Built with industry best practices and clean architecture principles.
