# Bobby — AI Service Management Agent

> **Phase 1 Demo** | Python · LangGraph · FastAPI · React · Freshdesk

Bobby is an AI-powered IT service management assistant. Employees interact with Bobby via a chat interface to raise tickets, check status, unlock accounts, and get answers from the knowledge base.

---

## Quick Start

### Prerequisites
- Python 3.10+
- Node 18+
- Freshdesk API key + domain
- OpenAI API key (demo) or Azure OpenAI (production)

### 1. Clone & setup env
```bash
git clone <repo-url>
cd bobby

cp .env.example .env
# Fill in: OPENAI_API_KEY, FRESHDESK_API_KEY, FRESHDESK_DOMAIN
```

### 2. Start backend
```bash
cd backend
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 3. Start frontend
```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` → select a demo role → start chatting with Bobby.

---

## Architecture

```
React UI (localhost:5173)
    │
    ├─ /commands/*  → FastAPI → LangGraph → Freshdesk / Graph API
    └─ /queries/*   → FastAPI → Freshdesk / DB (no LangGraph)

LangGraph Graph (Bobby):
  Triage → Knowledge / Ticket / Account
                    ↓
              HITL interrupt()
                    ↓
             Execute / Cancel
                    ↓
               Response
```

For full architecture details see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## Phase 1 Demo Scope

| Feature | Status |
|---|---|
| Bobby chat UI | ✅ Working |
| Intent classification (triage) | ✅ Working |
| Knowledge base Q&A (RAG) | ✅ Working |
| Create ticket via Freshdesk | ✅ Working |
| Check my tickets | ✅ Working |
| Human-in-the-loop approval | ✅ Working |
| Account unlock / password reset | 🔲 Stub (no Graph API creds) |
| Teams bot | 🔲 Phase 2 |
| Langfuse observability | ✅ Configured |

---

## Key Docs

| Document | Purpose |
|---|---|
| [DECISIONS.md](DECISIONS.md) | All architectural decisions |
| [docs/DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md) | Coding standards & git workflow |
| [docs/ENV_SETUP.md](docs/ENV_SETUP.md) | Environment configuration |
| [docs/API.md](docs/API.md) | API endpoint reference |
| Backend API Docs | `http://localhost:8000/docs` (Swagger) |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18 + TypeScript + Vite |
| State | Zustand |
| Backend | Python 3.10 + FastAPI |
| Agent | LangGraph 0.2+ |
| LLM (demo) | OpenAI GPT-4o |
| LLM (prod) | Azure OpenAI |
| DB (demo) | Supabase PostgreSQL |
| DB (prod) | Azure PostgreSQL |
| Knowledge Search (demo) | Supabase pgvector with ranked lexical fallback |
| Vector Search (prod) | Azure AI Search |
| ITSM | Freshdesk API v2 |
| Observability | Langfuse |

---

## Project Structure

```
bobby/
├── frontend/     React chatbot UI
├── backend/      FastAPI + LangGraph
│   ├── agent/    Bobby graph + nodes
│   ├── api/      CQRS commands + queries
│   ├── integrations/  Freshdesk, LLM, Search clients
│   └── config/   Dual-config settings
├── docs/         Developer documentation
├── DECISIONS.md  Architectural decision log
└── docker-compose.yml
```
