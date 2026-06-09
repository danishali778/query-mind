# QueryMind

QueryMind is an AI-powered business intelligence application built primarily around a Python backend and a React frontend. It lets a user connect a database, ask questions in plain English, generate SQL, inspect results, save useful queries, and build interactive dashboards from those results.

## What problem it solves

Teams usually have business questions long before they have clean answers.

In a typical workflow, a user has to:
- know where the relevant data lives
- understand the schema and table relationships
- write the SQL by hand
- validate whether the query is safe and correct
- interpret the result
- decide which chart, summary, or follow-up question matters next

That creates a gap between business users and the underlying data. Even technical users lose time switching between schema exploration, SQL writing, debugging, chart selection, and report preparation.

QueryMind reduces that gap by turning a plain-language question into an end-to-end analytics workflow:
- it inspects schema context
- generates SQL
- executes it safely
- returns rows and visual recommendations
- preserves useful outputs in a query library or dashboard

The long-term goal is not only to answer questions like `what happened?`, but also to support questions like `why is revenue dropping?` by combining query generation, result analysis, follow-up reasoning, and structured report generation.

## Key features

- Natural-language to SQL workflow with schema-aware prompting
- Read-only SQL validation and execution safeguards
- Chat-based analytics sessions with result history
- Query library for saving, tagging, scheduling, and re-running queries
- Dashboard widgets built from saved or ad hoc query results
- Supabase-backed auth, persistence, and application data
- SSH-capable database connection flow in the frontend
- Worker-based scheduling for saved queries and dashboard refresh jobs

## Tech stack

| Layer | Technologies |
| --- | --- |
| Frontend | React 19, Vite, TypeScript, React Router, Zustand, Recharts, Framer Motion, Lucide |
| Backend API | Python, FastAPI, Pydantic v2, Uvicorn |
| AI / Orchestration | LangGraph, LangChain, Groq |
| Data / Auth | Supabase, PostgreSQL |
| Query Execution | SQLAlchemy, psycopg2, PyMySQL, SSH tunneling |
| Scheduling | APScheduler |

## Architecture

The backend has been refactored so `backend/app` is the canonical runtime package.

### Architecture overview

```mermaid
flowchart LR
    U[User] --> FE[React Frontend]
    FE --> API[FastAPI API Routes]

    API --> SVC[Service Layer]
    SVC --> AGENTS[Agents]
    SVC --> QE[Query Engine]
    SVC --> DB[DB / Repositories]
    SVC --> WORKERS[Workers]
    SVC --> INT[Integrations]

    AGENTS --> INT
    QE --> DB
    DB --> SB[(Supabase)]
    INT --> SB
    QE --> EXTDB[(Connected Databases)]
    WORKERS --> SVC
```

### Backend package layout

```text
backend/
  app/
    api/            # FastAPI routes, DTO schemas, dependencies
    core/           # config, secrets, security, middleware, errors
    db/             # domain models, repositories, migrations, connection manager
    services/       # application workflows
    agents/         # NL-to-SQL, visualization, insight generation
    integrations/   # Supabase, Groq, Lemon Squeezy, provider clients
    query_engine/   # query execution, schema inspection, safety
    workers/        # schedulers and background jobs
    main.py         # canonical backend app entrypoint
```

### Runtime flow

1. The frontend sends a request to the API.
2. The API layer validates request DTOs and forwards them to services.
3. Services orchestrate repositories, agents, query execution, integrations, and workers.
4. Query execution is handled in `app/query_engine` with safety checks and schema inspection.
5. Persistent application data is stored in Supabase.
6. Connected analytics databases are queried through the query engine and connection manager.

## Screenshots

### Landing and product views

![Landing page](assets/01-landing-page.png)

### Dashboards

| Dashboard 1 | Dashboard 2 |
| --- | --- |
| ![Dashboard 1](assets/dashboard-1.png) | ![Dashboard 2](assets/dashboard-2.png) |

| Dashboard 3 | Dashboard 4 |
| --- | --- |
| ![Dashboard 3](assets/dashboard-3.png) | ![Dashboard 4](assets/dashboard-4.png) |

### Chat, analytics, and data management

| AI Chat | Analytics |
| --- | --- |
| ![Chat](assets/chat-detailed.png) | ![Analytics](assets/analytics-top.png) |

| Query Library | Connections |
| --- | --- |
| ![Query Library](assets/04-query-library.png) | ![Connections](assets/05-connections-page.png) |

## Local setup

### Prerequisites

- Node.js 18+
- Python 3.11+
- a Supabase project
- a Groq API key

### 1. Clone the repository

```bash
git clone https://github.com/danishali778/query-mind.git
cd InsightAI
```

### 2. Backend setup

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

Backend runs at:

```text
http://127.0.0.1:8000
```

### 3. Frontend setup

Open a second terminal:

```bash
cd frontend
npm install
copy .env.example .env
npm run dev
```

Frontend runs at:

```text
http://127.0.0.1:5173
```

## Environment variables

### Backend: `backend/.env`

The backend loads its environment from `backend/.env`.

Required or commonly used variables:

```env
APP_ENV=development
APP_HOST=0.0.0.0
APP_PORT=8000
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000

DATABASE_URL=postgresql://user:password@localhost:5432/querymind_demo
ENCRYPTION_KEY=your_fernet_key

SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
SUPABASE_JWT_SECRET=your-jwt-secret

GROQ_API_KEY=your-groq-api-key
GROQ_MODEL=llama-3.3-70b-versatile

LEMON_SQUEEZY_WEBHOOK_SECRET=your-webhook-secret
LEMON_SQUEEZY_API_KEY=your-api-key

BACKEND_DEV_MODE=false
DEV_USER_ID=00000000-0000-0000-0000-000000000000
```

### Frontend: `frontend/.env`

```env
VITE_API_BASE_URL=http://localhost:8000/api
VITE_SUPABASE_URL=your_supabase_project_url
VITE_SUPABASE_ANON_KEY=your_supabase_anon_key
VITE_LEMON_SQUEEZY_CHECKOUT_URL=https://your-store.lemonsqueezy.com/checkout/buy/...
VITE_DEV_MODE=false
```

## Future improvements

- Replace in-process scheduling with Redis + Celery based workers
- Expand test coverage into full route and end-to-end integration suites
- Improve query-engine chunking and frontend bundle splitting
- Add richer observability around agent retries, SQL correction loops, and worker runs
- Broaden database support and connection diagnostics
- Strengthen billing and plan enforcement beyond the current integration boundary
- Add stronger collaboration, sharing controls, and audit features
- Generate richer business reports from query results, not just raw answers and charts
- Support deeper analytical reasoning over result sets, such as:
  - `Why is revenue dropping?`
  - `Which segments are contributing most to the decline?`
  - `What changed compared to the previous period?`
- Introduce agent-driven summaries that fetch supporting data, explain findings, and assemble a structured narrative report with trends, anomalies, and recommended follow-up questions

## Notes

- The merged backend architecture now lives under `backend/app`.
- The top-level `backend/main.py` remains as a convenience wrapper, while `backend/app/main.py` is the canonical backend entrypoint.
