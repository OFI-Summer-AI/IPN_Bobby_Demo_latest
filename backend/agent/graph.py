"""
Bobby - Main LangGraph Graph Definition
=======================================
Wires all nodes together into the Bobby agent graph.
Uses Supabase PostgreSQL Checkpointer (AsyncPostgresSaver) with resilient connection health checks.
"""
from __future__ import annotations
import sys
import asyncio
import structlog
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from config.settings import settings
from agent.state import TicketState
from agent.nodes.triage import triage_node, route_after_triage
from agent.nodes.knowledge_node import knowledge_node, route_after_knowledge
from agent.nodes.ticket_node import ticket_node, route_after_ticket
from agent.nodes.account_node import account_node
from agent.nodes.hitl_node import hitl_node, execute_action_node, cancelled_node, route_after_hitl
from agent.nodes.escalation_node import escalation_node, response_node

logger = structlog.get_logger(__name__)

_pool = None
_checkpointer = None
_graph_instance = None


async def init_persistent_checkpointer():
    """Initializes the AsyncPostgresSaver checkpointer with resilient connection checking."""
    global _pool, _checkpointer, _graph_instance
    if _checkpointer is not None:
        return _checkpointer

    try:
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

        from psycopg_pool import AsyncConnectionPool
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        db_password = settings.supabase_db_password or "ofiservices2026"
        db_host = settings.supabase_db_host or "db.tlohofzcstxogebrhmdr.supabase.co"
        db_uri = f"postgresql://postgres:{db_password}@{db_host}:5432/postgres?sslmode=require"

        _pool = AsyncConnectionPool(
            conninfo=db_uri,
            min_size=1,
            max_size=5,
            max_idle=10.0,
            open=False,
            check=AsyncConnectionPool.check_connection,
            kwargs={"autocommit": True, "prepare_threshold": 0}
        )
        await asyncio.wait_for(_pool.open(), timeout=4.0)

        checkpointer = AsyncPostgresSaver(_pool)
        await asyncio.wait_for(checkpointer.setup(), timeout=4.0)
        _checkpointer = checkpointer
        logger.info("graph.async_postgres_checkpointer_ready", host=db_host)

        _graph_instance = build_bobby_graph(checkpointer=_checkpointer)
        return _checkpointer
    except Exception as e:
        logger.warning("graph.checkpointer_fallback_memory", error=str(e))
        if _pool is not None:
            try:
                await _pool.close(timeout=0.5)
            except Exception:
                pass
            _pool = None
        _checkpointer = MemorySaver()
        _graph_instance = build_bobby_graph(checkpointer=_checkpointer)
        return _checkpointer


async def close_persistent_checkpointer():
    """Closes the connection pool on application shutdown."""
    global _pool
    if _pool is not None:
        try:
            await _pool.close()
            logger.info("graph.postgres_pool_closed")
        except Exception as e:
            logger.error("graph.postgres_pool_close_error", error=str(e))


def build_bobby_graph(checkpointer=None):
    """Builds and compiles the Bobby LangGraph."""
    graph = StateGraph(TicketState)

    # 1. Register Nodes
    graph.add_node("triage_node",         triage_node)
    graph.add_node("knowledge_node",      knowledge_node)
    graph.add_node("ticket_node",         ticket_node)
    graph.add_node("account_node",        account_node)
    graph.add_node("hitl_node",           hitl_node)
    graph.add_node("execute_action_node", execute_action_node)
    graph.add_node("cancelled_node",      cancelled_node)
    graph.add_node("escalation_node",     escalation_node)
    graph.add_node("response_node",       response_node)

    # 2. Entry Point
    graph.add_edge(START, "triage_node")

    # 3. Conditional Routing After Triage
    graph.add_conditional_edges(
        "triage_node",
        route_after_triage,
        {
            "knowledge_node":   "knowledge_node",
            "ticket_node":      "ticket_node",
            "account_node":     "account_node",
            "escalation_node":  "escalation_node",
        }
    )

    # 4. After Knowledge Retrieval
    graph.add_conditional_edges(
        "knowledge_node",
        route_after_knowledge,
        {
            "response_node":   "response_node",
            "escalation_node": "escalation_node",
        }
    )

    # 5. After Ticket Node
    graph.add_conditional_edges(
        "ticket_node",
        route_after_ticket,
        {
            "hitl_node":       "hitl_node",
            "escalation_node": "escalation_node",
            "response_node":   "response_node",
        }
    )

    # 6. Account Node -> HITL
    graph.add_edge("account_node", "hitl_node")

    # 7. After HITL Decision
    graph.add_conditional_edges(
        "hitl_node",
        route_after_hitl,
        {
            "execute_action_node": "execute_action_node",
            "cancelled_node":      "cancelled_node",
        }
    )

    # 8. After Execution / Cancellation -> Response
    graph.add_edge("execute_action_node", "response_node")
    graph.add_edge("cancelled_node",      "response_node")
    graph.add_edge("escalation_node",     "response_node")

    # 9. End
    graph.add_edge("response_node", END)

    if checkpointer is None:
        checkpointer = MemorySaver()

    return graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["hitl_node"],
    )


def get_bobby_graph():
    """Returns the compiled Bobby graph."""
    global _graph_instance
    if _graph_instance is None:
        _graph_instance = build_bobby_graph()
    return _graph_instance
