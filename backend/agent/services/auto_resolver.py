"""
Bobby — Autonomous Ticket Resolution Agent
==========================================
Delegates resolution to the Multi-Agent Ticket Orchestrator, which routes
to the appropriate Domain Specialist Agent (Workplace, Network, IAM, Security, Apps),
updates Freshdesk status to 4 (Resolved), and dispatches the HTML email with CSAT survey.
"""
from __future__ import annotations
import structlog
from agent.services.orchestrator import orchestrator, ResolutionReport

logger = structlog.get_logger(__name__)


async def auto_resolve_ticket_background(
    ticket_id: str,
    subject: str,
    category: str,
    recipient_email: str,
    recipient_name: str,
    delay_seconds: int = 4,
    description: str = ""
) -> ResolutionReport:
    """
    Background worker that runs the full multi-agent resolution lifecycle:
    1. Orchestrator analyzes ticket and assigns to Domain Specialist Agent
    2. Specialist agent executes resolution actions
    3. Freshdesk status updated to 4 (Resolved) with audit notes
    4. Branded HTML resolution email dispatched to the user
    """
    logger.info("auto_resolver.delegating_to_orchestrator", ticket_id=ticket_id, recipient=recipient_email)
    return await orchestrator.process_and_resolve(
        ticket_id=ticket_id,
        subject=subject,
        category=category,
        description=description or subject,
        recipient_email=recipient_email,
        recipient_name=recipient_name,
        delay_seconds=delay_seconds
    )
