"""Deterministic intent classification and scope guardrails for Bobby."""
from __future__ import annotations

import json
import re

import structlog

from agent.state import TicketState
from text_utils import (
    EMAIL_RE,
    PHONE_RE,
    extract_message_text,
    is_valid_contact_name,
    normalize_query,
)

logger = structlog.get_logger(__name__)

VALID_INTENTS = {
    "it_question",
    "create_ticket",
    "ticket_status",
    "account_unlock",
    "password_reset",
    "clarification_needed",
    "guardrail_refusal",
}

_GREETINGS = {
    "hi", "hello", "hey", "good morning", "good afternoon", "good evening",
    "hi bobby", "hello bobby", "hey bobby", "who are you", "what can you do",
    "help", "thank you", "thank you!", "thanks", "thanks!", "thx", "thx!",
    "thanks bobby", "thank you bobby", "appreciate it", "great help", "awesome",
    "perfect", "bye", "goodbye", "see you", "cya", "have a good day",
    "have a nice day",
}

# Kept as a public module constant because the HTTP command layer imports it.
# These patterns are deliberately phrase-oriented: isolated security terms such as
# "malware" are valid when an employee is reporting an incident.
_BAD_INTENT_PATTERNS = [
    r"\b(ignore (all |any )?(previous|prior) instructions|reveal (the )?(system|developer) prompt|"
    r"show (me )?(the )?(system|developer) prompt|jailbreak|developer mode|dan mode|"
    r"bypass (the )?(safety|security|filter|guardrail)s?)\b",
    r"\b(how (do|can|could) i|help me|write|build|create|deploy|install|spread|send|launch)\b.{0,50}"
    r"\b(malware|ransomware|keylogger|ddos|sql injection|computer virus|phishing campaign)\b",
    r"\b(steal|harvest|exfiltrate|crack)\b.{0,35}\b(passwords?|credentials?|accounts?|data)\b",
    r"\b(fuck|shit|bitch|bastard|stupid bot|asshole|shut up|cunt)\b",
    r"\b(kill myself|commit suicide|self[ -]?harm|hurt myself|build a bomb|make a weapon)\b",
]

_OUT_OF_SCOPE_PATTERNS = [
    r"\b(find|locate|track|where (is|are)|lost|stolen)\b.{0,40}\b(shoes?|sneakers?|boots?|"
    r"slippers?|socks?|clothes?|jacket|wallet|purse|handbag|watch|jewelry|umbrella|car keys?|"
    r"house keys?|lunch|water bottle|dog|cat|pet)\b",
    r"\b(recipe|weather forecast|movie recommendation|write (a )?poem|book (a )?(flight|hotel)|"
    r"vacation plan|restaurant recommendation|dating advice|horoscope|astrology|sports score|"
    r"football score|cricket score)\b",
    r"\b(plumbing|blocked toilet|clean the restroom|janitor|cafeteria menu|medical advice|"
    r"prescription|lawsuit|legal advice|tax advice|parking space)\b",
    r"\b(stock|crypto|investment|trading) (tip|tips|advice|recommendation)s?\b",
]

_IT_KEYWORDS = {
    "account", "access", "active directory", "ad account", "azure", "bitlocker",
    "bluetooth", "certificate", "computer", "credentials", "cyber", "database", "device",
    "dns", "domain", "dynamics", "email", "endpoint", "erp", "excel", "firewall",
    "globalprotect", "hardware", "helpdesk", "internet", "intranet", "ip address", "it support",
    "keyboard", "laptop", "login", "log in", "mail", "malware", "mfa", "microsoft",
    "monitor", "mouse", "network", "office 365", "onedrive", "outlook", "password",
    "phishing", "portal", "printer", "ransomware", "security", "server", "sharepoint", "software",
    "teams", "ticket", "usb", "username", "vpn", "wi-fi", "wifi", "windows",
    "workflow",
}

_AMBIGUOUS_PHRASES = {
    "it doesnt work", "it doesn't work", "not working", "broken", "issue", "problem",
    "error", "help me", "fix", "please fix", "bad", "slow", "nothing", "what to do",
    "need help", "something wrong", "stuck", "yes", "no", "okay", "ok",
}

