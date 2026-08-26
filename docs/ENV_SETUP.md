# Bobby — Environment Setup Guide

> How to configure `.env` for demo (Supabase + OpenAI) and production (Azure).

---

## Files You Need

| File | Location | Purpose |
|---|---|---|
| `.env` | `bobby/` (root) | Backend credentials — never commit |
| `frontend/.env.local` | `bobby/frontend/` | Frontend env — never commit |

Both files are in `.gitignore`. Only `.env.example` and `frontend/.env.example` are committed.

---

## Step 1 — Copy the examples

```bash
cd bobby
cp .env.example .env
cp frontend/.env.example frontend/.env.local
```

---

## Step 2 — Set APP_ENV

```bash
# For Phase 1 demo (Supabase + OpenAI):
APP_ENV=demo

# For production (Azure services):
APP_ENV=production
```

---

## Step 3 — Fill in credentials

### Demo Mode (`APP_ENV=demo`)

**Required:**
| Variable | Where to get it |
|---|---|
| `OPENAI_API_KEY` | https://platform.openai.com/api-keys |
| `FRESHDESK_API_KEY` | Freshdesk → Profile Settings → API Key |
| `FRESHDESK_DOMAIN` | Your subdomain, e.g. `acme.freshdesk.com` |

**Optional for demo (app works without these):**
| Variable | What it enables |
|---|---|
| `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` | Real vector search (KB search) |
| `LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY` | Observability tracing |

If Supabase vars are not set → app falls back to `InMemorySearchClient` (mock KB articles).  
If Langfuse vars are not set → tracing is silently disabled.

---

### Production Mode (`APP_ENV=production`)

**All demo credentials are replaced by Azure equivalents:**

| Variable | Where to get it |
|---|---|
| `AZURE_OPENAI_API_KEY` | Azure Portal → Azure OpenAI resource → Keys |
| `AZURE_OPENAI_ENDPOINT` | Azure Portal → Azure OpenAI → Overview |
| `AZURE_OPENAI_DEPLOYMENT` | Azure AI Studio → Deployments |
| `AZURE_POSTGRES_HOST` | Azure Portal → PostgreSQL flexible server |
| `AZURE_POSTGRES_USER` | Same |
| `AZURE_POSTGRES_PASSWORD` | Same |
| `AZURE_SEARCH_ENDPOINT` | Azure Portal → AI Search resource |
| `AZURE_SEARCH_API_KEY` | Azure Portal → AI Search → Keys |

---

## Step 4 — Graph API credentials (optional for demo)

Account unlock and password reset are stubbed in demo mode.  
To enable real Graph API calls (for production):

1. Register an app in Azure Portal → App registrations
2. Add API permissions: `User.ReadWrite.All`, `UserAuthenticationMethod.ReadWrite.All`
3. Grant admin consent
4. Create a client secret
5. Fill in:
   ```
   GRAPH_TENANT_ID=your-tenant-id
   GRAPH_CLIENT_ID=your-app-client-id
   GRAPH_CLIENT_SECRET=your-client-secret
   ```

---

## Step 5 — Verify setup

Start the backend and check the health endpoint:

```bash
cd backend
uvicorn main:app --reload
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "ok",
  "env": "demo",
  "freshdesk_configured": true,
  "llm_configured": true
}
```

If `freshdesk_configured: false` → `FRESHDESK_API_KEY` or `FRESHDESK_DOMAIN` is not set.  
If `llm_configured: false` → `OPENAI_API_KEY` (demo) or `AZURE_OPENAI_API_KEY` (prod) is not set.

---

## Supabase Setup (for KB vector search in demo)

If you want real knowledge base search instead of the in-memory fallback:

1. Create a Supabase project at https://supabase.com
2. Run this SQL in Supabase Studio to create the vector search function:

```sql
-- Enable pgvector
create extension if not exists vector;

-- Create documents table
create table documents (
  id bigserial primary key,
  title text,
  content text,
  source text,
  embedding vector(1536)
);

-- Create similarity search RPC function
create or replace function match_documents(
  query_embedding vector(1536),
  match_count int default 5,
  match_threshold float default 0.7
)
returns table (
  id bigint,
  title text,
  content text,
  source text,
  similarity float
)
language sql stable
as $$
  select id, title, content, source,
    1 - (embedding <=> query_embedding) as similarity
  from documents
  where 1 - (embedding <=> query_embedding) > match_threshold
  order by embedding <=> query_embedding
  limit match_count;
$$;
```

3. Add your `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` to `.env`
