# Bobby — System Architecture

---

## Overview

Bobby is a single-agent AI system built on LangGraph for IT service management.  
Employees interact via a React chat UI. Bobby classifies intent, retrieves knowledge, manages tickets, and handles account operations — all within a stateful graph that supports human-in-the-loop approval before any write action.

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                        USERS                            │
│  Employee (chat)  │  Helpdesk (dashboard)  │  Admin     │
└───────────────────────────┬─────────────────────────────┘
                            │ HTTPS
┌───────────────────────────▼─────────────────────────────┐
│              FRONTEND (React + TypeScript)               │
│                                                          │
│  ChatPage          DashboardPage       LoginPage         │
│  MessageBubble     TypingIndicator     ActionButtons     │
│  ChatInput         TicketList                            │
│                                                          │
│  State: Zustand (useChatStore)                           │
│  Services: chatService, ticketService (Axios)            │
└───────────────┬───────────────────────────┬─────────────┘
                │ /commands/*               │ /queries/*
                │ (write → LangGraph)       │ (read → direct)
┌───────────────▼───────────────────────────▼─────────────┐
│              BACKEND (FastAPI — Python)                   │
│                                                          │
│  Auth middleware (JWT / Entra ID)                        │
│  Rate limiting middleware                                │
│  CORS middleware                                         │
│                                                          │
│  Commands:  /commands/chat                               │
│             /commands/chat/approve (HITL resume)         │
│             /commands/account/action                     │
│                                                          │
│  Queries:   /queries/tickets                             │
│             /queries/tickets/{id}                        │
│             /queries/knowledge/search                    │
└───────────────┬───────────────────────────┬─────────────┘
                │ ainvoke()                 │ direct call
┌───────────────▼──────────────┐  ┌────────▼─────────────┐
│   LANGGRAPH — Bobby Graph    │  │   Freshdesk REST API  │
│                              │  │   (tickets, search)   │
│  START                       │  └──────────────────────┘
│    ↓                         │
│  triage_node (intent)        │  ┌───────────────────────┐
│    ↓ [conditional]           │  │   Azure AI Search     │
│    ├── knowledge_node (RAG)  │  │   / Supabase pgvector │
│    ├── ticket_node           │  └──────────────────────┘
│    ├── account_node          │
│    └── escalation_node       │  ┌───────────────────────┐
│         ↓                    │  │   Azure OpenAI        │
│  hitl_node (interrupt())     │  │   / OpenAI (demo)     │
│    ↓ [approve/reject]        │  └──────────────────────┘
│    ├── execute_action_node   │
│    └── cancelled_node        │  ┌───────────────────────┐
│         ↓                    │  │   Langfuse            │
│  response_node               │  │   (observability)     │
│    ↓                         │  └──────────────────────┘
│  END                         │
└──────────────────────────────┘
```

---

## CQRS Pattern

Bobby separates reads and writes:

```
Write operation (e.g. create ticket)
  React → POST /commands/chat → LangGraph → HITL → Freshdesk → response

Read operation (e.g. list tickets)
  React → GET /queries/tickets → Freshdesk API directly → response (no LLM)
```

**Why:** Read operations don't need AI reasoning. Bypassing LangGraph saves 2–4 seconds and LLM token costs per query.

---

## LangGraph State Machine

The Bobby graph flows through these nodes:

| Node | Trigger | What it does |
|---|---|---|
| `triage_node` | Every message | LLM classifies intent, sets confidence |
| `knowledge_node` | `it_question` intent | Vector search → LLM synthesis |
| `ticket_node` | `create_ticket` / `ticket_status` | Slot-filling or Freshdesk lookup |
| `account_node` | `account_unlock` / `password_reset` | Prepares HITL action |
| `hitl_node` | Any write action | `interrupt()` — graph pauses for user |
| `execute_action_node` | User approves | Calls Freshdesk / Graph API |
| `cancelled_node` | User rejects | Returns cancellation message |
| `escalation_node` | Low confidence / error | Routes to human agent |
| `response_node` | Always last | Formats final response |

---

## Dual Environment Config

```
APP_ENV=demo          APP_ENV=production
──────────────        ──────────────────
OpenAI direct    →    Azure OpenAI
Supabase pgvec   →    Azure AI Search
Supabase PG      →    Azure PostgreSQL
Mock auth JWT    →    Entra ID MSAL
Graph API stub   →    Real Graph API
MemorySaver      →    PostgresSaver (LangGraph checkpoints)
```

Zero code changes required to switch — only `.env` changes.

---

## Security Model

| Layer | Demo | Production |
|---|---|---|
| Auth | Mock JWT (role selector) | Entra ID OIDC / MSAL |
| Transport | HTTP (localhost) | HTTPS + Azure APIM (optional) |
| Secrets | `.env` file (local) | Azure Key Vault |
| DB | Supabase (shared cloud) | Azure PostgreSQL (private endpoint) |
| LLM | OpenAI public API | Azure OpenAI (in-tenant) |
| Traces | Langfuse cloud | Langfuse self-hosted (in-tenant) |

---

## Phase 1 Demo Scope vs Full Architecture

| Feature | Phase 1 (Demo) | Full Architecture |
|---|---|---|
| Chat UI | ✅ | ✅ |
| Intent classification | ✅ | ✅ |
| Knowledge base RAG | ✅ (in-memory fallback) | ✅ (Azure AI Search) |
| Ticket creation | ✅ (Freshdesk) | ✅ |
| HITL approval | ✅ | ✅ |
| Account unlock / reset | 🔲 Stub | ✅ (Graph API) |
| Teams bot | 🔲 Out of scope | ✅ |
| Langfuse tracing | ✅ | ✅ |
| Multi-tenant | 🔲 | ✅ |
| Azure APIM | 🔲 Optional | ✅ |
