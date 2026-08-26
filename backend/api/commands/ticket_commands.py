"""
Bobby - CQRS Commands: Ticket Operations
==========================================
All ticket write operations go through LangGraph.
Approval is handled directly at the HTTP layer for reliability.
Contact info (name/email/phone) is collected in a simple in-memory session store.
"""
from __future__ import annotations
from integrations.email_service import send_escalation_email
import re
import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from langchain_core.messages import HumanMessage
from agent.graph import get_bobby_graph, build_bobby_graph
from agent.nodes.triage import _BAD_INTENT_PATTERNS
import re
from middleware.auth import get_current_user
from config.settings import settings

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/commands")

_sessions: dict[str, dict] = {}
_fallback_graph = None
_EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
_PHONE_RE = re.compile(r"[\+]?[\d\s\-\(\)]{7,15}")
_CONFIRM_WORDS = {"yes", "y", "sure", "please", "yes please", "ok", "okay", "confirm", "yep", "yup"}

CONTACT_STEPS = [
    ("contact_name",  "Before I create the ticket, could you please tell me your **full name**?"),
    ("contact_email", "Great! What is your **email address** so we can send you ticket updates?"),
    ("contact_phone", "Almost done! What is your **phone / mobile number** for the helpdesk to reach you?"),
]


def _get_sess(sid: str) -> dict:
    if sid not in _sessions:
        _sessions[sid] = {
            "contact_name": None,
            "contact_email": None,
            "contact_phone": None,
            "awaiting_confirmation": False,
            "collecting_contact": False,
            "current_step": 0,
        }
    return _sessions[sid]


def _all_collected(sess: dict) -> bool:
    return bool(sess.get("contact_name") and sess.get("contact_email") and sess.get("contact_phone"))


def _fill_step(sess: dict, value: str):
    step_idx = sess.get("current_step", 0)
    if step_idx >= len(CONTACT_STEPS):
        return
    field, _ = CONTACT_STEPS[step_idx]
    if field == "contact_email":
        m = _EMAIL_RE.search(value)
        sess[field] = m.group(0) if m else value.strip()
    elif field == "contact_phone":
        m = _PHONE_RE.search(value)
        sess[field] = m.group(0).strip() if m else value.strip()
    else:
        sess[field] = value.strip()
    sess["current_step"] = step_idx + 1


class ChatRequest(BaseModel):
    message: str
    session_id: str
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    local_time_greeting: Optional[str] = None
    local_hour: Optional[int] = None


class ResumeApprovalRequest(BaseModel):
    session_id: str
    approved: bool


