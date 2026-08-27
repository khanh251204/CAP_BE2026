from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.ai.agent.agent import Agent
from app.ai.agent.agent_state import AgentContext
from app.configs.database import get_db
from app.configs.jwt import get_current_user_id


router = APIRouter()


# ============================================================
# AGENT
# ============================================================

agent = Agent()


# ============================================================
# AGENT CONTEXT
# ============================================================

# Tạm thời lưu context theo user
agent_contexts: dict[int, AgentContext] = {}


# ============================================================
# REQUEST SCHEMA
# ============================================================

class AgentChatRequest(BaseModel):
    text: str


# ============================================================
# CHAT
# ============================================================

@router.post("/chat")
async def agent_chat(
    request: AgentChatRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    # ========================================================
    # Validate text
    # ========================================================

    if not request.text.strip():
        return {
            "success": False,
            "status": "error",
            "message": "Nội dung không được để trống."
        }

    # ========================================================
    # Get / Create context
    # ========================================================

    if user_id not in agent_contexts:
        agent_contexts[user_id] = AgentContext()

    context = agent_contexts[user_id]

    # ========================================================
    # Run Agent
    # ========================================================

    result = await agent.run(
        text=request.text,
        user_id=user_id,
        db=db,
        context=context
    )

    return result