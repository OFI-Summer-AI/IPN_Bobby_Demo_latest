from __future__ import annotations
import structlog
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from middleware.auth import DEMO_USERS, create_demo_token

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/auth")


class LoginRequest(BaseModel):
    email: str


@router.post("/login")
async def login(request: LoginRequest):
    """
    Demo login endpoint: maps email to demo role and returns signed JWT token.
    """
    email = request.email.strip().lower()
    
    # Map email to demo users
    if "admin" in email:
        user_key = "admin-001"
    elif "helpdesk" in email:
        user_key = "helpdesk-001"
    else:
        user_key = "employee-001"

    user = DEMO_USERS[user_key]
    # For the walkthrough, override the email with the user's entered email
    user_data = {
        "user_id": email,
        "name": user["name"],
        "role": user["role"]
    }
    
    logger.info("auth.login_success", email=email, role=user["role"])
    
    token = create_demo_token(user_key)
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user_data
    }
