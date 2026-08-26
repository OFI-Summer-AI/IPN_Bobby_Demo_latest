"""
Bobby — Account Node (stub for demo)
======================================
Handles: account_unlock, password_reset intents.
In demo mode: returns a confirmation stub (no real Graph API calls).
In production: calls Microsoft Graph API via graph_api_tools.
"""
from __future__ import annotations
import structlog
from agent.state import TicketState
from config.settings import settings

logger = structlog.get_logger(__name__)


async def account_node(state: TicketState) -> dict:
    """
    Handles account management requests.
    Demo: returns stub confirmation with HITL.
    Production: triggers Graph API after HITL approval.
    """
    intent = state.get("intent")
    user_id = state.get("user_id")

    logger.info("account_node.start", intent=intent, user_id=user_id)

    if intent == "account_unlock":
        action_message = (
            f"Bobby wants to **unlock your account**.\n\n"
            f"This will re-enable your login access.\n"
            f"User: {user_id}"
        )
        action_type = "account_unlock"
    elif intent == "password_reset":
        action_message = (
            f"Bobby wants to **reset your password**.\n\n"
            f"A temporary password will be sent to your registered email.\n"
            f"User: {user_id}"
        )
        action_type = "password_reset"
    else:
        return {
            "escalated": True,
            "escalation_reason": "Unknown account action",
        }

    return {
        "needs_human_approval": True,
        "pending_action": {
            "type": action_type,
            "data": {"user_id": user_id},
            "message": action_message,
        },
    }
