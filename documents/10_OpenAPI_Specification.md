# OpenAPI & Swagger API Specification

> **Course:** IT314: Software Engineering (Autumn 2026–27)  
> **Project:** AI Software Project Health & Risk Analyzer  
> **API Version:** 0.1.0  
> **OpenAPI Specification Standard:** OpenAPI 3.1.0  
> **Canonical Schema Export:** [`documents/openapi.json`](openapi.json)

---

## 1. Overview & Interactive Documentation

The **AI Software Project Health & Risk Analyzer** exposes a RESTful web service built with FastAPI. All endpoints are fully documented in compliance with the OpenAPI 3.1.0 standard.

When running the backend server locally or in production, the interactive API explorers are available at:

| Interface | URL | Description |
|---|---|---|
| **Swagger UI** | `http://localhost:5000/docs` | Interactive API sandbox allowing authenticated testing directly from the browser. |
| **ReDoc** | `http://localhost:5000/redoc` | Clean, structural API reference documentation with schema drill-downs. |
| **Raw JSON Schema** | `http://localhost:5000/openapi.json` | Complete machine-readable OpenAPI 3.1.0 JSON payload. |

---

## 2. Authentication & Authorization Architecture

All protected endpoints utilize **Bearer Token Authentication** using JSON Web Tokens (JWT).

```http
Authorization: Bearer <access_token>
```

### Security Schemes (OpenAPI Definition)

```yaml
components:
  securitySchemes:
    HTTPBearer:
      type: http
      scheme: bearer
      bearerFormat: JWT
      description: Enter the JWT access token received from POST /auth/login or POST /auth/signup.
```

### Role-Based Access Control (RBAC) Levels

Endpoints enforce role-based access checks through FastAPI dependency injection (`require_role`):

1. **Public / Unauthenticated**: Health check (`/health`), User registration (`/auth/signup`), User login (`/auth/login`).
2. **Authenticated (`developer` / `member`)**: Project listing, viewing permitted project health summaries, inspecting own contributor activity, viewing advisory explanations.
3. **Project Manager (`project_manager` / `lead`)**: Milestone pacing, schedule risk analysis, status report generation, report scheduling, advisory recommendations.
4. **Project Owner (`owner`)**: Project threshold adjustments (`PUT /api/projects/{id}/thresholds`), repository synchronization triggers, member role management.
5. **System Administrator (`admin`)**: Cross-project administrative privileges, user account deactivation (`POST /api/users/{id}/deactivate`), global audit log access.

---

## 3. API Route Directory (Categorized)

The application organizes endpoints into cohesive domain routers under `/api`:

### 3.1. Authentication & Session Management

| Method | Endpoint | Access Level | Description | Status Code |
|---|---|---|---|---|
| `POST` | `/auth/signup` | Public | Registers a new user account with hashed credentials. | `201 Created` |
| `POST` | `/auth/login` | Public | Validates credentials and returns JWT access token. | `200 OK` |
| `POST` | `/auth/logout` | Authenticated | Stateless session termination (client discards token). | `200 OK` |
| `GET` | `/auth/me` | Authenticated | Retrieves profile of currently authenticated user. | `200 OK` |

### 3.2. User Lifecycle Management (Admin Only)

| Method | Endpoint | Access Level | Description | Status Code |
|---|---|---|---|---|
| `POST` | `/api/users/{id}/deactivate` | **Admin Only** | Sets `is_active: false` on the target user account and immediately invalidates active sessions in `get_current_user`. | `200 OK` |

### 3.3. Project Management

| Method | Endpoint | Access Level | Description | Status Code |
|---|---|---|---|---|
| `GET` | `/api/projects` | Authenticated | Lists all projects associated with the authenticated user. | `200 OK` |
| `POST` | `/api/projects` | Authenticated | Creates a new project and designates the creator as Owner. | `201 Created` |
| `GET` | `/api/projects/{id}` | Member / Admin | Retrieves comprehensive project metadata and member list. | `200 OK` |
| `PUT` | `/api/projects/{id}` | Owner / Admin | Updates project configuration details (name, description, repo URL). | `200 OK` |
| `DELETE` | `/api/projects/{id}` | Owner / Admin | Removes or archives a project entity. | `200 OK` |

### 3.4. Repository Integration & Branch Discovery

| Method | Endpoint | Access Level | Description | Status Code |
|---|---|---|---|---|
| `POST` | `/api/repositories/connect` | Member / Owner | Binds a remote GitHub repository to an existing project. | `200 OK` |
| `GET` | `/api/repositories/branches` | Authenticated | Proxies remote branch lookup using server `GITHUB_TOKEN` to prevent rate-limit exhaustion. | `200 OK` |
| `POST` | `/api/projects/{id}/sync` | Member / Owner | Triggers background data ingestion (commits, PRs, issues). | `202 Accepted` |

