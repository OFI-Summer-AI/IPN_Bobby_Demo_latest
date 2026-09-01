# Bobby — API Reference

> All endpoints are served from `http://localhost:8000` in development.  
> Interactive docs: `http://localhost:8000/docs` (Swagger UI)

---

## Authentication

**Demo mode:** All endpoints work without a token (default employee role is used).  
To test with a specific role, include a JWT in the `Authorization` header:

```
Authorization: Bearer <token>
```

Generate a demo token:
```python
from middleware.auth import create_demo_token
token = create_demo_token("helpdesk-001")
```

### `POST /auth/login`
Maps an email address to a demo role and returns a signed bearer token. This endpoint is for the
demo login flow; production authentication uses the configured identity provider.

```json
{
  "email": "employee@example.com"
}
```

---

## CQRS Pattern

| Route prefix | Goes through LangGraph | Has HITL | Cost |
|---|---|---|---|
| `/commands/*` | ✅ Yes | May pause for approval | LLM tokens |
| `/queries/*` | ❌ No | Never | Zero |

---

## Commands (Write — through LangGraph)

### `POST /commands/chat`
Main chat endpoint. Routes user message through Bobby graph.

**Request body:**
```json
{
  "message": "I can't log in to my account",
  "session_id": "session-1234"
}
```

**Response (normal):**
```json
{
  "session_id": "session-1234",
  "message": "I understand your account is locked. Let me help you unlock it.",
  "intent": "account_unlock",
  "escalated": false
}
```

**Response (when HITL fires — graph is paused):**
```json
{
  "session_id": "session-1234",
  "message": "Bobby wants to **unlock your account**...",
  "requires_approval": true,
  "pending_action": {
    "type": "account_unlock",
    "data": { "user_id": "alice@company.com" },
    "message": "Bobby wants to unlock your account. Do you approve?"
  }
}
```

When `requires_approval: true` — the graph is paused. Call `/commands/chat/approve` to resume.

---

### `POST /commands/chat/approve`
Resumes a paused Bobby graph after HITL approval or rejection.

**Request body:**
```json
{
  "session_id": "session-1234",
  "approved": true
}
```

**Response:**
```json
{
  "session_id": "session-1234",
  "message": "✅ Your account has been unlocked! You can now log in.",
  "approved": true,
  "ticket_id": "12345"
}
```

---

### `POST /commands/account/action`
Triggers an account action (unlock or password reset) through Bobby graph.

**Request body:**
```json
{
  "session_id": "session-1234",
  "action": "unlock"
}
```

Valid `action` values: `"unlock"` | `"password_reset"`

---

### `POST /commands/tickets/resolve`
Marks a Freshdesk ticket as resolved, adds a private resolution note, and dispatches the configured
resolution email.

```json
{
  "ticket_id": "12345",
  "resolution_notes": "VPN access restored after profile reset.",
  "resolved_by": "IT Helpdesk Specialist",
  "recipient_email": "employee@example.com",
  "recipient_name": "Employee"
}
```

---

## Queries (Read — bypass LangGraph)

### `GET /queries/tickets`
Get current user's tickets from Freshdesk.

**Query params:**
- `status` (optional): `open` | `resolved` | `closed`

**Response:**
```json
{
  "tickets": [
    {
      "id": "123",
      "subject": "VPN not connecting",
      "status": "Open",
      "priority": 2,
      "created_at": "2026-08-12T10:00:00Z"
    }
  ],
  "count": 1
}
```

---

### `GET /queries/tickets/{ticket_id}`
Get a single ticket by ID.

---

### `GET /queries/tickets/search?q=<query>`
Search tickets by keyword.

---

### `GET /queries/knowledge/search?q=<query>&top_k=5`
Search the knowledge base.

**Response:**
```json
{
  "results": [
    {
      "title": "How to connect to VPN",
      "content": "...",
      "source": "IT Knowledge Base"
    }
  ],
  "query": "vpn",
  "count": 1
}
```

---

## Health

### `GET /health`
Returns service status and config state.

```json
{
  "status": "ok",
  "service": "bobby-api",
  "env": "demo",
  "freshdesk_configured": true,
  "llm_configured": true
}
```

---

## Error Responses

| Status | Meaning |
|---|---|
| `400` | Bad request — invalid body |
| `401` | Unauthorized — missing/invalid token |
| `422` | Validation error — check request body |
| `429` | Rate limit exceeded |
| `500` | Internal server error — check logs |
