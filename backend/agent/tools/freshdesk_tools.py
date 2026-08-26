"""
Bobby — Freshdesk LangChain Tools
====================================
These are LangChain @tool-decorated functions that the Bobby agent
can call directly from within a node using tool-calling.

They wrap the FreshdeskClient with typed inputs that the LLM can fill.

Usage in a node:
  from agent.tools.freshdesk_tools import create_ticket_tool, get_tickets_tool
  tools = [create_ticket_tool, get_tickets_tool]
"""
from __future__ import annotations
from langchain_core.tools import tool
from integrations.freshdesk_client import get_freshdesk_client


@tool
async def create_ticket_tool(
    subject: str,
    description: str,
    category: str = "IT",
    priority: str = "medium",
    requester_email: str = "",
) -> dict:
    """
    Creates a support ticket in Freshdesk.
    Use this when the user wants to report a problem or make a service request.

    Args:
        subject: Short title for the ticket (max 255 chars)
        description: Detailed description of the issue
        category: One of 'IT', 'HR', 'Finance', 'General'
        priority: One of 'low', 'medium', 'high', 'urgent'
        requester_email: Email of the user raising the ticket

    Returns:
        Dict with ticket id, subject, and status
    """
    client = get_freshdesk_client()
    result = await client.create_ticket(
        subject=subject,
        description=description,
        category=category,
        priority=priority,
        requester_id=requester_email,
    )
    return {"ticket_id": result.get("id"), "subject": subject, "status": "created"}


@tool
async def get_tickets_tool(user_email: str, status: str = "") -> list[dict]:
    """
    Gets open tickets for a user by their email address.
    Use this when the user asks about their ticket status.

    Args:
        user_email: Email of the user
        status: Optional filter — 'open', 'resolved', 'closed', or empty for all

    Returns:
        List of ticket dicts with id, subject, status
    """
    client = get_freshdesk_client()
    tickets = await client.get_tickets_by_user(
        user_email=user_email,
        status=status or None,
    )
    return tickets


@tool
async def search_tickets_tool(query: str) -> list[dict]:
    """
    Searches Freshdesk tickets by keyword.
    Use this when the user mentions a specific issue or ticket topic.

    Args:
        query: Search keyword or phrase

    Returns:
        List of matching tickets
    """
    client = get_freshdesk_client()
    return await client.search_tickets(query)


@tool
async def add_note_to_ticket_tool(ticket_id: str, note: str) -> dict:
    """
    Adds an internal note to an existing ticket.
    Use this to record actions taken by Bobby.

    Args:
        ticket_id: The Freshdesk ticket ID
        note: Text of the note to add

    Returns:
        Dict confirming the note was added
    """
    client = get_freshdesk_client()
    result = await client.add_note(ticket_id=ticket_id, body=note, private=True)
    return {"status": "note_added", "ticket_id": ticket_id}
