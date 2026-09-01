"""
Bobby - Knowledge Node (RAG, Greetings, Gestures & Observability)
"""
from __future__ import annotations
import datetime
import re
import structlog
from langchain_core.messages import HumanMessage, SystemMessage
from agent.state import TicketState
from config.settings import settings
from integrations.search_client import get_search_client
from integrations.observability import observe_node
from text_utils import extract_message_text, normalize_query

logger = structlog.get_logger(__name__)

SYNTHESIS_PROMPT = """You are Bobby, an IT support assistant for Inspired Pet Nutrition (IPN).
Answer the user question using the provided IT knowledge base context below.
Be concise, professional, and include numbered steps where applicable.
If context is insufficient, offer to create a support ticket.
Do not use outside knowledge or invent steps that are absent from the context.
Mention the title or source of the guide used for the answer.

Knowledge Base Context:
{context}
"""

_CONTEXTUAL_FOLLOW_UP = re.compile(
    r"\b(it|that|this|those|still|again|same|after|before|step|didn't|doesn't|not fixed)\b",
    re.IGNORECASE,
)
_SEARCH_CONTEXT_TERMS = (
    "vpn", "wifi", "network", "password", "account", "mfa", "teams", "outlook",
    "email", "printer", "laptop", "monitor", "software", "access", "sharepoint",
    "onedrive", "dynamics", "malware", "phishing", "windows", "certificate",
)


def build_search_query(state: TicketState, user_query: str) -> str:
    """Expand a vague follow-up with the most recent relevant user query."""
    normalized_query = normalize_query(user_query)
    if not _CONTEXTUAL_FOLLOW_UP.search(normalized_query) or any(
        term in normalized_query for term in _SEARCH_CONTEXT_TERMS
    ):
        return user_query

    messages = list(state.get("messages") or [])
    for message in reversed(messages[:-1]):
        message_type = getattr(message, "type", getattr(message, "role", ""))
        if message_type not in ("human", "user", ""):
            continue
        content = str(getattr(message, "content", "")).strip()
        if content and any(term in normalize_query(content) for term in _SEARCH_CONTEXT_TERMS):
            return f"{content}\nFollow-up detail: {user_query}"
    return user_query


def _get_time_aware_greeting(user_query: str = "", user_time_greeting: str | None = None) -> str:
    """Returns time-sensitive greeting based on client local time or query context."""
    if user_time_greeting and user_time_greeting.strip():
        clean_g = user_time_greeting.strip().capitalize()
        if not clean_g.endswith("!"):
            clean_g += "!"
        return clean_g

    q_lower = user_query.lower()
    if "good afternoon" in q_lower or "afternoon" in q_lower:
        return "Good afternoon!"
    if "good evening" in q_lower or "evening" in q_lower or "night" in q_lower:
        return "Good evening!"
    if "good morning" in q_lower or "morning" in q_lower:
        return "Good morning!"

    # Fallback to local machine clock
    hour = datetime.datetime.now().hour
    if 5 <= hour < 12:
        return "Good morning!"
    elif 12 <= hour < 17:
        return "Good afternoon!"
    else:
        return "Good evening!"


def _format_rag_answer(docs: list[dict], user_query: str) -> str:
    """Formats retrieved KB articles into a clean grounded response."""
    if not docs:
        return (
            "I searched our knowledge base but couldn't find a specific match for your query.\n\n"
            "**Recommended next steps:**\n"
            "- Call IT Support at **ext. 4000** (Mon-Fri 08:00-18:00 CET)\n"
            "- Or type **'create ticket'** and I'll raise a support request for you right away."
        )

    primary_doc = docs[0]
    title = primary_doc.get("title", "IT Support Guide")
    content = primary_doc.get("content", "").strip()

    related_titles = [d.get("title") for d in docs[1:3] if d.get("title") and d.get("title") != title]

    response_lines = [
        f"### 📋 {title}\n",
        f"{content}\n",
    ]

    if related_titles:
        response_lines.append("\n**Related guides:**")
        for rt in related_titles:
            response_lines.append(f"• {rt}")

    response_lines.append(
        "\n\n💡 *Still having trouble? Type **create ticket** to open a support request.*"
    )

    return "\n".join(response_lines)


