# Bobby — Developer Guide
> **Version:** 1.0 | **Last updated:** August 2026  
> This document defines the standards every developer must follow throughout the project.

---

## 1. Project Structure

```
bobby/
├── frontend/        React + TypeScript + Vite
├── backend/         Python FastAPI + LangGraph
├── docs/            All documentation
├── DECISIONS.md     Architectural Decision Log ← read before making decisions
├── README.md        Quickstart
└── docker-compose.yml
```

---

## 2. Setup

### Prerequisites
- Python 3.10+
- Node 18+
- Git 2.40+

### Backend Setup
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # Mac/Linux

pip install -r requirements.txt

cp ../.env.example .env
# Fill in OPENAI_API_KEY and FRESHDESK credentials in .env

uvicorn main:app --reload --port 8000
```

### Frontend Setup
```bash
cd frontend
npm install

cp .env.example .env.local
# VITE_API_BASE_URL=http://localhost:8000

npm run dev
```

Visit `http://localhost:5173` — select a demo role and start chatting.

---

## 3. Environment Configuration

Bobby uses a **dual-config system**:

| `APP_ENV` | LLM | Database | Vector Store |
|---|---|---|---|
| `demo` | OpenAI direct | Supabase / local PG | Supabase pgvector |
| `production` | Azure OpenAI | Azure PostgreSQL | Azure AI Search |

**Never hard-code credentials.** All config goes through `backend/config/settings.py`.

If you add a new environment variable:
1. Add it to `.env.example` with a comment
2. Add it to `Settings` in `settings.py`
3. Document it in `docs/ENV_SETUP.md`

---

## 4. Git Workflow

### Branch naming
```
feature/<short-description>     # e.g. feature/ticket-status-query
fix/<issue-or-short-desc>       # e.g. fix/triage-json-parse-error
chore/<what>                    # e.g. chore/update-requirements
docs/<what>                     # e.g. docs/update-api-reference
```

### Workflow
```bash
# Always branch from develop
git checkout develop
git pull origin develop
git checkout -b feature/your-feature

# Work, commit often
git add .
git commit -m "feat(agent): add account unlock node"

# Push and open PR into develop
git push origin feature/your-feature
# → Open PR → assign reviewer → merge after approval
```

