"""Bobby — Auth Middleware (mock login for demo)"""
from __future__ import annotations
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from config.settings import settings

security = HTTPBearer(auto_error=False)

ALGORITHM = "HS256"

# ── Demo mock users (replace with Entra ID in production) ─────────────────────
DEMO_USERS = {
    "employee-001": {"user_id": "employee-001@company.com", "name": "Demo Employee", "role": "employee"},
    "helpdesk-001": {"user_id": "helpdesk-001@company.com", "name": "Demo Helpdesk", "role": "helpdesk"},
    "admin-001":    {"user_id": "admin-001@company.com",    "name": "Demo Admin",    "role": "admin"},
}


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict:
    """
    Demo: validates a simple JWT signed with API_SECRET_KEY.
    Production: validates Entra ID JWT (JWKS endpoint).
    """
    if credentials is None:
        # Dev fallback — return default employee user (only in demo mode)
        if settings.is_demo:
            return DEMO_USERS["employee-001"]
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.api_secret_key,
            algorithms=[ALGORITHM],
        )
        user_id = payload.get("sub")
        if user_id not in DEMO_USERS:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        return DEMO_USERS[user_id]
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def create_demo_token(user_id: str) -> str:
    """Utility to generate a demo JWT for testing."""
    return jwt.encode({"sub": user_id}, settings.api_secret_key, algorithm=ALGORITHM)