def _valid_evidence(docs: list[dict]) -> list[dict]:
    """Remove empty and duplicate retrieval records before answer generation."""
    accepted = []
    seen = set()
    for doc in docs:
        title = str(doc.get("title", "")).strip()
        content = str(doc.get("content", "")).strip()
        identity = str(doc.get("id") or f"{title}:{content[:80]}")
        if not title or not content or identity in seen:
            continue
        seen.add(identity)
        accepted.append(doc)
    return accepted


@observe_node(name="knowledge_node")
async def knowledge_node(state: TicketState) -> dict:
    """Retrieves relevant KB articles and synthesises a grounded response."""
    logger.info("knowledge_node.start", user_id=state.get("user_id"))

    raw_query = state["messages"][-1].content if state.get("messages") else ""
    user_query = extract_message_text(raw_query)
    intent = state.get("intent", "it_question")
    q_lower = user_query.strip().lower()

    # 1. Guardrail Refusal
    if intent == "guardrail_refusal":
        if state.get("scope") == "unsafe":
            msg = (
                "🛡️ **I can’t help with that request.**\n\n"
                "I can assist with legitimate workplace IT support and cybersecurity incident "
                "reporting, but I can’t provide harmful instructions, bypass safeguards, or expose "
                "protected system information.\n\n"
                "If you are reporting a suspected security incident, describe what you observed "
                "and I’ll help you raise it with IT."
            )
            return {"retrieved_docs": [], "knowledge_answer": msg, "final_response": msg}
        msg = (
            "🛡️ **Out of Scope Request**\n\n"
            "I am Bobby, the AI Service Management Assistant at Inspired Pet Nutrition, dedicated strictly to **IT Systems and Technical Support**.\n\n"
            "I cannot assist with personal belongings, non-IT matters, or facility requests. However, I am ready to help you with:\n\n"
            "• 🔑 **Account & Access:** Password resets, MFA token resets & domain unlocks\n"
            "• 🌐 **Network & Connectivity:** Corporate VPN, Wi-Fi 802.1X & DNS issues\n"
            "• 💻 **Workplace Hardware:** Laptops, 4K monitors, docking stations & accessories\n"
            "• 📊 **Enterprise Software:** Microsoft 365, Teams, Outlook & Dynamics 365 ERP\n"
            "• 🎫 **ITSM Ticketing:** Raising, tracking, and resolving IT service requests\n\n"
            "👉 *Please rephrase your request with your specific IT or workplace technology issue.*"
        )
        return {"retrieved_docs": [], "knowledge_answer": msg, "final_response": msg}

    # 2. Clarification Needed
    if intent == "clarification_needed":
        msg = (
            "🤔 **Could you give me a bit more detail?**\n\n"
            "To find the right solution for you, can you describe what you're experiencing? For example:\n\n"
            "• *\"My VPN disconnects during Teams meetings\" *\n"
            "• *\"I can't reset my Windows password\" *\n"
            "• *\"My laptop won't connect to the office printer\" *\n"
            "• *\"I need a new software license for our team\" *\n\n"
            "Or type **create ticket** to log a request immediately."
        )
        return {"retrieved_docs": [], "knowledge_answer": msg, "final_response": msg}

    # 3. Dynamic Greetings
    is_greeting = q_lower in ("hi", "hello", "hey", "good morning", "good afternoon", "good evening", "hi bobby", "hello bobby", "hey bobby") or any(q_lower.startswith(g) for g in ("hi ", "hello ", "hey ", "good morning", "good afternoon", "good evening"))
    if is_greeting:
        time_g = _get_time_aware_greeting(user_query, state.get('user_time_greeting'))
        msg = (
            f"👋 **{time_g}** I'm **Bobby**, your IT Support Assistant at Inspired Pet Nutrition.\n\n"
            "I'm here 24/7 to help you stay productive. Here's what I can do:\n\n"
            "🎫 **Raise & track support tickets** for any IT issue\n"
            "🔑 **Account unlocks, password resets** & MFA support\n"
            "🌐 **VPN, Wi-Fi & connectivity** troubleshooting\n"
            "💻 **Hardware, software & Microsoft 365** help\n\n"
            "What can I help you with today?"
        )
        return {"retrieved_docs": [], "knowledge_answer": msg, "final_response": msg}

    # 4. Thank You / Appreciation
    if any(w in q_lower for w in ("thank", "thx", "thanks", "appreciate", "great help", "awesome", "perfect", "good job")):
        msg = (
            "You're very welcome! 😊 Happy to help anytime.\n\n"
            "If you run into any other IT issues or need further assistance, just drop a message here — I'm always available."
        )
        return {"retrieved_docs": [], "knowledge_answer": msg, "final_response": msg}

    # 5. Goodbye
    if q_lower in ("bye", "goodbye", "see you", "cya", "have a good day", "have a nice day"):
        msg = "Goodbye! 👋 Have a great rest of your day. Reach out whenever you need IT support!"
        return {"retrieved_docs": [], "knowledge_answer": msg, "final_response": msg}

    # 6. Capabilities / Help
    if "who are you" in q_lower or "what can you do" in q_lower or q_lower == "help":
        msg = (
            "🤖 **Hi, I'm Bobby — your IT Support Assistant at Inspired Pet Nutrition.**\n\n"
            "• **Instant IT guides:** VPN, Wi-Fi, Office 365, Teams, Printers, and more\n"
            "• **Ticket management:** Raise, track, update, and escalate support requests\n"
            "• **Account self-service:** Password resets, MFA setup, account unlocks\n"
            "• **Automated resolutions:** Standard requests handled and confirmed via email\n\n"
            "Just describe your issue and I'll help right away!"
        )
        return {"retrieved_docs": [], "knowledge_answer": msg, "final_response": msg}

    # 7. RAG Retrieval from IT Knowledge Base
    search_query = build_search_query(state, user_query)
    search_client = get_search_client()
    search_failed = False
    try:
        docs = await search_client.search(query=search_query, top_k=3)
        docs = _valid_evidence(docs)
        logger.info(
            "search.completed",
            provider=type(search_client).__name__,
            result_count=len(docs),
            top_score=docs[0].get("score") if docs else None,
            query_rewritten=search_query != user_query,
        )
    except Exception as e:
        logger.error("knowledge_node.search_error", error=str(e))
        docs = []
        search_failed = True

    # 8. Never ask the LLM to answer without retrieved evidence.
    if not docs:
        if search_failed:
            rag_answer = (
                "Our IT knowledge service is temporarily unavailable. "
                "Please try again shortly, or type **'create ticket'** for immediate assistance."
            )
        else:
            rag_answer = _format_rag_answer([], user_query)
        return {
            "retrieved_docs": [],
            "knowledge_answer": rag_answer,
            "final_response": rag_answer,
        }

    # 9. LLM Synthesis or Grounded Template
    api_key = settings.llm_api_key
    if api_key and api_key.strip() != "" and "TODO" not in api_key:
        try:
            from integrations.llm_client import get_llm
            llm = get_llm()
            context = "\n\n".join([
                f"[{doc.get('title', 'Guide')} | Source: {doc.get('source', 'IT Knowledge Base')}]\n{doc.get('content', '')}"
                for doc in docs
            ])
            response = await llm.ainvoke([
                SystemMessage(content=SYNTHESIS_PROMPT.format(context=context)),
                HumanMessage(content=user_query),
            ])
            return {
                "retrieved_docs": docs,
                "knowledge_answer": response.content,
                "final_response": response.content,
            }
        except Exception as e:
            logger.error("knowledge_node.llm_error", error=str(e))

    rag_answer = _format_rag_answer(docs, user_query)
    return {
        "retrieved_docs": docs,
        "knowledge_answer": rag_answer,
        "final_response": rag_answer,
    }


def route_after_knowledge(state: TicketState) -> str:
    if state.get("escalated"):
        return "escalation_node"
    return "response_node"
