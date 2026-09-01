"""Context-aware retrieval query tests."""
from types import SimpleNamespace

from agent.nodes.knowledge_node import _valid_evidence, build_search_query


def _message(content: str, message_type: str = "human"):
    return SimpleNamespace(content=content, type=message_type)


def test_contextual_follow_up_is_rewritten_from_previous_user_query():
    state = {
        "messages": [
            _message("My GlobalProtect VPN disconnects after MFA"),
            _message("Try reconnecting the VPN", "ai"),
            _message("It still fails after step three"),
        ]
    }
    query = build_search_query(state, "It still fails after step three")
    assert "GlobalProtect VPN" in query
    assert "Follow-up detail" in query


def test_standalone_query_is_not_rewritten():
    state = {"messages": [_message("How do I connect to VPN?")]}
    query = build_search_query(state, "How do I connect to VPN?")
    assert query == "How do I connect to VPN?"


def test_invalid_and_duplicate_evidence_is_removed():
    docs = [
        {"id": "1", "title": "VPN", "content": "Connect using GlobalProtect."},
        {"id": "1", "title": "VPN duplicate", "content": "Duplicate."},
        {"id": "2", "title": "Empty", "content": ""},
    ]
    assert _valid_evidence(docs) == [docs[0]]
