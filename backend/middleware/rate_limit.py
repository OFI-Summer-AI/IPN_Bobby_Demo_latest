"""
Bobby — Rate Limiting Middleware
==================================
Basic per-user/per-endpoint rate limiting using an in-memory sliding window.

Phase 1 (demo): in-memory counter — resets on server restart, not shared
                across multiple instances.
Production:     replace with Redis-backed rate limiter.

Limits (configurable):
  - /commands/chat    → 20 requests/min per user
  - /commands/*       → 30 requests/min per user
  - /queries/*        → 60 requests/min per user (cheaper operations)

Decision DEC-XXX: Rate limiting scope — basic per-user/per-endpoint.
Advanced quota management (per department, per licence tier) is out of scope
for Phase 1 (see Assumption 90 in the estimation sheet).
"""
from __future__ import annotations
import time
import collections
from fastapi import Request, HTTPException, status

# In-memory store: {key: deque of timestamps}
_request_log: dict[str, collections.deque] = collections.defaultdict(
    lambda: collections.deque()
)

# Rate limit config: (max_requests, window_seconds)
RATE_LIMITS = {
    "/commands/chat":    (20, 60),   # 20 per min — LLM calls are expensive
    "/commands/":        (30, 60),   # 30 per min for all other commands
    "/queries/":         (60, 60),   # 60 per min — reads are cheap
}


def get_rate_limit_key(request: Request) -> tuple[str, int, int]:
    """
    Returns (key, max_requests, window_seconds) for the current request.
    Key is user_id (from header) + path prefix.
    """
    user_id = request.headers.get("X-User-Id", request.client.host if request.client else "anon")
    path = request.url.path

    for path_prefix, (max_req, window) in RATE_LIMITS.items():
        if path.startswith(path_prefix):
            return f"{user_id}:{path_prefix}", max_req, window

    return f"{user_id}:default", 60, 60


async def rate_limit_middleware(request: Request, call_next):
    """
    FastAPI middleware for sliding window rate limiting.
    Add to app with: app.middleware("http")(rate_limit_middleware)
    """
    key, max_requests, window_seconds = get_rate_limit_key(request)
    now = time.time()
    window_start = now - window_seconds

    log = _request_log[key]

    # Remove timestamps outside the current window
    while log and log[0] < window_start:
        log.popleft()

    if len(log) >= max_requests:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Max {max_requests} requests per {window_seconds}s.",
            headers={"Retry-After": str(window_seconds)},
        )

    log.append(now)
    return await call_next(request)
