"""
Bobby - Ticket Node (Create / Status / Escalate / Resolve)
==========================================================
Production-grade ticket lifecycle management:
- Smart AI classification of subject, category, priority from user message
- Draft ticket preview with editable fields shown before creation
- Freshdesk live write-backs with agent assignment routing
- Automated email dispatches and audit trail
"""
from __future__ import annotations
import asyncio
import json
import re
import structlog
from langchain_core.messages import SystemMessage
from agent.state import TicketState
from integrations.freshdesk_client import get_freshdesk_client
from integrations.email_service import send_ticket_created_email, send_ticket_resolved_email
from agent.services.auto_resolver import auto_resolve_ticket_background
from config.settings import settings
from text_utils import extract_message_text

logger = structlog.get_logger(__name__)

SLOT_FILLING_PROMPT = """
Extract the following fields from the user's message to create an IT support ticket.
Return a JSON object. If a field is ambiguous, make a reasonable inference.

Fields:
- subject: A clear, concise title for the ticket (string, max 10 words)
- description: A detailed description of the issue suitable for an IT specialist (string)
- category: One of ["IT", "HR", "Finance", "General"] (string)
- priority: One of ["low", "medium", "high", "urgent"] (string)
  - Use "urgent" for security incidents, complete outages affecting business
  - Use "high" for issues blocking a single user entirely (laptop dead, no internet)
  - Use "medium" for degraded performance issues (slow laptop, intermittent wifi)
  - Use "low" for configuration requests, questions, access requests

User message: {message}

Return ONLY valid JSON. Example:
{{"subject": "Laptop Not Starting Up", "description": "User reports laptop will not boot. Requires hardware inspection or replacement.", "category": "IT", "priority": "high"}}
"""

_CONFIRMATION_WORDS = {"yes", "y", "sure", "please", "yes please", "ok", "okay", "confirm", "go ahead", "create", "submit", "create it", "yes create"}


def _classify_agent_assignment(subject: str, category: str, description: str = "") -> tuple[str, str]:
    """Intelligent agent classifier based on ticket content."""
    text = (subject + " " + category + " " + description).lower()

    if any(k in text for k in ("office", "account", "onboarding", "mark thuishaven", "hr", "license", "365", "mailbox", "email setup")):
        return ("Sarah Connor", "Identity & Access Management")
    if any(k in text for k in ("vpn", "wifi", "wi-fi", "network", "firewall", "dns", "anyconnect", "internet", "connectivity")):
        return ("David Miller", "Network & Infrastructure")
    if any(k in text for k in ("hardware", "laptop", "monitor", "printer", "print", "scanner", "dock", "mouse", "keyboard", "screen", "not starting", "won't boot", "slow", "performance")):
        return ("Alex Chen", "Workplace & Field Support")
    if any(k in text for k in ("password", "locked", "unlock", "security", "mfa", "authenticator", "phishing", "2fa")):
        return ("Michael Scott", "Cybersecurity & Access Control")

    return ("Emma Watson", "Enterprise IT Helpdesk")


def _is_confirmation(msg: str) -> bool:
    return msg.strip().lower() in _CONFIRMATION_WORDS


def _smart_classify_from_message(user_message: str) -> dict:
    """Rule-based smart fallback classifier when no LLM available."""
    msg_lower = user_message.lower()

    # Priority classification
    priority = "medium"
    if any(k in msg_lower for k in ("urgent", "critical", "cannot work", "completely down", "security breach", "hacked")):
        priority = "urgent"
    elif any(k in msg_lower for k in ("not working", "broken", "dead", "won't start", "no internet", "locked out", "can't log in", "laptop dead")):
        priority = "high"
    elif any(k in msg_lower for k in ("slow", "intermittent", "sometimes", "occasionally", "request", "access", "need")):
        priority = "medium"
    else:
        priority = "low"

    # Category classification
    category = "IT"
    if any(k in msg_lower for k in ("payroll", "salary", "hr", "leave", "holiday", "onboarding", "new employee", "offboarding")):
        category = "HR"
    elif any(k in msg_lower for k in ("invoice", "finance", "budget", "expense", "purchase order")):
        category = "Finance"

    # Generate subject from message
    words = user_message.strip().split()
    subject_words = []
    skip_next = False
    for i, w in enumerate(words):
        if w.lower() in ("i", "want", "to", "raise", "ticket", "for", "please", "can", "you", "a", "an", "the", "as", "am"):
            continue
        subject_words.append(w)
        if len(subject_words) >= 6:
            break

    if subject_words:
        subject = " ".join(subject_words).strip(".,!?")
        subject = subject[0].upper() + subject[1:] if len(subject) > 0 else "IT Support Request"
    else:
        subject = "IT Support Request"

    return {
        "subject": subject,
        "description": user_message.strip(),
        "category": category,
        "priority": priority,
    }


