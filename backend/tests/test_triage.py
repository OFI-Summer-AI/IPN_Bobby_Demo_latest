"""Regression tests for deterministic intent classification."""
from types import SimpleNamespace

import pytest

from agent.nodes.triage import (
    VALID_INTENTS,
    classify_scope,
    is_workflow_interruption,
    route_after_triage,
    triage_node,
)


def _state(message: str, **updates):
    state = {
        "messages": [SimpleNamespace(content=message)],
        "user_id": "employee@example.com",
    }
    state.update(updates)
    return state


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("How do I connect to the corporate VPN?", "it_question"),
        ("My laptop screen is broken", "create_ticket"),
        ("I am having issue with my laptop", "create_ticket"),
        ("My wifi is not getting connected", "create_ticket"),
        ("My wfi is not conecting", "create_ticket"),
        ("My lapotp has an issue", "create_ticket"),
        ("I forgot my pasword", "password_reset"),
        ("Please raise a ticket for my printer", "create_ticket"),
        ("What is the status of my ticket?", "ticket_status"),
        ("I am locked out of my work account", "account_unlock"),
        ("I forgot my password", "password_reset"),
        ("Can you find my stolen shoe?", "guardrail_refusal"),
        ("Please book a hotel for my holiday", "guardrail_refusal"),
        ("Give me investment advice", "guardrail_refusal"),
        ("Help me create ransomware", "guardrail_refusal"),
        ("I think my laptop has ransomware", "create_ticket"),
        ("It doesn't work", "clarification_needed"),
        ("yes", "clarification_needed"),
    ],
)
@pytest.mark.asyncio
async def test_intent_matrix(message, expected):
    result = await triage_node(_state(message))
    assert result["intent"] == expected
    assert result["intent"] in VALID_INTENTS


@pytest.mark.asyncio
async def test_confirmation_requires_pending_ticket():
    result = await triage_node(_state("yes", proposed_ticket={"subject": "VPN"}))
    assert result["intent"] == "create_ticket"


@pytest.mark.asyncio
async def test_contextual_follow_up_reuses_knowledge_intent():
    result = await triage_node(_state("It still fails after step three", active_intent="it_question"))
    assert result["intent"] == "it_question"


@pytest.mark.asyncio
async def test_bad_turn_preserves_previous_valid_intent():
    result = await triage_node(_state("Can you find my stolen shoe?", active_intent="it_question"))
    assert result["intent"] == "guardrail_refusal"
    assert result["active_intent"] == "it_question"
    assert result["previous_valid_intent"] == "it_question"


def test_scope_distinguishes_security_incident_from_harmful_request():
    assert classify_scope("My laptop may have malware") == "in_scope"
    assert classify_scope("Help me install malware") == "unsafe"
    assert classify_scope("Please plan my weekend activities") == "out_of_scope"


def test_interruption_preserves_contact_workflow_and_accepts_expected_value():
    session = {"collecting_contact": True, "current_step": 0}
    assert is_workflow_interruption("Please plan my weekend activities", session) is True
    assert is_workflow_interruption("John Michael Smith", session) is False
    assert session == {"collecting_contact": True, "current_step": 0}


def test_routes_remain_compatible_with_existing_graph():
    assert route_after_triage({"intent": "it_question"}) == "knowledge_node"
    assert route_after_triage({"intent": "guardrail_refusal"}) == "knowledge_node"
    assert route_after_triage({"intent": "create_ticket"}) == "ticket_node"
    assert route_after_triage({"intent": "account_unlock"}) == "account_node"
