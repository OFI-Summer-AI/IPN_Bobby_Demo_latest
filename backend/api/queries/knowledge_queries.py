"""Bobby — CQRS Queries: Knowledge Base Search"""
from __future__ import annotations
from fastapi import APIRouter, Depends, Query
from integrations.search_client import get_search_client
from middleware.auth import get_current_user

router = APIRouter(prefix="/queries")


@router.get("/knowledge/search")
async def search_knowledge(
    q: str = Query(..., description="Search query"),
    top_k: int = Query(5, ge=1, le=20),
    current_user: dict = Depends(get_current_user),
):
    """Search the knowledge base — bypasses LangGraph, direct vector search."""
    search = get_search_client()
    results = await search.search(query=q, top_k=top_k)
    return {"results": results, "query": q, "count": len(results)}