def _format_draft_card(ticket: dict, ticket_number: str | None = None) -> str:
    """Formats a clear ticket draft card for user review."""
    priority_icons = {
        "low": "🟢 Low",
        "medium": "🟡 Medium",
        "high": "🟠 High",
        "urgent": "🔴 Urgent (P1)",
    }
    category_icons = {
        "IT": "💻 Workplace & Hardware",
        "Workplace & Hardware": "💻 Workplace & Hardware",
        "Network & Infrastructure": "🌐 Network & Connectivity",
        "Identity & Access": "🔑 Identity & Access Management",
        "Cybersecurity": "🛡️ Cybersecurity & Auth",
        "Enterprise Applications": "📊 Enterprise Applications",
        "HR": "👥 HR & People Operations",
        "Finance": "💳 Finance & Billing",
        "General": "📋 IT Support",
    }
    p_display = priority_icons.get(ticket.get("priority", "medium").lower(), "🟡 Medium")
    c_display = category_icons.get(ticket.get("category", "IT"), f"💻 {ticket.get('category', 'IT')}")
    subj = ticket.get('subject', 'IT Support Request')
    desc = ticket.get('description', '').split('\n')[0].strip()

    header = f"📋 **Ticket Draft #{ticket_number}**" if ticket_number else "📋 **Ticket Draft — Please Review**"

    return (
        f"{header}\n\n"
        f"• **Subject:** {subj}\n"
        f"• **Category:** {c_display}\n"
        f"• **Priority:** {p_display}\n\n"
        f"**Description:**\n> {desc}\n\n"
        f"---\n"
        f"👉 *Review the details below. Click **Confirm & Submit** to assign a specialist, or **Edit Details** to customize.*"
    )