### Commit message format
Use [Conventional Commits](https://www.conventionalcommits.org/):
```
feat(scope): short description
fix(scope): short description
docs(scope): short description
chore(scope): short description
refactor(scope): short description
test(scope): short description
```

Examples:
```
feat(agent): add knowledge retrieval node with Supabase pgvector
fix(freshdesk): handle 429 rate limit with exponential backoff
docs(api): update /commands/chat endpoint documentation
```

### PR checklist (reviewer must verify)
- [ ] All new env vars documented in `.env.example` and `settings.py`
- [ ] New agent nodes have docstrings explaining purpose and routing
- [ ] New API endpoints documented in `docs/API.md`
- [ ] Significant decisions recorded in `DECISIONS.md`
- [ ] No hardcoded credentials or API keys
- [ ] Async used for all I/O operations (HTTP, DB, LLM)

---

## 5. Backend Coding Standards

### Async Rule
```python
# ✅ Correct — use async for ALL I/O (LLM, HTTP, DB)
async def my_node(state: TicketState) -> dict:
    result = await llm.ainvoke([...])
    return {"field": result}

# ❌ Wrong — sync I/O blocks the event loop
def my_node(state: TicketState) -> dict:
    result = llm.invoke([...])  # blocks FastAPI worker
    return {"field": result}
```

### Node return rule
```python
# ✅ Correct — return only the fields you changed
async def my_node(state: TicketState) -> dict:
    return {"intent": "it_question", "confidence": 0.9}

# ❌ Wrong — don't return the full state
async def my_node(state: TicketState) -> dict:
    state["intent"] = "it_question"
    return state  # mutating state directly is wrong
```

### CQRS rule
```python
# ✅ Commands (write) — go through LangGraph
@router.post("/commands/create-ticket")
async def create_ticket(cmd, user=Depends(get_current_user)):
    result = await bobby_graph.ainvoke(...)

# ✅ Queries (read) — bypass LangGraph, direct API call
@router.get("/queries/my-tickets")
async def get_tickets(user=Depends(get_current_user)):
    return await freshdesk_client.get_tickets_by_user(...)

# ❌ Never put a read operation through LangGraph
@router.get("/queries/my-tickets")
async def get_tickets():
    result = await bobby_graph.ainvoke({"intent": "ticket_status"})  # WRONG
```

### Error handling
```python
# ✅ Log the error, return safe state update
try:
    result = await external_api.call()
except Exception as e:
    logger.error("node_name.action", error=str(e))
    return {"error": str(e), "escalated": True, "escalation_reason": "..."}

# ❌ Don't let exceptions propagate silently from nodes
```

### Logging
Use structlog — always log with key-value pairs:
```python
import structlog
logger = structlog.get_logger(__name__)

logger.info("node_name.event", user_id=user_id, intent=intent)
logger.error("node_name.error", error=str(e), context={"key": "value"})
```

---

## 6. Frontend Coding Standards

### Component structure
```
MyComponent/
├── MyComponent.tsx          # Logic
├── MyComponent.module.css   # Styles
└── index.ts                 # Re-export (optional)
```

### CSS rule
- Use CSS Modules only — no inline styles, no global class names
- Use design tokens from `index.css` via `var(--token-name)`
- Never use magic numbers — use spacing tokens

```css
/* ✅ Correct */
padding: var(--space-4);
color: var(--color-text-primary);
border-radius: var(--radius-md);

/* ❌ Wrong */
padding: 16px;
color: #f0f2ff;
border-radius: 10px;
```

### State rule
- **Chat state** → Zustand (`useChatStore`)
- **Local UI state** → `useState`
- **Server data** → direct service calls (no Redux, no React Query for MVP)

### Type rule
All types live in `src/types/`. Import from there — never inline type definitions in components.

```typescript
// ✅
import type { Message, Ticket } from '@/types/chat.types';

// ❌
interface Message { ... }  // don't define in component file
```

---

## 7. Adding a New Use Case Workflow

To add a new use case (e.g., "order laptop"):

1. **Add intent to triage** — add the intent to `VALID_INTENTS` and the deterministic precedence rules in `triage.py`; intent classification must not call an LLM
2. **Add node** — create `backend/agent/nodes/laptop_order_node.py`
3. **Add edge** — wire the node into `graph.py` with `add_node()` and `add_conditional_edges()`
4. **Add tools** — if it needs a new API, add to `agent/tools/`
5. **Add integration** — if it needs a new API client, add to `integrations/`
6. **Record decision** — if it's a significant design choice, add to `DECISIONS.md`
7. **Update docs** — add to `docs/API.md`

---

## 8. Testing

### Backend unit tests
```bash
cd backend
pytest tests/ -v
```

### Frontend type check
```bash
cd frontend
npm run typecheck
```

### Manual API testing
FastAPI auto-generates Swagger docs at `http://localhost:8000/docs`.

---

## 9. Observability

Langfuse tracing is configured in `backend/config/settings.py`. When `LANGFUSE_PUBLIC_KEY` is set, all LangGraph invocations are automatically traced.

Access Langfuse dashboard at `https://cloud.langfuse.com` (or your self-hosted URL).

What is traced per invocation:
- Full message history
- Each node's input/output
- LLM call latency and token usage when an LLM is used for grounded answer synthesis or ticket field extraction
- Deterministic intent and scope classification result
- HITL decisions

---

## 10. Before Every Deployment

- [ ] Run `npm run typecheck` in frontend
- [ ] Check no `.env` files are being committed (`git status`)
- [ ] Verify `API_SECRET_KEY` is not the default value
- [ ] Confirm `APP_ENV` is set correctly (`demo` vs `production`)
- [ ] Check Langfuse is receiving traces
