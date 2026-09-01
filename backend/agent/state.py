"""
Bobby LangGraph — State Definition
===================================
TicketState is the single source of truth that flows through
every node in the Bobby graph.

Rule: All nodes READ from state, return UPDATED state fields only.
      Never mutate state directly — always return a dict of changes.
"""
from __future__ import annotations
from typing import Optional, Annotated, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class TicketState(TypedDict):
    # ── Conversation history (LangGraph manages append) ───────────────────────
    messages: Annotated[list[BaseMessage], add_messages]

    # ── User context ──────────────────────────────────────────────────────────
    user_id: str
    user_name: str
    user_role: str          # "employee" | "helpdesk" | "admin"
    session_id: str         # maps to LangGraph thread_id

    # ── Contact info collection (for ticket & email notifications) ────────────
    contact_name: str | None        # full name provided by user in chat
    contact_email: str | None       # email for ticket notifications
    contact_phone: str | None       # phone/mobile number
    contact_info_collected: bool
    user_time_greeting: Optional[str]    # True once all 3 fields are gathered

    # ── Triage output ─────────────────────────────────────────────────────────
    intent: str             # "it_question" | "create_ticket" | "ticket_status"
                            # | "account_unlock" | "password_reset" | "out_of_scope"
    confidence: float       # 0.0 - 1.0
    raw_intent_response: str
    active_intent: str | None       # ongoing valid task; refusals do not overwrite it
    previous_valid_intent: str | None
    scope: str | None               # in_scope | out_of_scope | unsafe | unknown

    # ── Knowledge retrieval ───────────────────────────────────────────────────
    retrieved_docs: list[dict]
    knowledge_answer: str

    # ── Ticket context ────────────────────────────────────────────────────────
    proposed_ticket: dict | None     # ticket Bobby wants to create
    ticket_id: str | None            # created/found ticket ID
    ticket_details: dict | None

    # ── Account actions ───────────────────────────────────────────────────────
    target_user_id: str | None       # user whose account to act on

    # ── HITL (Human-in-the-loop) ──────────────────────────────────────────────
    needs_human_approval: bool
    human_approved: bool | None      # None=waiting, True=approved, False=rejected
    pending_action: dict | None      # what needs approval

    # ── Control flow ──────────────────────────────────────────────────────────
    escalated: bool
    escalation_reason: str
    error: str | None
    final_response: str
