# query-mind

**Ask your database questions in plain English. Get SQL, results, charts, and dashboards back in seconds.**

<p align="left">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/TypeScript-5-3178C6?style=for-the-badge&logo=typescript&logoColor=white" alt="TypeScript" />
  <img src="https://img.shields.io/badge/React-19-61DAFB?style=for-the-badge&logo=react&logoColor=black" alt="React" />
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/PostgreSQL-Ready-4169E1?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL" />
  <img src="https://img.shields.io/badge/Supabase-Auth%20%2B%20Data-3FCF8E?style=for-the-badge&logo=supabase&logoColor=white" alt="Supabase" />
</p>

<p align="left">
  <img src="https://img.shields.io/badge/LangGraph-Agent%20Orchestration-1C3C3C?style=for-the-badge&logo=langchain&logoColor=white" alt="LangGraph" />
  <img src="https://img.shields.io/badge/Google%20Gemini-LLM-4285F4?style=for-the-badge&logo=googlegemini&logoColor=white" alt="Gemini" />
  <img src="https://img.shields.io/badge/Celery-Background%20Jobs-37814A?style=for-the-badge&logo=celery&logoColor=white" alt="Celery" />
  <img src="https://img.shields.io/badge/Redis-Broker-DC382D?style=for-the-badge&logo=redis&logoColor=white" alt="Redis" />
  <img src="https://img.shields.io/badge/Vite-Build-646CFF?style=for-the-badge&logo=vite&logoColor=white" alt="Vite" />
  <img src="https://img.shields.io/badge/SQLAlchemy-ORM-D71F00?style=for-the-badge&logo=sqlalchemy&logoColor=white" alt="SQLAlchemy" />
</p>

---

## 🎥 Demo Video

