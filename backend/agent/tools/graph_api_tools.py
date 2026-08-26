"""
Bobby — Microsoft Graph API Tools (Stub for Demo)
===================================================
LangChain @tool-decorated functions for account management via Graph API.

Phase 1 (demo): All functions return stub responses.
                Graph API credentials not required.
Production:     Requires GRAPH_TENANT_ID, GRAPH_CLIENT_ID, GRAPH_CLIENT_SECRET
                and Microsoft Graph scopes:
                  - User.ReadWrite.All
                  - UserAuthenticationMethod.ReadWrite.All

Decision: Account unlock and password reset require HITL approval BEFORE
          these tools are called. See hitl_node.py and DEC-007.
"""
from __future__ import annotations
from langchain_core.tools import tool
import structlog
from config.settings import settings

logger = structlog.get_logger(__name__)


async def _get_graph_token() -> str:
    """
    Gets an access token for Microsoft Graph via client credentials flow.
    Production only — raises if credentials not configured.
    """
    if not all([settings.graph_tenant_id, settings.graph_client_id, settings.graph_client_secret]):
        raise ValueError(
            "GRAPH_TENANT_ID, GRAPH_CLIENT_ID, and GRAPH_CLIENT_SECRET must be set for Graph API operations"
        )
    import httpx
    token_url = f"https://login.microsoftonline.com/{settings.graph_tenant_id}/oauth2/v2.0/token"
    async with httpx.AsyncClient() as client:
        response = await client.post(token_url, data={
            "grant_type": "client_credentials",
            "client_id": settings.graph_client_id,
            "client_secret": settings.graph_client_secret,
            "scope": "https://graph.microsoft.com/.default",
        })
        response.raise_for_status()
        return response.json()["access_token"]


@tool
async def unlock_account_tool(user_id: str) -> dict:
    """
    Unlocks a locked Azure Active Directory / Entra ID account.
    REQUIRES prior HITL approval. Do not call without user confirmation.

    Args:
        user_id: The user's email or Entra object ID

    Returns:
        Dict with status and user_id
    """
    if settings.is_demo:
        logger.info("graph_tool.unlock_account.stub", user_id=user_id)
        return {
            "status": "stub_success",
            "user_id": user_id,
            "message": "Demo mode: account unlock simulated. No real Graph API call made.",
        }

    # Production implementation
    token = await _get_graph_token()
    import httpx
    async with httpx.AsyncClient() as client:
        response = await client.patch(
            f"https://graph.microsoft.com/v1.0/users/{user_id}",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"accountEnabled": True},
        )
        response.raise_for_status()
    return {"status": "success", "user_id": user_id}


@tool
async def reset_password_tool(user_id: str) -> dict:
    """
    Resets a user's password in Entra ID and forces change on next login.
    REQUIRES prior HITL approval. Do not call without user confirmation.

    Args:
        user_id: The user's email or Entra object ID

    Returns:
        Dict with status and temporary password (masked)
    """
    if settings.is_demo:
        logger.info("graph_tool.reset_password.stub", user_id=user_id)
        return {
            "status": "stub_success",
            "user_id": user_id,
            "message": "Demo mode: password reset simulated. No real Graph API call made.",
        }

    # Production: use /users/{id}/authentication/passwordMethods/{id}/resetPassword
    # TODO: Implement when Graph API credentials are provisioned (see DEC-003)
    raise NotImplementedError("Password reset not yet implemented for production mode")
