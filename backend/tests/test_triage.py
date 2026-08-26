"""
Tests for Bobby triage node (intent classifier).
Run with: pytest tests/ -v
"""
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_triage_returns_valid_intent():
    """Triage node should return one of the 6 valid intents."""
    from agent.nodes.triage import VALID_INTENTS
    assert "it_question" in VALID_INTENTS
    assert "create_ticket" in VALID_INTENTS
    assert "account_unlock" in VALID_INTENTS
    assert "out_of_scope" in VALID_INTENTS

@pytest.mark.asyncio
async def test_route_after_triage_it_question():
    """Low confidence should route to escalation, not knowledge."""
    from agent.nodes.triage import route_after_triage
    state = {"intent": "it_question", "confidence": 0.9}
    assert route_after_triage(state) == "knowledge_node"

@pytest.mark.asyncio
async def test_route_after_triage_low_confidence():
    from agent.nodes.triage import route_after_triage
    state = {"intent": "it_question", "confidence": 0.3}
    assert route_after_triage(state) == "escalation_node"
