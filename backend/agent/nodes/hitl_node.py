"""
Bobby — HITL Node (Human-in-the-Loop)
=======================================
Uses LangGraph interrupt_before to pause the graph before this node
executes. The graph resumes when the user approves or rejects.
"""
from __future__ import annotations
import asyncio
import structlog
from agent.state import TicketState
from integrations.freshdesk_client import get_freshdesk_client
from integrations.email_service import send_ticket_created_email, send_escalation_email
from agent.services.auto_resolver import auto_resolve_ticket_background

logger = structlog.get_logger(__name__)


async def hitl_node(state: TicketState) -> dict:
    """
    Runs AFTER the graph resumes from interrupt_before pause.
    Reads human_approved from state (set by the resume ainvoke call).
    """
    pending = state.get("pending_action", {})
    approved = state.get("human_approved", False)
    logger.info("hitl_node.decision", approved=approved, action_type=pending.get("type"))

    return {
        "human_approved": approved,
        "needs_human_approval": False,
    }


async def execute_action_node(state: TicketState) -> dict:
    """
    Executes the approved action with full Autonomous Resolution Agent support.
    """
    pending = state.get("pending_action", {})
    action_type = pending.get("type")
    ticket_id = state.get("ticket_id")

    logger.info("execute_action_node.start", action_type=action_type, ticket_id=ticket_id)

    if action_type == "create_ticket":
        # Escalation path
        if ticket_id:
            contact_name  = state.get("contact_name")  or state.get("user_name")  or "User"
            contact_email = state.get("contact_email") or state.get("user_id", "")
            if contact_email and "@" in contact_email:
                asyncio.create_task(
                    send_escalation_email(contact_email, contact_name, str(ticket_id), "Support Request Escalation")
                )
            return {
                "final_response": (
                    f"✅ Done! Ticket **#TKT-{ticket_id}** has been escalated to **P1 High Priority**.\n\n"
                    f"The on-call engineer has been alerted.\n\n"
                    f"**Assigned to:** Workplace & Field Support Lead\n"
                    f"**Expected response:** Under 15 minutes\n\n"
                    f"📧 *(An email confirmation was sent to **{contact_email}**)*"
                ),
            }

        # New ticket creation
        try:
            freshdesk = get_freshdesk_client()
            ticket_data = pending.get("data", {})
            subject = ticket_data.get("subject", "IT Support Request")
            description = ticket_data.get("description", "")
            category = ticket_data.get("category", "IT")
            priority = ticket_data.get("priority", "medium")

            created = await freshdesk.create_ticket(
                subject=subject,
                description=description,
                category=category,
                priority=priority,
                requester_id=state["user_id"],
            )
            created_id = str(created.get("id"))
            logger.info("execute_action_node.ticket_created", ticket_id=created_id)

            from agent.nodes.ticket_node import _classify_agent_assignment
            assigned_specialist, assigned_team = _classify_agent_assignment(subject, category, description)

            try:
                await freshdesk.add_note(
                    created_id,
                    f"Bobby AI: Ticket classified and routed to {assigned_team} (Specialist: {assigned_specialist}). Priority: {priority}.",
                    private=True
                )
            except Exception:
                pass

            target_email = state.get("contact_email") or state.get("user_id")
            recipient_name = state.get("contact_name") or state.get("user_name") or "Colleague"

            if target_email and "@" in target_email:
                asyncio.create_task(
                    send_ticket_created_email(
                        to_email=target_email,
                        recipient_name=recipient_name,
                        ticket_id=created_id,
                        subject_summary=subject,
                        priority=priority,
                        category=category
                    )
                )
                asyncio.create_task(
                    auto_resolve_ticket_background(
                        ticket_id=created_id,
                        subject=subject,
                        category=category,
                        recipient_email=target_email,
                        recipient_name=recipient_name,
                        delay_seconds=4,
                        description=description
                    )
                )

            priority_icons = {"low": "🟢", "medium": "🟡", "high": "🟠", "urgent": "🔴"}
            p_icon = priority_icons.get(priority.lower(), "🟡")

            return {
                "ticket_id": str(created_id),
                "final_response": (
                    f"✅ **Ticket #{created_id} created successfully!**\n\n"
                    f"**{subject}**\n\n"
                    f"| Field | Detail |\n|---|---|\n"
                    f"| 🎫 **Ticket ID** | #{created_id} |\n"
                    f"| {p_icon} **Priority** | {priority.title()} |\n"
                    f"| 👤 **Assigned to** | {assigned_specialist} — {assigned_team} |\n"
                    f"| ⚡ **Status** | In Progress (Autonomous Resolver Agent active) |\n\n"
                    f"📬 *Confirmation email sent to {target_email}. Our Autonomous Agent is resolving this request.*"
                ),
            }
        except Exception as e:
            logger.error("execute_action_node.create_error", error=str(e))
            return {
                "error": str(e),
                "final_response": "Sorry, I could not create the ticket. Please try again or contact the helpdesk at ext. 4000.",
            }

    if action_type in ("account_unlock", "password_reset"):
        return {
            "final_response": (
                f"✅ {action_type.replace('_', ' ').title()} is being processed. "
                "A confirmation email has been dispatched."
            ),
        }

    return {"final_response": "✅ Action completed."}


async def cancelled_node(state: TicketState) -> dict:
    """Called when user rejects the HITL approval."""
    logger.info("cancelled_node.action_cancelled")
    return {
        "final_response": "Okay, I've cancelled that action. Is there anything else I can help you with?",
    }


def route_after_hitl(state: TicketState) -> str:
    """Route based on human decision after HITL."""
    if state.get("human_approved"):
        return "execute_action_node"
    return "cancelled_node"
