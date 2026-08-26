"""
Bobby — Knowledge Base LangChain Tools
=========================================
LangChain @tool-decorated functions for knowledge retrieval.
The Bobby agent uses these tools to search the KB before answering
IT questions.
"""
from __future__ import annotations
from langchain_core.tools import tool
from integrations.search_client import get_search_client


@tool
async def search_knowledge_base_tool(query: str, top_k: int = 5) -> list[dict]:
    """
    Searches the IT knowledge base for relevant articles.
    Use this when the user asks an IT question like 'how do I...' or 'what is...'.

    Args:
        query: The user's question or search terms
        top_k: Number of results to return (default 5, max 10)

    Returns:
        List of dicts with 'title', 'content', 'source' fields
    """
    client = get_search_client()
    results = await client.search(query=query, top_k=min(top_k, 10))
    return results
