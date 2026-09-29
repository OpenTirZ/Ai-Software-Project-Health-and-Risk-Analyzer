## Project Structure 
```
AI Software Project Health & Risk Analyzer
│
├── Frontend
│   ├── Authentication UI
│   ├── Project Management UI
│   ├── Repository Connection UI
│   ├── Dashboard
│   ├── Risk Dashboard
│   └── Project Reports
│
├── Backend
│   ├── Authentication
│   ├── Authorization / RBAC
│   ├── Project Management
│   ├── GitHub Integration
│   ├── Data Ingestion
│   ├── Analytics Engine
│   ├── Risk Engine
│   ├── LangGraph Workflow
│   └── Report Generation
│
├── Database
│   └── MongoDB
│       ├── Users
│       ├── Projects
│       ├── Repositories
│       ├── Contributors
│       ├── Commits
│       ├── Issues
│       ├── Pull Requests
│       ├── Metrics
│       ├── Risk Reports
│       └── AI Reports
│
├── External Services
│   ├── GitHub API
│   └── LLM API
│
└── Development / Collaboration
    ├── GitHub
    ├── GitHub Issues
    ├── GitHub Projects
    ├── Pull Requests
    └── Slack
```


## Flow 
```
                         ┌──────────────┐
                         │   Issue #8   │
                         │   MongoDB    │
                         └──────┬───────┘
                                │
                    ┌───────────┼───────────┐
                    ↓           ↓           ↓
               ┌────────┐ ┌─────────┐ ┌─────────┐
               │  #2    │ │   #7    │ │   #4    │
               │ Auth   │ │ Project │ │ GitHub  │
               └───┬────┘ └────┬────┘ └────┬────┘
                   ↓            ↓            │
               ┌────────┐       │            │
               │  #3    │       │            │
               │  RBAC  │       │            │
               └────┬───┘       │            │
                    └────────────┼────────────┘
                                 ↓
                       ┌─────────────────┐
                       │ GitHub Data     │
                       │ Integration     │
                       └───────┬─────────┘
                               │
                  ┌────────────┴────────────┐
                  ↓                         ↓
             ┌──────────┐             ┌──────────┐
             │   #5     │             │   #6     │
             │ Commits  │             │Contribs  │
             └────┬─────┘             └────┬─────┘
                  │                         │
                  └────────────┬────────────┘
                               ↓
                         ┌───────────┐
                         │  MongoDB  │
                         └─────┬─────┘
                               ↓
                         ┌───────────┐
                         │   #10     │
                         │ Integration│
                         │  Testing  │
                         └───────────┘

#1 Frontend
    │
    ├──→ #2 Authentication
    ├──→ #7 Project API
    └──→ #4 GitHub API

#9 Security/Error Handling
    └──→ applies across the entire flow
```
