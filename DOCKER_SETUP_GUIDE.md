# Docker Setup & Full-Stack Deployment Guide

This guide explains how to set up, run, and deploy the entire **AI Software Project Health & Risk Analyzer** stack (React Frontend + FastAPI Backend + MongoDB) using Docker and Docker Compose.

---

## 1. System Architecture in Docker

When deployed with `docker-compose.yml`, three interconnected containers are orchestrated on a shared network:

```text
       Browser (User)
             │
             ├──► [Frontend SPA] (Port 3000) ── Nginx Web Server
             │         │
             │         └── (Reverse Proxy /api/ & /auth/)
             │                  │
             └──► [FastAPI Backend] (Port 8000) ── Uvicorn ASGI Server
                       │
                       ├──► [Local MongoDB Container] (Port 27017, default)
                       └──► [MongoDB Atlas Cloud Cluster] (if MONGO_URI in .env)
```

---

## 2. Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running.
- (Optional) MongoDB Atlas account and connection string (or use the included local MongoDB container).

---

## 3. Environment Configuration (`.env`)

Create a `.env` file in the project root:

```env
# Database Configuration (Atlas Cloud or leave empty to use local container)
MONGO_URI=mongodb+srv://<username>:<password>@<cluster>.mongodb.net/?retryWrites=true&w=majority
MONGO_DATABASE=project_health

# Security & JWT Tokens
JWT_SECRET_KEY=your-secure-random-secret-key-at-least-32-chars
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Upstream Integrations
GITHUB_TOKEN=your_optional_github_personal_access_token

# CORS Origins
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173,http://localhost:80,http://127.0.0.1:3000
```

> **Note**: If `MONGO_URI` is not provided, the stack automatically connects to the internal `mongodb` container (`mongodb://mongodb:27017/project_health`).

---

## 4. Single-Command Launch

From the repository root:

```bash
docker compose up --build
```

To run in the background (detached mode):
```bash
docker compose up -d
```

To stop all services:
```bash
docker compose down
```

---

## 5. Accessing the Application

Once the containers are healthy:

| Service | URL | Description |
| :--- | :--- | :--- |
| **Frontend Web Application** | [http://localhost:3000](http://localhost:3000) | Production React SPA served via Nginx |
| **FastAPI Interactive Docs** | [http://localhost:8000/docs](http://localhost:8000/docs) | Interactive Swagger UI for live API testing |
| **ReDoc Documentation** | [http://localhost:8000/redoc](http://localhost:8000/redoc) | Clean API schema reference |
| **Backend Health Check** | [http://localhost:8000/api/health](http://localhost:8000/api/health) | System health & liveness probe |

---

## 6. Running the Test Suite in Docker

Run all 512+ unit and integration tests inside an isolated test container:

```bash
docker compose run --rm backend pytest -v
```

Run specific test modules:
```bash
docker compose run --rm backend pytest Backend/tests/test_health_summary.py -v
docker compose run --rm backend pytest Backend/tests/test_persistence_telemetry.py -v
docker compose run --rm backend pytest Backend/tests/test_project_management.py -v
```

---

## 7. Useful Docker Commands

| Task | Command |
| :--- | :--- |
| **Rebuild & Start All** | `docker compose up --build` |
| **Start in Background** | `docker compose up -d` |
| **View Backend Logs** | `docker compose logs -f backend` |
| **View Frontend Logs** | `docker compose logs -f frontend` |
| **Restart Stack** | `docker compose restart` |
| **Stop & Remove Volumes** | `docker compose down -v` |
| **Open Container Shell** | `docker compose exec backend bash` |

---

## 8. Cloud Production Deployment (Render & Cloud Services)

The application is configured for cloud deployment on **Render** (via [`render.yaml`](render.yaml)) as well as Vercel / Railway / AWS:

### Production Architecture
- **Backend Service (Render Web Service):**
  - **Runtime:** Python 3.12 (Multi-stage container / native python)
  - **Start Command:** `uvicorn Backend.main:app --host 0.0.0.0 --port $PORT`
  - **Health Check Path:** `/api/health`
  - **Production Base URL:** `https://<backend-app-name>.onrender.com/api`
- **Frontend SPA (Render Static Site / Vercel):**
  - **Build Command:** `npm install && npm run build`
  - **Publish Directory:** `Frontend/dist` (or `dist` with Root Directory set to `Frontend`)
  - **Routing Rewrite:** `/* -> /index.html` (Status: 200)
  - **Production URL:** `https://<frontend-app-name>.onrender.com` (or `.vercel.app`)

### Environment & CORS Linking
- In the Backend Web Service:
  - `CORS_ALLOWED_ORIGINS=https://<frontend-app-name>.onrender.com`
- In the Frontend Static Site / Vercel:
  - `VITE_API_BASE_URL=https://<backend-app-name>.onrender.com/api`
