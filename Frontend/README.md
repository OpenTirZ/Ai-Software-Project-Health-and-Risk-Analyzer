# Aegis AI - AI Software Project Health and Risk Analyzer

Frontend implementation for **Sprint 1: Workflow Onboarding (Login -> Create Project -> Connect GitHub Repository)** built with React 19, TypeScript, Vite, and Tailwind CSS.

---

## 🚀 Sprint 1 Flow

The frontend implements the complete Sprint 1 workflow:
1. **Login & Signup (`/login`, `/signup`)**
   - Email format validation (`name@domain.com`)
   - Password requirements (min 6 chars for login, min 8 chars for signup)
   - Password confirmation matching
   - Loading states on form submission
   - Inline field error messages and API failure banners
2. **Project Creation (`/create-project`)**
   - Step 1 of onboarding wizard
   - Project name validation (min 3 chars, alphanumeric/hyphens)
   - Project type selector (Backend, Frontend, Fullstack)
   - Project description
   - Communicates with `POST /api/projects`
3. **Connect GitHub Repository (`/connect-repo`)**
   - Step 2 of onboarding wizard
   - GitHub URL regex validation (`https://github.com/owner/repository`)
   - Default branch configuration (`main`, `master`, custom)
   - Private repository toggle with Personal Access Token (PAT)
   - Communicates with `POST /api/repositories/connect`
   - Success confirmation and automatic transition to project overview

---

## 🛠️ Getting Started

### 1. Install Dependencies
```bash
npm install
```

### 2. Environment Configuration
Copy the example `.env` file:
```bash
cp .env.example .env
```
Settings:
- `VITE_API_BASE_URL`: Base URL of your backend API (default: `http://localhost:8000`).
  - Automatically routes authentication requests to `/auth/login`, `/auth/signup`, `/auth/me`.
  - Automatically routes project & repository operations to `/api/projects`, `/api/projects/{id}`.
- `VITE_USE_MOCK`: Set to `false` (default) to connect to the live FastAPI backend. Defaults gracefully to fallback simulation if the backend is offline.

### 3. Running Backend (FastAPI)
From your backend directory:
```bash
uvicorn Backend.main:app --reload --port 8000
```
Make sure `CORS_ALLOWED_ORIGINS` includes `http://localhost:5173`.

### 3. Run Development Server
```bash
npm run dev
```
Open `http://localhost:5173` in your browser.

### 4. Build for Production
```bash
npm run build
```

---

## 📂 Project Structure

```
src/
├── services/
│   └── api.ts                 # API service layer (authApi, projectApi, repositoryApi)
├── pages/
│   ├── Login.tsx              # Login page with validation & API error alerts
│   ├── SignUp.tsx             # Signup page with confirmation check & API error alerts
│   ├── CreateProject.tsx      # Step 1: Project Details form with validation
│   ├── ConnectRepository.tsx  # Step 2: GitHub repo connection form with regex check
│   ├── Projects.tsx           # All Repositories list
│   ├── ProjectOverview.tsx    # Project dashboard with health gauge & sprint velocity
│   ├── HealthAnalysis.tsx     # 4-factor health score breakdown
│   ├── RiskAnalysis.tsx       # Vulnerability & risk classification inspector
│   ├── Contributors.tsx       # Team telemetry & bus factor analysis
│   ├── Activity.tsx           # Commits, PRs, and Issues tabbed tables
│   ├── Reports.tsx            # Compliance reports & PDF export
│   └── UserProfile.tsx        # User settings & security
├── components/
│   ├── Layout.tsx             # Shared dashboard shell
│   ├── Sidebar.tsx            # Sidebar navigation
│   └── TopBar.tsx             # Breadcrumbs & repository switcher
├── data/
│   └── mockData.ts            # Mock repositories and sprint data
├── types/
│   └── index.ts               # TypeScript data models
├── App.tsx                    # View router coordinating Sprint 1 flow
└── main.tsx                   # Entry point
```