▶️ **[Watch the full product demo](https://youtu.be/X7novGZY15E)** — natural-language questions turning into SQL, live results, auto-selected charts, saved queries, and dashboards.

---

## 💡 What is query-mind?

query-mind is a **full-stack, AI-powered business intelligence platform**. You connect a real database, type a question like *"How many support tickets are there per category, broken down by priority?"*, and a **tool-calling AI agent** explores your schema, writes the SQL, validates it, runs it safely (read-only), and hands back the answer with an explanation, a results table, and an automatically chosen chart.

It is not a thin wrapper around a chat API. Under the hood there is a **LangGraph agent loop** with 12 database tools, budget enforcement, context compaction, error-recovery ladders, and a deterministic fallback pipeline — all built to survive the messy reality of real schemas and imperfect model output.

### The problem it solves

Getting an answer out of a database normally requires you to:

1. Know where the data lives and how tables relate
2. Write correct SQL by hand
3. Verify the query is safe and performant
4. Interpret raw rows into something a human can act on
5. Rebuild the same reports over and over

query-mind collapses all five steps into a single conversation, while keeping everything **auditable** — every agent step (schema search, table inspection, validation, execution) is traceable in the UI via "Show Agent Steps."

---

## 💬 AI Chat — from question to insight

Ask a question, watch the agent reason through your schema, and get back explained SQL plus results.

![Natural language to SQL with explanation and agent steps](demos/chat_1.png)

The agent explains *how* it derived the query — which tables it joined, how it grouped, and why:

![Complex query with HAVING clause and detailed explanation](demos/chatt_3.png)

Results render as a sortable table with execution time, and a chart is auto-selected to fit the data shape:

![Results table with average ratings and review counts](demos/chat_4.png)

Charts are interactive — hover for exact values, switch between Bar, Line, Pie, and Area with one click:

![Grouped bar chart with hover tooltips per ticket category](demos/chat_2.png)

Dual-axis charts are handled automatically when the metrics live on different scales:

![Dual y-axis chart comparing average rating vs review count](demos/chat_5.png)

Multi-grid KPI views break one answer into per-segment mini-dashboards:

![Multi-grid KPI breakdown by department](demos/chat_6.png)

---

## 📊 Dashboards — pin answers, keep them live

Any chat result can be added to a dashboard in one click. Widgets are drag-and-drop, resizable, and each one can switch its own chart type. Dashboards support runtime filters, PNG export, and scheduled refresh.

![Dashboard with line and bar widgets for order analytics](demos/Dashboard_1.png)

![Dashboard with project performance and salary breakdowns](demos/Dashboard_2.png)

---

## 📚 Query Library — save, organize, schedule

Every useful query can be saved into folders, tagged, re-run, and scheduled. The library shows the SQL, run history, and last-run status per query. Scheduled queries execute in the background via Celery workers.

![Query library with folders, saved SQL, and scheduling](demos/Library_1.png)

---

## 🔌 Connections — real databases, safely

Connect PostgreSQL databases (including cloud-hosted, e.g. Supabase poolers) through a guided wizard with SSL and SSH-tunnel support. Each connection gets a live health check, latency telemetry, and a fully mapped schema ledger.

![Connection detail with schema ledger, health, and telemetry](demos/connection_1.png)

![Guided source registration wizard with credentials step](demos/connection_2.png)

---

## ✨ Feature Overview

| Area | What you get |
|------|--------------|
| **AI Agent** | Tool-calling LangGraph agent with 12 tools: schema search, table inspection, relationship discovery, data profiling, row counting, SQL validation, live preview queries, and more |
| **Safety** | Read-only enforcement, write-intent refusal, query timeouts, row-limit wrapping, live-query caps, credential encryption (Fernet) |
| **Resilience** | Call/time budgets with salvage finish, mechanical no-LLM fallback, context compaction for long agent runs, difflib-powered error suggestions, repeat-tool-call detection ladder |
| **Chat UX** | Explanations with every query, expandable agent trace, editable SQL with re-run, pinned results, session history per connection |
| **Visualization** | Auto-selected chart types, dual-axis support, grouped/single/multi-grid modes, interactive tooltips, CSV export |
| **Dashboards** | Drag-and-drop grid, per-widget chart switching, runtime filters, live refresh, PNG export, share links |
| **Library** | Folders, tags, duplicate detection, scheduling (daily/weekly/monthly), run history, public template cloning |
| **Multi-user** | Supabase JWT auth with HTTP-only cookies, per-owner data isolation enforced at the repository layer |
| **Background jobs** | Celery + Redis + Beat for scheduled query runs and dashboard widget refresh, with dispatch locks |

---

## 🏗️ Architecture

```mermaid
flowchart LR
    U[User] --> FE[React 19 + Vite Frontend]
    FE --> API[FastAPI Routes]

    API --> SVC[Service Layer]
    SVC --> AGENT[LangGraph DB Agent]
    SVC --> PIPE[NL-to-SQL Fallback Pipeline]
    SVC --> QE[Query Engine]
    SVC --> REPO[Repositories]
    SVC --> WORKERS[Celery Workers]

    AGENT --> LLM[Gemini / Groq via LangChain]
    PIPE --> LLM
    AGENT --> QE
    QE --> EXTDB[(Connected PostgreSQL DBs)]
    REPO --> SB[(Supabase / App DB)]
    WORKERS --> SVC
```

### How a chat request flows

1. **Deterministic shortcuts first** — schema commands like "show all tables" are answered instantly from the cached catalog, with zero LLM calls. Write-intent messages are refused outright.
2. **Agent loop** — the LangGraph agent iterates `think → call tool → observe`, exploring schema, validating SQL, and profiling data. Budgets cap tool calls and wall-clock time; when exceeded, a salvage finish extracts the best answer so far.
3. **Context compaction** — long tool transcripts are compacted mid-run so the agent keeps its scratchpad without blowing the context window.
4. **Fallback pipeline** — if the agent fails, a simpler schema-prompted generation pipeline takes over, and the failed agent trace is preserved for debugging.
5. **Execution** — SQL runs through the query engine with read-only checks, timeouts, and row limits, then results are persisted to the chat session with full metadata.

### Backend layout

```text
backend/app/
  api/            # FastAPI routes, request/response schemas, auth deps
  core/           # config, secrets, logging, CORS, error handling
  db/             # ORM models, repositories, session management
  services/       # chat, connections, library, dashboards, billing, auth
  agents/         # db_agent (tool-calling loop), nl_to_sql, visualization
  integrations/   # LLM client (Gemini/Groq), Supabase
  query_engine/   # execution, schema inspection, safety wrapping
  workers/        # Celery app, beat scheduler, background jobs
```

---

## 🛠️ Tech Stack

| Layer | Technologies |
|-------|--------------|
| **Frontend** | React 19, TypeScript, Vite, React Router, Zustand, Recharts, react-grid-layout, Lucide |
| **Backend** | Python 3.11, FastAPI, Pydantic v2, Uvicorn |
| **AI / Agents** | LangGraph, LangChain, Google Gemini (primary), Groq (switchable via `LLM_PROVIDER`) |
| **Data & Auth** | Supabase (Postgres + JWT auth), SQLAlchemy, psycopg2 |
| **Query Execution** | SQLAlchemy engines per connection, SSH tunneling, schema introspection |
| **Background Jobs** | Celery, Redis, Celery Beat |
| **Testing** | Pytest — 200+ backend tests covering agent budgets, compaction, tools, safety, repositories, and provider switching |

---

## 🧠 Engineering Highlights

These are the parts I'm most proud of as an engineer:

- **Resilient agent design** — the agent never just "gives up." Budget exhaustion triggers an LLM salvage finish; if *that* fails to produce valid JSON, a mechanical salvage assembles an answer from the trace with zero LLM calls.
- **Context compaction with round-pairing invariants** — tool-call/response pairs are compacted together so the message history stays API-valid while shrinking dramatically.
- **Error recovery ladder** — repeated failing tool calls escalate through warn → skip-with-explanation → force-finish, with difflib-based "did you mean" suggestions on schema errors.
- **Defense in depth for SQL safety** — regex write-detection at the chat boundary, read-only validation in the engine, statement timeouts, and automatic row-limit wrapping.
- **Provider abstraction** — swapping Gemini ↔ Groq is one env var; message-content normalization handles each provider's response shape differences.
- **Owner-scoped repositories** — every query filters by `owner_id` at the data layer, verified by dedicated multi-user isolation tests.

---

## 🚀 Local Setup

### 🐳 Quick start with Docker (recommended)

The whole stack — API, Celery worker, beat scheduler, Redis, and the frontend — runs with one command. You only need Docker installed, plus two free accounts you bring yourself:

- A **Supabase project** (auth + app data) — [supabase.com](https://supabase.com), free tier
- A **Google Gemini API key** (or Groq) — [aistudio.google.com](https://aistudio.google.com), free tier

```bash
git clone https://github.com/danishali778/query-mind.git
cd query-mind

# Fill in your Supabase + LLM keys in both files:
copy backend\.env.example backend\.env      # cp on macOS/Linux
copy frontend\.env.example frontend\.env

docker compose up --build
```

The backend applies database migrations automatically on startup. Open **http://localhost:5173** — the API is at http://localhost:8000.

> Redis URLs are handled for you inside compose; the values in `.env.example` only matter for the manual setup below.

### Manual setup

#### Prerequisites

- Node.js 18+
- Python 3.11+
- A Supabase project
- A Google Gemini API key (or Groq)
- Redis 7+ (optional in dev — rate limiting falls back to in-memory)

### 1. Clone

```bash
git clone https://github.com/danishali778/query-mind.git
cd query-mind
```

### 2. Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
copy .env.example .env       # then fill in your keys
uvicorn app.main:app --reload
```

Optional — background workers for scheduled queries (separate terminals):

```bash
celery -A app.workers.worker:app worker --loglevel=info --queues default,scheduled,templates --pool=solo
celery -A app.workers.beat:app beat --loglevel=info
```

API runs at `http://127.0.0.1:8000`.

### 3. Frontend

```bash
cd frontend
npm install
copy .env.example .env
npm run dev
```

App runs at `http://127.0.0.1:5173`.

### Key environment variables

**`backend/.env`**

```env
# App
APP_ENV=development
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:5174

# LLM provider — gemini or groq
LLM_PROVIDER=gemini
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-2.0-flash
AGENT_MODE=tools

# Supabase (auth + app data)
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
SUPABASE_JWT_SECRET=your-jwt-secret
APP_DATABASE_URL=postgresql+psycopg2://postgres:password@db.your-project-id.supabase.co:5432/postgres

# Connection credential encryption
ENCRYPTION_KEY=your-fernet-key

# Background jobs (optional in dev)
REDIS_URL=redis://127.0.0.1:6379/0
CELERY_BROKER_URL=redis://127.0.0.1:6379/0
```

**`frontend/.env`**

```env
VITE_API_BASE_URL=http://localhost:8000/api
VITE_SUPABASE_URL=your-supabase-project-url
VITE_SUPABASE_ANON_KEY=your-supabase-anon-key
```

---

## 🧪 Testing

```bash
cd backend
python -m pytest
```

The suite covers the agent loop, tool behavior, budget/salvage paths, context compaction, LLM provider switching, SQL safety, schema commands, repositories with multi-user isolation, and API routes.

---

## 🗺️ Roadmap

- **Deeper analytical reasoning** — "Why is revenue dropping?" answered with multi-query investigations and narrative reports
- **Real-time agent progress streaming** to the chat UI (currently a single blocking request)
- **More database engines** — MySQL support is scaffolded; broader engine coverage planned
- **Containerized deployment** — Docker Compose for API + workers + Redis
- **Collaboration** — shared workspaces, dashboard permissions, and audit trails

---

## 📄 Notes

- `backend/app` is the canonical backend package; `backend/main.py` is a thin convenience wrapper.
- All demo media lives in the [`demos/`](demos/) folder.