CONFIRM_WORDS = {
    "yes", "y", "sure", "please", "yes please", "ok", "okay", "confirm", "yep", "yup",
    "go ahead", "create", "submit", "create it", "yes create",
}
_EXPLICIT_TICKET_RE = re.compile(
    r"\b(create|raise|open|log|submit|new)\b.{0,15}\b(ticket|case|request)\b|"
    r"\b(ticket|case) for\b|\breport\b.{0,15}\b(issue|problem|incident)\b|"
    r"\b(create account|onboard|hardware request)\b",
    re.IGNORECASE,
)

def _matches_any(patterns: list[str], message: str) -> bool:
    return any(re.search(pattern, message, re.IGNORECASE) for pattern in patterns)


def _has_it_signal(message: str) -> bool:
    return any(keyword in message for keyword in _IT_KEYWORDS)


def is_explicit_ticket_request(message: str) -> bool:
    """Return True for an explicit request to open a ticket or service case."""
    return bool(_EXPLICIT_TICKET_RE.search(message.strip()))


def classify_scope(message: str) -> str:
    """Classify scope without an LLM: safe values are in_scope/out_of_scope/unsafe/unknown."""
    text = normalize_query(message)
    if _matches_any(_BAD_INTENT_PATTERNS, text):
        return "unsafe"
    if _matches_any(_OUT_OF_SCOPE_PATTERNS, text):
        return "out_of_scope"
    if _has_it_signal(text):
        return "in_scope"
    words = text.split()
    if (
        text in _GREETINGS
        or text in _AMBIGUOUS_PHRASES
        or EMAIL_RE.search(text)
        or PHONE_RE.search(text)
        or len(words) <= 2
        or text.startswith("i need help with")
    ):
        return "unknown"
    # Complete requests without an IT signal are out of Bobby's supported scope.
    # Contact collection explicitly exempts valid values at the HTTP layer.
    if len(words) >= 3:
        return "out_of_scope"
    return "unknown"


def is_workflow_interruption(message: str, session: dict, scope: str | None = None) -> bool:
    """Return True when a turn should bypass, but not cancel, contact collection."""
    scope = scope or classify_scope(message)
    if scope not in ("unsafe", "out_of_scope"):
        return False
    if not session.get("collecting_contact"):
        return True

    step = session.get("current_step", 0)
    if step == 0:
        return not is_valid_contact_name(message)
    if step == 1:
        return not bool(EMAIL_RE.fullmatch(message.strip()))
    if step == 2:
        return not bool(PHONE_RE.fullmatch(message.strip()))
    return True


def _is_contact_info_response(state: TicketState, message: str) -> bool:
    if not state.get("proposed_ticket") or state.get("ticket_id") or state.get("contact_info_collected", False):
        return False
    if EMAIL_RE.search(message) or PHONE_RE.search(message):
        return True
    return is_valid_contact_name(message)


def _result(
    intent: str,
    confidence: float,
    previous_valid: str | None = None,
    scope: str | None = None,
) -> dict:
    if scope is None:
        scope = "unknown" if intent == "clarification_needed" else "in_scope"
    payload = {"intent": intent, "confidence": confidence}
    result = {
        "intent": intent,
        "confidence": confidence,
        "scope": scope,
        "raw_intent_response": json.dumps(payload),
    }
    if intent not in ("guardrail_refusal", "clarification_needed"):
        result["active_intent"] = intent
        result["previous_valid_intent"] = intent
    elif previous_valid:
        # Refusals are turn-local and must not destroy the active valid workflow.
        result["active_intent"] = previous_valid
        result["previous_valid_intent"] = previous_valid
    logger.info(
        "classification.result",
        scope=scope,
        intent=intent,
        confidence=confidence,
        method="deterministic_rules",
        previous_intent=previous_valid,
    )
    return result


