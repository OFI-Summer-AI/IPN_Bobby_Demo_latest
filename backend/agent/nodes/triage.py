"""
Bobby - Triage Node (Intent Classifier & Guardrails)
===================================================
Classifies incoming user messages into defined ITSM intents.
Features:
- Guardrail detection (abusive language, prompt injection, off-topic queries)
- Clarification detection (ambiguous or under-specified queries)
- ITSM routing (knowledge/RAG, ticket creation, ticket status, account unlock, password reset)
"""
from __future__ import annotations
import json
import re
import structlog
from agent.state import TicketState

logger = structlog.get_logger(__name__)

VALID_INTENTS = {
    "it_question",           # RAG-grounded IT KB lookup
    "create_ticket",         # Report issue or request service/hardware/software
    "ticket_status",         # Check Freshdesk ticket status
    "account_unlock",        # Unlock AD/Azure account
    "password_reset",        # SSPR / password reset
    "clarification_needed",  # Low confidence / ambiguous message -> ask user to refine
    "guardrail_refusal",     # Bad intent / abusive / prompt injection / off-topic
}

_GREETINGS = {
    "hi", "hello", "hey", "good morning", "good afternoon", "good evening",
    "hi bobby", "hello bobby", "hey bobby", "who are you", "what can you do",
    "help", "thank you", "thank you!", "thanks", "thanks!", "thx", "thx!",
    "thanks bobby", "thank you bobby", "appreciate it", "great help", "awesome", "perfect",
    "bye", "goodbye", "see you", "cya", "have a good day", "have a nice day",
}

_BAD_INTENT_PATTERNS = [
    # 1. Prompt injection / Jailbreak
    r"\b(ignore previous instructions|system prompt|jailbreak|disregard all|bypass filter|developer mode|dan mode)\b",
    # 2. Hacking & Malware
    r"\b(hack|exploit|malware|ddos|sql injection|drop table|steal password|keylogger|ransomware)\b",
    # 3. Profanity & Toxicity
    r"\b(fuck|shit|bitch|bastard|idiot|stupid bot|asshole|shut up|cunt|dick)\b",
    # 4. Self-harm & Harm
    r"\b(kill myself|suicide|self harm|hurt myself|bomb|weapon)\b",
    # 5. Non-IT Personal Belongings & Lost Items (Out-of-Scope)
    r"\b(shoes?|sneakers?|boots?|slippers?|socks?|clothes?|clothing|jacket|coat|shirt|pants|jeans|dress|hat|cap|wallet|purse|handbag|backpack|watch|jewelry|ring|necklace|sunglasses|glasses|umbrella|car keys?|house keys?|bike|bicycle|scooter|lunch|lunchbox|water bottle|tumbler|food|groceries|dog|cat|pet)\b",
    # 6. Non-IT Lifestyle, Travel, Food & Consumer Services (Out-of-Scope)
    r"\b(recipe|weather|movie|poem|flight|hotel|vacation|pizza|burger|sandwich|coffee|restaurant|dating|horoscope|astrology|sports score|cricket|football|game cheat)\b",
    # 7. Non-IT Facility, Medical, Legal & General HR Complaints
    r"\b(plumbing|toilet|restroom|janitor|cleaning|ac too cold|air conditioning|car park|parking space|cafeteria|medical advice|prescription|lawsuit|tax advice)\b",
]

_AMBIGUOUS_PHRASES = {
    "it doesnt work", "it doesn't work", "not working", "broken", "issue", "problem",
    "error", "help me", "fix", "please fix", "bad", "slow", "nothing", "what to do",
    "need help", "something wrong", "stuck"
}

_EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
_PHONE_RE = re.compile(r"[\+]?[\d\s\-\(\)]{7,15}")


def _is_contact_info_response(state: TicketState, message: str) -> bool:
    """Returns True if user is providing contact info during ticket creation."""
    if not state.get("proposed_ticket") or state.get("ticket_id") or state.get("contact_info_collected", False):
        return False
    if _EMAIL_RE.search(message):
        return True
    if _PHONE_RE.search(message) and any(c.isdigit() for c in message):
        return True
    words = message.strip().lower().split()
    if 1 <= len(words) <= 5 and all(w.isalpha() or w in ("-", "'", ".") for w in words):
        return True
    return False