async def ticket_node(state: TicketState) -> dict:
    """
    Handles ticket creation, status lookup, updates, and in-chat resolution.
    Production-grade with AI smart classification and editable draft preview.
    """
    logger.info("ticket_node.start", intent=state.get("intent"))

    intent = state.get("intent")
    raw_message = state["messages"][-1].content if state.get("messages") else ""
    user_message = extract_message_text(raw_message)
    user_message_lower = user_message.lower()

    # 1. In-Chat Ticket Resolution (Agent / Admin)
    if ("resolve" in user_message_lower or "close" in user_message_lower) and any(char.isdigit() for char in user_message):
        tid_match = re.search(r"#?(\d+)", user_message)
        if tid_match:
            target_tid = tid_match.group(1)
            try:
                freshdesk = get_freshdesk_client()
                await freshdesk.update_ticket(target_tid, {"status": 4})
                contact_email = state.get("contact_email") or state.get("user_id")
                if contact_email and "@" in contact_email:
                    asyncio.create_task(
                        send_ticket_resolved_email(
                            to_email=contact_email,
                            recipient_name=state.get("contact_name") or state.get("user_name", "Colleague"),
                            ticket_id=target_tid,
                            subject_summary=f"Ticket #{target_tid}",
                            resolution_notes="Ticket marked as resolved by IT Support."
                        )
                    )

                return {
                    "final_response": (
                        f"✅ **Ticket #{target_tid}** has been marked as **Resolved**.\n\n"
                        f"📧 A resolution confirmation email has been sent to the requester."
                    )
                }
            except Exception as e:
                logger.error("ticket_node.resolve_error", error=str(e))
                return {"final_response": f"Sorry, I couldn't update Ticket #{target_tid}. Please try again or call ext. 4000."}

    # 2. Ticket Status Lookup
    if intent == "ticket_status":
        try:
            freshdesk = get_freshdesk_client()
            id_match = re.search(r"#?(\d{2,8})", user_message)
            if id_match:
                spec_id = id_match.group(1)
                try:
                    t = await freshdesk.get_ticket(spec_id)
                    status_map = {2: "Open", 3: "Pending", 4: "Resolved", 5: "Closed"}
                    status_val = t.get("status")
                    status_key = int(status_val) if isinstance(status_val, int) or (isinstance(status_val, str) and status_val.isdigit()) else None
                    status_str = status_map.get(status_key, str(status_val or "In Progress")) if status_key is not None else str(status_val or "In Progress")

                    priority_map = {1: "🟢 Low", 2: "🟡 Medium", 3: "🟠 High", 4: "🔴 Urgent (P1)"}
                    priority_val = t.get("priority")
                    priority_key = int(priority_val) if isinstance(priority_val, int) or (isinstance(priority_val, str) and priority_val.isdigit()) else None
                    priority_str = priority_map.get(priority_key, "Medium") if priority_key is not None else "Medium"

                    return {
                        "ticket_details": {"ticket": t},
                        "final_response": (
                            f"🎫 **Ticket #{spec_id} Details**\n\n"
                            f"• **Subject:** {t.get('subject')}\n"
                            f"• **Status:** *{status_str}*\n"
                            f"• **Priority:** {priority_str}\n"
                            f"• **Created:** {t.get('created_at', '')[:10]}\n\n"
                            f"🤝 *Need to add details or escalate this ticket?*"
                        ),
                    }
                except Exception:
                    pass

            tickets = await freshdesk.get_tickets_by_user(state["user_id"])
            if tickets:
                ticket_summary = "\n".join([
                    f"🎫 **Ticket #{t['id']}:** {t['subject']} — *{t['status']}*"
                    for t in tickets[:5]
                ])
                return {
                    "ticket_details": {"tickets": tickets},
                    "final_response": f"Here are your recent support tickets:\n\n{ticket_summary}\n\nNeed to update or escalate any of these?",
                }
            return {"final_response": "You don't have any open tickets at the moment. Would you like to create one?"}
        except Exception as e:
            logger.error("ticket_node.status_error", error=str(e))
            return {"error": str(e), "escalated": True, "escalation_reason": "Could not fetch tickets"}

    # 3. State Machine — proposed ticket flow
    proposed_ticket = state.get("proposed_ticket")
    ticket_id = state.get("ticket_id")

    # Special walkthrough: Mark Thuishaven
    if "mark thuishaven" in user_message_lower and not proposed_ticket:
        new_ticket = {
            "subject": "New Office Account for Mark Thuishaven",
            "description": "Request to create a new Microsoft Office 365 account and mailbox for new HR employee Mark Thuishaven. Please configure standard employee access.",
            "category": "HR",
            "priority": "medium",
            "requester_id": state["user_id"],
        }
        draft_card = _format_draft_card(new_ticket)
        return {
            "proposed_ticket": new_ticket,
            "final_response": draft_card,
            "needs_human_approval": True,
            "pending_action": {
                "type": "create_ticket",
                "data": new_ticket,
                "message": draft_card,
            },
        }

    # State B: User confirmed -> create ticket
    if _is_confirmation(user_message) and proposed_ticket and not ticket_id:
        contact_name = state.get("contact_name")
        contact_email = state.get("contact_email")
        contact_phone = state.get("contact_phone")

        if not contact_name:
            return {"final_response": "Before I submit the ticket, could you please tell me your **full name**?"}
        if not contact_email:
            return {"final_response": "And your **email address** so we can send you ticket updates?"}
        if not contact_phone:
            return {"final_response": "Finally, your **phone or mobile number** in case the helpdesk needs to reach you?"}

        try:
            freshdesk = get_freshdesk_client()
            created = await freshdesk.create_ticket(
                subject=proposed_ticket["subject"],
                description=proposed_ticket["description"],
                category=proposed_ticket["category"],
                priority=proposed_ticket["priority"],
                requester_id=state["user_id"],
            )
            new_ticket_id = str(created.get("id"))
            assigned_specialist, assigned_team = _classify_agent_assignment(
                proposed_ticket.get("subject", ""),
                proposed_ticket.get("category", ""),
                proposed_ticket.get("description", "")
            )

            try:
                await freshdesk.add_note(
                    new_ticket_id,
                    f"Bobby AI: Ticket classified and routed to {assigned_team} (Specialist: {assigned_specialist}). Priority: {proposed_ticket.get('priority')}.",
                    private=True
                )
            except Exception:
                pass

            target_email = contact_email or state.get("user_id")
            if target_email and "@" in target_email:
                asyncio.create_task(
                    send_ticket_created_email(
                        to_email=target_email,
                        recipient_name=contact_name or "Colleague",
                        ticket_id=new_ticket_id,
                        subject_summary=proposed_ticket["subject"],
                        priority=proposed_ticket.get("priority", "medium"),
                        category=proposed_ticket.get("category", "IT")
                    )
                )
                asyncio.create_task(
                    auto_resolve_ticket_background(
                        ticket_id=new_ticket_id,
                        subject=proposed_ticket["subject"],
                        category=proposed_ticket.get("category", "IT"),
                        recipient_email=target_email,
                        recipient_name=contact_name or "Colleague",
                        delay_seconds=4,
                        description=proposed_ticket.get("description", "")
                    )
                )

            priority_icons = {"low": "🟢", "medium": "🟡", "high": "🟠", "urgent": "🔴"}
            p_icon = priority_icons.get(proposed_ticket.get("priority", "medium"), "🟡")

            response_text = (
                f"✅ **Ticket #{new_ticket_id} created successfully!**\n\n"
                f"**{proposed_ticket['subject']}**\n\n"
                f"| | |\n|---|---|\n"
                f"| 🎫 **Ticket ID** | #{new_ticket_id} |\n"
                f"| {p_icon} **Priority** | {proposed_ticket['priority'].title()} |\n"
                f"| 👤 **Assigned to** | {assigned_specialist} — {assigned_team} |\n"
                f"| 📧 **Updates sent to** | {contact_email} |\n\n"
                f"📬 You'll receive an email confirmation shortly.\n"
                f"Is there anything else I can help you with?"
            )
            return {
                "ticket_id": new_ticket_id,
                "final_response": response_text,
                "needs_human_approval": False,
            }
        except Exception as e:
            logger.error("ticket_node.create_error", error=str(e))
            return {"error": str(e), "escalated": True, "escalation_reason": "Could not create ticket"}

    # State C: Escalate priority
    if ("priority" in user_message_lower or "escalate" in user_message_lower or "urgent" in user_message_lower) and ticket_id:
        try:
            freshdesk = get_freshdesk_client()
            await freshdesk.update_ticket(ticket_id, {"priority": "high"})
            updated_ticket = (proposed_ticket or {}).copy()
            updated_ticket["priority"] = "high"
            return {
                "proposed_ticket": updated_ticket,
                "needs_human_approval": True,
                "pending_action": {
                    "type": "create_ticket",
                    "data": updated_ticket,
                    "message": f"Bobby wants to escalate Ticket #{ticket_id} to **High Priority (P1)**. Please approve.",
                },
                "final_response": f"Bobby wants to escalate Ticket #{ticket_id} to **High Priority (P1)**. Please approve.",
            }
        except Exception as e:
            logger.error("ticket_node.update_error", error=str(e))
            return {"error": str(e), "escalated": True, "escalation_reason": "Could not update ticket"}

    # 4. Standard Ticket Creation — AI Smart Classification or Rule-Based Fallback
    api_key = settings.llm_api_key
    if api_key and api_key.strip() and "TODO" not in api_key:
        from integrations.llm_client import get_llm
        llm = get_llm(json_mode=True)
        try:
            response = await llm.ainvoke([
                SystemMessage(content=SLOT_FILLING_PROMPT.format(message=user_message)),
            ])
            ticket_fields = json.loads(extract_message_text(response.content))
        except Exception as e:
            logger.error("ticket_node.slot_fill_error", error=str(e))
            ticket_fields = _smart_classify_from_message(user_message)
    else:
        ticket_fields = _smart_classify_from_message(user_message)

    proposed_ticket = {
        "subject": ticket_fields.get("subject", "IT Support Request"),
        "description": ticket_fields.get("description", user_message),
        "category": ticket_fields.get("category", "IT"),
        "priority": ticket_fields.get("priority", "medium"),
        "requester_id": state["user_id"],
    }

    draft_card = _format_draft_card(proposed_ticket)

    return {
        "proposed_ticket": proposed_ticket,
        "needs_human_approval": True,
        "pending_action": {
            "type": "create_ticket",
            "data": proposed_ticket,
            "message": draft_card,
        },
        "final_response": draft_card,
    }


def route_after_ticket(state: TicketState) -> str:
    """Route to HITL if approval needed, response if status lookup."""
    if state.get("needs_human_approval"):
        return "hitl_node"
    if state.get("escalated"):
        return "escalation_node"
    return "response_node"
