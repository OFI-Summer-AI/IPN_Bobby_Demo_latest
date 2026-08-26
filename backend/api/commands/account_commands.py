"""Bobby — Account Commands (stub for demo)"""
from __future__ import annotations
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from middleware.auth import get_current_user

router = APIRouter(prefix="/commands")


class AccountActionRequest(BaseModel):
    session_id: str
    action: str   # "unlock" | "password_reset"


@router.post("/account/action")
async def account_action(
    request: AccountActionRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Handles account management requests through Bobby graph.
    Graph API integration stubbed for demo.
    """
    from langchain_core.messages import HumanMessage
    from agent.graph import get_bobby_graph

    graph = get_bobby_graph()
    config = {"configurable": {"thread_id": request.session_id}}

    message_map = {
        "unlock": "My account is locked and I cannot log in. Please unlock it.",
        "password_reset": "I need to reset my password.",
    }
    message = message_map.get(request.action, "I need help with my account.")

    result = await graph.ainvoke(
        {
            "messages": [HumanMessage(content=message)],
            "user_id": current_user["user_id"],
            "user_name": current_user["name"],
            "user_role": current_user["role"],
            "session_id": request.session_id,
            "escalated": False,
            "needs_human_approval": False,
            "human_approved": None,
            "error": None,
        },
        config=config,
    )

    state_snapshot = await graph.aget_state(config)
    response = {
        "session_id": request.session_id,
        "message": result.get("final_response", ""),
    }
    if state_snapshot.next and "hitl_node" in state_snapshot.next:
        pending = result.get("pending_action", {})
        response["requires_approval"] = True
        response["pending_action"] = pending
        response["message"] = pending.get("message", "")

    return response