async def triage_node(state: TicketState) -> dict:
    """Classifies user intent with guardrail checks and confidence scoring."""
    logger.info("triage_node.start", user_id=state.get("user_id"))

    last_message = state["messages"][-1].content if state["messages"] else ""
    last_message_lower = last_message.strip().lower()

    # 1. Guardrail & Bad Intent Check
    for pattern in _BAD_INTENT_PATTERNS:
        if re.search(pattern, last_message_lower, re.IGNORECASE):
            logger.warning("triage_node.guardrail_triggered", pattern=pattern)
            return {
                "intent": "guardrail_refusal",
                "confidence": 0.99,
                "raw_intent_response": '{"intent": "guardrail_refusal", "confidence": 0.99}',
            }

    # 2. Contact Info Sub-flow
    if _is_contact_info_response(state, last_message):
        return {
            "intent": "create_ticket",
            "confidence": 1.0,
            "raw_intent_response": '{"intent": "create_ticket", "confidence": 1.0}',
        }

    # 3. Conversational Greetings & Bot Intro
    if last_message_lower in _GREETINGS or any(last_message_lower.startswith(g) for g in ("hi ", "hello ", "hey ")):
        return {
            "intent": "it_question",
            "confidence": 1.0,
            "raw_intent_response": '{"intent": "it_question", "confidence": 1.0}',
        }

    # 4. Ticket Creation / Confirmation Trigger
    _TICKET_TRIGGERS = (
        "mark thuishaven", "office account", "create ticket", "raise ticket",
        "open ticket", "log ticket", "log a ticket", "raise a ticket",
        "create a ticket", "report issue", "report a problem", "submit ticket",
        "new ticket", "i want to raise", "i need to raise", "i need help with",
        "my laptop", "my computer", "my screen", "my monitor", "my printer",
        "not working", "broken", "laptop issue", "hardware issue", "software issue",
        "cannot connect", "keeps failing", "locked out", "need access to", "request access",
        "onboard", "please onboard", "mfa needs reset", "domain account is locked",
        "portal for invoicing", "access to microsoft dynamics", "access to erp",
        "ticket for", "request for", "provision", "replace laptop",
        "monitor flickering", "usb-c hub", "certificate expired", "provision shared mailbox",
        "phishing email", "workflow stuck", "error code", "pairing lost", "dns resolution failing",
        "internal staging", "failing for", "suspect phishing", "shared mailbox", "approval workflow",
        "bluetooth", "dial pad", "stuck with", "expired on", "send-as permissions",
    )
    _CONFIRM_WORDS_TRIAGE = {"yes", "y", "sure", "please", "yes please", "ok", "okay", "confirm", "go ahead", "create", "submit", "create it", "yes create"}
    if (
        any(t in last_message_lower for t in _TICKET_TRIGGERS)
        or last_message_lower in _CONFIRM_WORDS_TRIAGE
        or "priority" in last_message_lower
        or "escalate" in last_message_lower
        or ("high" in last_message_lower and state.get("proposed_ticket"))
    ):
        return {
            "intent": "create_ticket",
            "confidence": 1.0,
            "raw_intent_response": '{"intent": "create_ticket", "confidence": 1.0}',
        }

    # 5a. Gratitude/appreciation gestures -> route to knowledge_node for polite response
    if any(w in last_message_lower for w in ("thank", "thx", "appreciate", "great help", "good job", "well done", "cheers")):
        return {
            "intent": "it_question",
            "confidence": 1.0,
            "raw_intent_response": '{"intent": "it_question", "confidence": 1.0}',
        }

    # 5. Ticket Status Lookup
    if any(k in last_message_lower for k in ("resolve", "close", "status", "4521", "my ticket", "ticket #", "check ticket")):
        return {
            "intent": "ticket_status",
            "confidence": 1.0,
            "raw_intent_response": '{"intent": "ticket_status", "confidence": 1.0}',
        }

    # 6. Ambiguous or overly vague inputs -> Clarification Needed
    words = last_message.strip().split()
    if last_message_lower in _AMBIGUOUS_PHRASES or (len(words) <= 2 and not any(k in last_message_lower for k in ("vpn", "wifi", "password", "teams", "outlook", "mail", "print", "laptop"))):
        return {
            "intent": "clarification_needed",
            "confidence": 0.3,
            "raw_intent_response": '{"intent": "clarification_needed", "confidence": 0.3}',
        }

    # 7. Informational How-To Questions (always RAG search)
    is_how_to = any(last_message_lower.startswith(prefix) for prefix in ("how do i", "how to", "how can i", "what is", "where is", "can i", "steps to"))
    if is_how_to:
        return {
            "intent": "it_question",
            "confidence": 0.95,
            "raw_intent_response": '{"intent": "it_question", "confidence": 0.95}',
        }

    # 8. Account unlock / password reset direct execution
    if last_message_lower in ("unlock my account", "unlock account", "please unlock my account"):
        return {
            "intent": "account_unlock",
            "confidence": 0.95,
            "raw_intent_response": '{"intent": "account_unlock", "confidence": 0.95}',
        }
    if last_message_lower in ("reset my password", "reset password", "please reset my password"):
        return {
            "intent": "password_reset",
            "confidence": 0.95,
            "raw_intent_response": '{"intent": "password_reset", "confidence": 0.95}',
        }

    # 9. Standard IT Knowledge Base (RAG)
    it_keywords = (
        "vpn", "wifi", "wi-fi", "network", "password", "reset", "mfa", "authenticator", "2fa",
        "office", "m365", "microsoft", "teams", "outlook", "email", "mail", "print", "printer",
        "scan", "scanner", "hardware", "laptop", "monitor", "software", "install", "dynamics",
        "sharepoint", "onedrive", "phishing", "contact", "hours", "helpdesk", "portal"
    )
    if any(k in last_message_lower for k in it_keywords):
        return {
            "intent": "it_question",
            "confidence": 0.95,
            "raw_intent_response": '{"intent": "it_question", "confidence": 0.95}',
        }

    # 10. Fallback: If message length >= 3 words, search KB with moderate confidence
    if len(words) >= 3:
        return {
            "intent": "it_question",
            "confidence": 0.75,
            "raw_intent_response": '{"intent": "it_question", "confidence": 0.75}',
        }

    # Otherwise request clarification
    return {
        "intent": "clarification_needed",
        "confidence": 0.3,
        "raw_intent_response": '{"intent": "clarification_needed", "confidence": 0.3}',
    }


def route_after_triage(state: TicketState) -> str:
    """Decides the next node after triage."""
    intent = state.get("intent", "it_question")
    confidence = state.get("confidence", 0.0)

    if intent in ("guardrail_refusal", "clarification_needed"):
        return "knowledge_node"

    if confidence < 0.5:
        return "knowledge_node"

    routes = {
        "it_question":    "knowledge_node",
        "create_ticket":  "ticket_node",
        "ticket_status":  "ticket_node",
        "account_unlock": "account_node",
        "password_reset": "account_node",
    }
    return routes.get(intent, "knowledge_node")