async def triage_node(state: TicketState) -> dict:
    """Classify the latest message using deterministic precedence and conversation state."""
    raw_message = state["messages"][-1].content if state.get("messages") else ""
    last_message = extract_message_text(raw_message)
    text = normalize_query(last_message)
    previous_valid = state.get("active_intent") or state.get("previous_valid_intent")
    is_contextual_follow_up = bool(re.search(
        r"\b(still|again|that|this|those|after|before|same|didn't|doesn't|not fixed)\b",
        text,
    ))
    logger.info("triage_node.start", user_id=state.get("user_id"), previous_intent=previous_valid)

    # Active workflow responses take precedence over generic words such as yes/no/name.
    if _is_contact_info_response(state, last_message):
        return _result("create_ticket", 1.0, previous_valid)

    scope = classify_scope(last_message)
    if (
        scope == "out_of_scope"
        and previous_valid == "it_question"
        and is_contextual_follow_up
        and not _matches_any(_OUT_OF_SCOPE_PATTERNS, text)
    ):
        return _result("it_question", 0.82, previous_valid)
    if scope in ("unsafe", "out_of_scope"):
        return _result("guardrail_refusal", 0.99, previous_valid, scope=scope)

    if text in _GREETINGS or any(text.startswith(g) for g in ("hi ", "hello ", "hey ")):
        return _result("it_question", 1.0, previous_valid)

    if any(word in text for word in ("thank", "thx", "appreciate", "great help", "good job", "well done", "cheers")):
        return _result("it_question", 1.0, previous_valid)

    # Specific account actions must be evaluated before broad issue/ticket rules.
    if re.search(r"\b(unlock|locked out of|account (is )?locked|domain account (is )?locked)\b", text):
        return _result("account_unlock", 0.98, previous_valid)
    if re.search(r"\b(reset|change)\b.{0,20}\b(password|passcode)\b", text) or re.search(
        r"\b(forgot(ten)?|expired)\b.{0,20}\bpassword\b", text
    ):
        return _result("password_reset", 0.98, previous_valid)

    # Ticket status requires explicit ticket context, not generic words like close/resolve.
    if re.search(r"\b(status|update|progress|track|tracking)\b.{0,30}\b(ticket|case|request)\b", text) or re.search(
        r"\b(ticket|case)\s*#?\s*\d+\b", text
    ) or re.search(r"\b(my|the) ticket\b", text):
        return _result("ticket_status", 0.98, previous_valid)

    has_pending_ticket = bool(state.get("proposed_ticket") or previous_valid == "create_ticket")
    if text in CONFIRM_WORDS and has_pending_ticket:
        return _result("create_ticket", 1.0, previous_valid)

    explicit_ticket = is_explicit_ticket_request(text)
    service_request = re.search(
        r"\b(request|need|new|create|provision|install|replace)\b.{0,35}"
        r"\b(access|account|software|hardware|laptop|monitor|mailbox|license)\b",
        text,
    )
    incident_statement = _has_it_signal(text) and bool(re.search(
        r"\b(issue|problem|not working|not connecting|not getting connected|won't connect|cannot connect|"
        r"can't connect|broken|fails?|failing|error|disconnect|cannot|can't|unable|lost|stolen|"
        r"infected|compromised|suspect|suspected|stuck|may have|might have|think .* has|received .* alert)\b",
        text,
    ))
    if explicit_ticket or service_request or incident_statement:
        return _result("create_ticket", 0.96, previous_valid)

    how_to = text.startswith(("how do i", "how to", "how can i", "what is", "where is", "can i", "steps to"))
    if _has_it_signal(text) or (how_to and previous_valid == "it_question"):
        return _result("it_question", 0.94, previous_valid)

    # Contextual follow-ups reuse a previous knowledge topic without treating arbitrary
    # unrelated sentences as IT queries.
    if is_contextual_follow_up and previous_valid == "it_question":
        return _result("it_question", 0.82, previous_valid)

    words = text.split()
    generic_help = bool(re.fullmatch(r"(can|could|would)?\s*(you\s*)?(please\s*)?help( me)?[?.!]?", text))
    if text in _AMBIGUOUS_PHRASES or generic_help or text.startswith("i need help with") or len(words) <= 2:
        return _result("clarification_needed", 0.3, previous_valid)

    # A complete request with no IT signal is positively out of scope. This replaces
    # the old "three words means IT" fallback that caused most false positives.
    return _result("guardrail_refusal", 0.85, previous_valid, scope="out_of_scope")


def route_after_triage(state: TicketState) -> str:
    intent = state.get("intent", "clarification_needed")
    routes = {
        "it_question": "knowledge_node",
        "create_ticket": "ticket_node",
        "ticket_status": "ticket_node",
        "account_unlock": "account_node",
        "password_reset": "account_node",
        "guardrail_refusal": "knowledge_node",
        "clarification_needed": "knowledge_node",
    }
    return routes.get(intent, "knowledge_node")