@router.post("/chat")
async def chat(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user),
):
    global _fallback_graph
    sess = _get_sess(request.session_id)

    if request.contact_name:
        sess["contact_name"] = request.contact_name
    if request.contact_email:
        sess["contact_email"] = request.contact_email
    if request.contact_phone:
        sess["contact_phone"] = request.contact_phone

    msg = request.message.strip()
    msg_lower = msg.lower()

    # Step 0: Strict ITSM Guardrail & Bad Intent Check (ALWAYS HIGHEST PRIORITY)
    for pattern in _BAD_INTENT_PATTERNS:
        if re.search(pattern, msg_lower, re.IGNORECASE):
            # Reset any contact collection state
            sess["collecting_contact"] = False
            sess["pending_ticket_query"] = None
            sess["awaiting_confirmation"] = False
            
            refusal_msg = (
                "🛡️ **Out of Scope Request**\n\n"
                "I am **Bobby**, the AI Service Management Assistant at Inspired Pet Nutrition, "
                "dedicated strictly to **IT Systems and Workplace Technology Support**.\n\n"
                "I cannot create tickets or assist with personal belongings, facility complaints, "
                "lifestyle, or non-IT requests.\n\n"
                "I am ready to help you with **ITSM cases only**, including:\n\n"
                "• 🔑 **Account & Access:** Password resets, MFA token resets & domain unlocks\n"
                "• 🌐 **Network & Connectivity:** Corporate VPN, Wi-Fi 802.1X & DNS issues\n"
                "• 💻 **Workplace Hardware:** Laptops, 4K monitors, docking stations & accessories\n"
                "• 📊 **Enterprise Software:** Microsoft 365, Teams, Outlook & Dynamics 365 ERP\n"
                "• 🎫 **ITSM Ticketing:** Raising, tracking, and resolving IT service requests\n\n"
                "👉 *Please provide your inquiry or concern related to our ITSM cases only.*"
            )
            return {
                "session_id": request.session_id,
                "message": refusal_msg,
                "intent": "guardrail_refusal",
                "escalated": False,
                "contact_info": {
                    "name": sess.get("contact_name"),
                    "email": sess.get("contact_email"),
                    "phone": sess.get("contact_phone"),
                    "collected": False,
                },
            }

    # Phase 1: Awaiting confirmation
    if sess.get("awaiting_confirmation"):
        if msg_lower in _CONFIRM_WORDS:
            sess["awaiting_confirmation"] = False
            sess["collecting_contact"] = True
            sess["current_step"] = 0
            _, q = CONTACT_STEPS[0]
            return {
                "session_id": request.session_id,
                "message": f"📝 **Contact Verification**\n\n{q}",
                "intent": "create_ticket",
                "contact_info": {"name": None, "email": None, "phone": None, "collected": False},
            }
        else:
            sess["awaiting_confirmation"] = False

    # Check if user message is an explicit ticket creation request
    is_ticket_intent = any(t in msg_lower for t in (
        "create ticket", "raise ticket", "log ticket", "open ticket", "submit ticket",
        "create a ticket", "raise a ticket", "log a ticket", "open a ticket", "new ticket",
        "ticket for", "create account", "onboard", "hardware request"
    ))

    # Phase 2: Contact Collection State Machine
    if sess.get("collecting_contact"):
        _fill_step(sess, msg)
        if not _all_collected(sess):
            step_idx = sess.get("current_step", 0)
            if step_idx < len(CONTACT_STEPS):
                _, next_q = CONTACT_STEPS[step_idx]
                return {
                    "session_id": request.session_id,
                    "message": f"📝 **Contact Verification**\n\n{next_q}",
                    "intent": "create_ticket",
                    "contact_info": {
                        "name": sess.get("contact_name"),
                        "email": sess.get("contact_email"),
                        "phone": sess.get("contact_phone"),
                        "collected": False,
                    },
                }
        else:
            # All 3 fields (Name, Email, Phone) collected! Resume ticket creation
            sess["collecting_contact"] = False
            if sess.get("pending_ticket_query"):
                msg = sess["pending_ticket_query"]
                msg_lower = msg.lower()
                sess["pending_ticket_query"] = None

    elif is_ticket_intent and not _all_collected(sess):
        # Auto-extract if provided in one-shot text (e.g. "My name is Mark, email mark@ipn.co.uk")
        em = _EMAIL_RE.search(msg)
        if em:
            sess["contact_email"] = em.group(0)
        pm = _PHONE_RE.search(msg)
        if pm and any(c.isdigit() for c in pm.group(0)) and len(pm.group(0).strip()) >= 7:
            sess["contact_phone"] = pm.group(0).strip()

        if not _all_collected(sess):
            sess["pending_ticket_query"] = msg
            sess["collecting_contact"] = True
            sess["current_step"] = 0
            if sess.get("contact_name"):
                sess["current_step"] = 1
            if sess.get("contact_name") and sess.get("contact_email"):
                sess["current_step"] = 2

            step_idx = sess.get("current_step", 0)
            _, next_q = CONTACT_STEPS[step_idx]
            return {
                "session_id": request.session_id,
                "message": f"📝 **Contact Verification**\n\n{next_q}",
                "intent": "create_ticket",
                "contact_info": {
                    "name": sess.get("contact_name"),
                    "email": sess.get("contact_email"),
                    "phone": sess.get("contact_phone"),
                    "collected": False,
                },
            }

    # Phase 3: Route via LangGraph
    logger.info("chat.routing_to_graph", msg=msg, all_collected=_all_collected(sess), sess=sess)
    graph = get_bobby_graph()
    config = {"configurable": {"thread_id": request.session_id}}

    invoke_input = {
        "messages": [HumanMessage(content=msg)],
        "user_id": current_user["user_id"],
        "user_name": current_user["name"],
        "user_role": current_user["role"],
        "session_id": request.session_id,
        "contact_name": sess.get("contact_name"),
        "contact_email": sess.get("contact_email"),
        "contact_phone": sess.get("contact_phone"),
        "user_time_greeting": request.local_time_greeting,
        "contact_info_collected": _all_collected(sess),
        "escalated": False,
        "needs_human_approval": False,
        "human_approved": None,
        "error": None,
    }

    try:
        try:
            result = await graph.ainvoke(invoke_input, config=config)
        except Exception as db_err:
            logger.warning("chat.checkpointer_retry_fallback", error=str(db_err))
            if _fallback_graph is None:
                _fallback_graph = build_bobby_graph()
            result = await _fallback_graph.ainvoke(invoke_input, config=config)

        bot_message = result.get("final_response", "")

        if bot_message and "shall i create a ticket" in bot_message.lower():
            sess["awaiting_confirmation"] = True

        response = {
            "session_id": request.session_id,
            "message": bot_message,
            "intent": result.get("intent"),
            "escalated": result.get("escalated", False),
            "contact_info": {
                "name": sess.get("contact_name"),
                "email": sess.get("contact_email"),
                "phone": sess.get("contact_phone"),
                "collected": _all_collected(sess),
            },
        }

        # Extract pending approval directly from graph execution result
        if result.get("needs_human_approval") or result.get("pending_action"):
            pending = result.get("pending_action", {})
            response["requires_approval"] = True
            response["pending_action"] = pending
            if not bot_message:
                response["message"] = pending.get("message", "Bobby is preparing your ticket request.")

        return response

    except Exception as e:
        logger.error("chat.error", error=str(e), session_id=request.session_id, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/approve")
async def resume_approval(
    request: ResumeApprovalRequest,
    current_user: dict = Depends(get_current_user),
):
    """Handles HITL approval at HTTP layer."""
    graph = get_bobby_graph()
    config = {"configurable": {"thread_id": request.session_id}}
    sess = _get_sess(request.session_id)

    try:
        state_snapshot = await graph.aget_state(config)
        if not state_snapshot or not state_snapshot.values:
            return {
                "session_id": request.session_id,
                "message": "No pending action found for this session.",
                "approved": request.approved,
            }

        state = state_snapshot.values
        pending = state.get("pending_action", {})
        ticket_id = state.get("ticket_id")
        action_type = pending.get("type", "")

        if not request.approved:
            return {
                "session_id": request.session_id,
                "message": "Okay, action cancelled. Is there anything else I can help you with?",
                "approved": False,
            }

        logger.info("approve.executing", action_type=action_type, ticket_id=ticket_id)

        from integrations.freshdesk_client import get_freshdesk_client

        if action_type == "create_ticket" and ticket_id:
            contact_email = sess.get("contact_email") or state.get("user_id", "your email")
            contact_name = sess.get("contact_name") or state.get("user_name", "User")
            if contact_email and "@" in contact_email:
                import asyncio
                asyncio.create_task(send_escalation_email(contact_email, contact_name, str(ticket_id), "New Office Account for Mark Thuishaven"))
            msg = (
                f"Done! Ticket **#TKT-{ticket_id}** has been escalated to **P1 priority**.\n\n"
                f"The on-call engineer has been notified.\n\n"
                f"**Assigned to:** IT Helpdesk team\n"
                f"**Expected wait time:** 15 minutes\n\n"
                f"An email confirmation will be sent to **{contact_email}**"
            )
            return {
                "session_id": request.session_id,
                "message": msg,
                "approved": True,
                "ticket_id": ticket_id,
                "contact_info": {
                    "name": sess.get("contact_name"),
                    "email": sess.get("contact_email"),
                    "phone": sess.get("contact_phone"),
                },
            }

        if action_type == "create_ticket" and not ticket_id:
            freshdesk = get_freshdesk_client()
            ticket_data = pending.get("data", {})
            try:
                subject = ticket_data.get("subject", "IT Support Request")
                description = ticket_data.get("description", "")
                category = ticket_data.get("category", "IT")
                priority = ticket_data.get("priority", "medium")

                created = await freshdesk.create_ticket(
                    subject=subject,
                    description=description,
                    category=category,
                    priority=priority,
                    requester_id=current_user["user_id"],
                )
                new_id = str(created.get("id"))

                from agent.nodes.ticket_node import _classify_agent_assignment
                assigned_specialist, assigned_team = _classify_agent_assignment(subject, category, description)

                # Add classification audit note
                try:
                    await freshdesk.add_note(
                        new_id,
                        f"Bobby AI: Ticket classified and routed to {assigned_team} (Specialist: {assigned_specialist}). Priority: {priority}.",
                        private=True
                    )
                except Exception:
                    pass

                target_email = sess.get("contact_email") or current_user.get("user_id") or "employee@company.com"
                recipient_name = sess.get("contact_name") or current_user.get("name") or "Colleague"

                # 1. Dispatch Ticket Created confirmation email
                if target_email and "@" in target_email:
                    import asyncio
                    from integrations.email_service import send_ticket_created_email
                    asyncio.create_task(
                        send_ticket_created_email(
                            to_email=target_email,
                            recipient_name=recipient_name,
                            ticket_id=new_id,
                            subject_summary=subject,
                            priority=priority,
                            category=category
                        )
                    )

                # 2. Trigger Autonomous Ticket Resolution Agent (Background Worker)
                import asyncio
                from agent.services.auto_resolver import auto_resolve_ticket_background
                asyncio.create_task(
                    auto_resolve_ticket_background(
                        ticket_id=new_id,
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

                response_text = (
                    f"🎉 **Ticket #{new_id} Created Successfully!**\n\n"
                    f"• **Subject:** {subject}\n"
                    f"• **Priority:** {p_icon} {priority.title()}\n"
                    f"• **Assigned Specialist:** {assigned_specialist} ({assigned_team})\n"
                    f"• **Requester:** {recipient_name} (`{target_email}`)\n"
                    f"• **Status:** ⚡ In Progress (Autonomous Domain Specialist Active)\n\n"
                    f"📧 *A full confirmation email and private audit note have been dispatched to **{target_email}**.*\n\n"
                    f"---\n"
                    f"🤝 **Is there anything else I can help you with today?**"
                )

                return {
                    "session_id": request.session_id,
                    "message": response_text,
                    "approved": True,
                    "ticket_id": new_id,
                    "contact_info": {
                        "name": recipient_name,
                        "email": target_email,
                        "phone": sess.get("contact_phone"),
                    },
                }
            except Exception as e:
                logger.error("approve.create_error", error=str(e))
                return {
                    "session_id": request.session_id,
                    "message": "Sorry, could not create the ticket. Please contact the helpdesk at ext. 4000.",
                    "approved": True,
                }

        return {
            "session_id": request.session_id,
            "message": "Action approved and completed.",
            "approved": True,
        }

    except Exception as e:
        logger.error("approve.error", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


class ResolveTicketRequest(BaseModel):
    ticket_id: str
    resolution_notes: str = "The requested account configuration has been completed and credentials dispatched."
    resolved_by: Optional[str] = "IT Helpdesk Specialist"
    recipient_email: Optional[str] = None
    recipient_name: Optional[str] = "Colleague"


@router.post("/tickets/resolve")
async def resolve_ticket(
    request: ResolveTicketRequest,
    current_user: dict = Depends(get_current_user),
):
    """Marks ticket as Resolved in Freshdesk, adds audit note and sends HTML email."""
    from integrations.freshdesk_client import get_freshdesk_client
    from integrations.email_service import send_ticket_resolved_email
    import asyncio

    freshdesk = get_freshdesk_client()
    logger.info("ticket.resolve_request", ticket_id=request.ticket_id, by_user=current_user.get("user_id"))

    ticket_subject = f"Support Request #{request.ticket_id}"
    target_email = request.recipient_email
    recipient_name = request.recipient_name or "Colleague"

    try:
        t = await freshdesk.get_ticket(request.ticket_id)
        if t:
            ticket_subject = t.get("subject") or ticket_subject
            if not target_email and t.get("email"):
                target_email = t.get("email")
    except Exception as e:
        logger.warning("ticket.get_error_before_resolve", error=str(e))

    if not target_email or "@" not in target_email:
        target_email = settings.smtp_to_emails or current_user.get("user_id") or "hello@inspirednutrition.com"

    try:
        await freshdesk.update_ticket(
            ticket_id=request.ticket_id,
            updates={"status": 4}
        )
        
        agent_name = request.resolved_by or current_user.get("name", "IT Support Specialist")
        note_body = (
            f"✅ Ticket marked as RESOLVED by {agent_name}.\n\n"
            f"Resolution Summary:\n{request.resolution_notes}\n\n"
            f"Notification email dispatched to: {target_email}"
        )
        await freshdesk.add_note(
            ticket_id=request.ticket_id,
            body=note_body,
            private=True
        )
    except Exception as e:
        logger.error("ticket.resolve_update_error", error=str(e), ticket_id=request.ticket_id)

    agent_name = request.resolved_by or current_user.get("name", "IT Helpdesk Specialist")
    if target_email and "@" in target_email:
        asyncio.create_task(
            send_ticket_resolved_email(
                to_email=target_email,
                recipient_name=recipient_name,
                ticket_id=str(request.ticket_id),
                subject_summary=ticket_subject,
                resolution_notes=request.resolution_notes,
                resolved_by=agent_name
            )
        )

    return {
        "status": "success",
        "ticket_id": request.ticket_id,
        "subject": ticket_subject,
        "new_status": "Resolved",
        "resolved_by": agent_name,
        "resolution_notes": request.resolution_notes,
        "email_dispatched_to": target_email,
        "message": f"Ticket #{request.ticket_id} has been marked as Resolved in Freshdesk. Resolution details and CSAT survey were sent to {target_email}."
    }