### 3.5. Health & Risk Analysis Thresholds

| Method | Endpoint | Access Level | Description | Status Code |
|---|---|---|---|---|
| `GET` | `/api/projects/{id}/thresholds` | Member / Admin | Retrieves project risk thresholds (stale PR hours, stale issue days, workload ratio, bus factor). | `200 OK` |
| `PUT` | `/api/projects/{id}/thresholds` | Owner / Lead / Admin | Configures customized thresholds with boundary validation. | `200 OK` |

### 3.6. Health Indicators & Deterministic Metrics

| Method | Endpoint | Access Level | Description | Status Code |
|---|---|---|---|---|
| `GET` | `/api/projects/{id}/health-summary` | Member / Admin | Computes the transparent 0–100 Composite Health Index. | `200 OK` |
| `GET` | `/api/projects/{id}/bottlenecks` | Member / Admin | Identifies PR review queues and aging unreviewed pull requests (> 48h). | `200 OK` |
| `GET` | `/api/projects/{id}/workload` | Member / Admin | Analyzes contributor commit distributions and bus-factor concentration. | `200 OK` |
| `GET` | `/api/projects/{id}/stale-issues` | Member / Admin | Detects issues inactive beyond the project's configured threshold (> 14d). | `200 OK` |
| `GET` | `/api/projects/{id}/schedule-risk` | Member / Admin | Evaluates milestone velocity and sprint deadline slippage. | `200 OK` |

### 3.7. AI-Assisted Explanations, Reports & Delivery

| Method | Endpoint | Access Level | Description | Status Code |
|---|---|---|---|---|
| `POST` | `/api/projects/{id}/reports` | PM / Lead / Admin | Generates a synthesized status report using prompt-guarded LLM synthesis. | `201 Created` |
| `GET` | `/api/projects/{id}/reports` | Member / Admin | Retrieves historical project status reports. | `200 OK` |
| `GET` | `/api/projects/{id}/reports/{reportId}` | Member / Admin | Fetches detailed status report narrative, risk flags, and recommendations. | `200 OK` |
| `GET` | `/api/projects/{id}/reports/{reportId}/pdf` | Member / Admin | Exports and streams status report formatted as a downloadable PDF document. | `200 OK` |
| `GET` | `/api/projects/{id}/recommendations` | PM / Lead / Admin | Generates advisory, non-prescriptive engineering recommendations. | `200 OK` |
| `POST` | `/api/projects/{id}/reports/{reportId}/deliver` | PM / Admin | Dispatches report summary to configured Slack and Email delivery channels. | `200 OK` |

### 3.8. System Health & Probes

| Method | Endpoint | Access Level | Description | Status Code |
|---|---|---|---|---|
| `GET` | `/health` / `/api/health` | Public | Liveness probe returning operational status of service. | `200 OK` |

---

## 4. Standard Response & Error Formats

All API endpoints return JSON payloads with standard HTTP status codes:

### Success Responses
- `200 OK`: Request succeeded; returns data entity or message.
- `201 Created`: Resource successfully created (e.g. project creation, report generation).
- `202 Accepted`: Asynchronous operation queued (e.g. background repository sync).

### Client & Validation Errors
- `400 Bad Request`: Malformed request parameters (e.g. invalid MongoDB ObjectId format).
  ```json
  {
    "detail": "Invalid user ID format."
  }
  ```
- `401 Unauthorized`: Token missing, expired, invalid, or belonging to a deactivated user account.
  ```json
  {
    "detail": "Account is deactivated."
  }
  ```
- `403 Forbidden`: Authenticated user lacks permission to execute the action or access the project.
  ```json
  {
    "detail": "You do not have permission to perform this action."
  }
  ```
- `404 Not Found`: Target resource does not exist in the database.
  ```json
  {
    "detail": "Project not found."
  }
  ```
- `422 Unprocessable Entity`: Payload failed Pydantic schema validation (e.g. out-of-bounds decimal).
  ```json
  {
    "detail": [
      {
        "loc": ["body", "workload_imbalance_ratio"],
        "msg": "Input should be greater than or equal to 1.01",
        "type": "greater_than_equal"
      }
    ]
  }
  ```

### Server & Database Errors
- `500 Internal Server Error`: Unhandled application exception. Traceback is logged server-side and an opaque message is returned to the client to avoid leaking internals.
- `503 Service Unavailable`: Database or critical external infrastructure unreachable.

---

## 5. Regenerating OpenAPI Specification

To regenerate the `documents/openapi.json` file from the current codebase:

```bash
python scripts/export_openapi.py --output documents/openapi.json
```
