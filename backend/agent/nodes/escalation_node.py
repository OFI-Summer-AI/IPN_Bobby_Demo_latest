"""
Bobby — Escalation & Response Nodes
=====================================
escalation_node : Routes to human helpdesk agent
response_node   : Final node — formats and returns Bobby's answer
"""
from __future__ import annotations
import structlog
from agent.state import TicketState

logger = structlog.get_logger(__name__)


async def escalation_node(state: TicketState) -> dict:
    """
    Escalates to a human helpdesk agent.
    Creates a Freshdesk ticket flagged for human attention.
    """
    reason = state.get("escalation_reason", "Unable to resolve automatically")
    logger.info("escalation_node.escalating", reason=reason)

    escalation_message = (
        "I'm not able to fully resolve this for you right now. "
        f"I've escalated your request to our helpdesk team — "
        "they will get back to you shortly.\n\n"
        f"**Reason:** {reason}"
    )

    return {
        "escalated": True,
        "final_response": escalation_message,
    }


async def response_node(state: TicketState) -> dict:
    """
    Final node — ensures final_response is set and clean.
    This is always the last node before END.
    """
    logger.info("response_node.complete", user_id=state.get("user_id"))

    final_response = state.get("final_response", "")

    if not final_response:
        # Fallback if something went wrong upstream
        final_response = (
            "I'm sorry, I wasn't able to process your request. "
            "Please try rephrasing or contact the helpdesk directly."
        )

    return {"final_response": final_response}
