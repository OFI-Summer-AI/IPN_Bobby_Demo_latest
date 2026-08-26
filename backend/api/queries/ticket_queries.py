"""Bobby — CQRS Queries: Ticket & Knowledge (bypass LangGraph)"""
from __future__ import annotations
from fastapi import APIRouter, Depends, Query
from integrations.freshdesk_client import get_freshdesk_client
from middleware.auth import get_current_user

router = APIRouter(prefix="/queries")


@router.get("/tickets")
async def get_my_tickets(
    status: str | None = Query(None, description="open|resolved|closed"),
    current_user: dict = Depends(get_current_user),
):
    """Get current user's tickets — bypasses LangGraph, direct Freshdesk call."""
    freshdesk = get_freshdesk_client()
    tickets = await freshdesk.get_tickets_by_user(current_user["user_id"], status=status)
    return {"tickets": tickets, "count": len(tickets)}


@router.get("/tickets/{ticket_id}")
async def get_ticket_detail(
    ticket_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get a single ticket by ID."""
    freshdesk = get_freshdesk_client()
    ticket = await freshdesk.get_ticket(ticket_id)
    return ticket


@router.get("/tickets/search")
async def search_tickets(
    q: str = Query(..., description="Search query"),
    current_user: dict = Depends(get_current_user),
):
    """Search tickets — bypasses LangGraph."""
    freshdesk = get_freshdesk_client()
    tickets = await freshdesk.search_tickets(q)
    return {"tickets": tickets, "query": q}
