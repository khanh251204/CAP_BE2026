import asyncio
from typing import Any

from app.ai.core.router import IntentRouter
from app.ai.core.state import pending_confirmations


CONFIRM_WORDS = {
    "có",
    "ok",
    "okay",
    "đồng ý",
    "được",
    "ừ",
    "uh",
    "yes"
}


class Agent:
    """
    AI Agent Orchestrator.
    Chịu trách nhiệm orchestration:
    Input -> LLM Analysis -> Intent -> Router -> Intent Handler -> Result.
    Tuyệt đối không chứa business logic cụ thể của từng intent.
    """

    def __init__(
        self,
        llm: Any,
        rag: Any = None,
        router: Any = None
    ):
        self.llm = llm
        self.rag = rag
        self.router = router or IntentRouter()

    async def run(
        self,
        user_id: int,
        text: str
    ) -> dict:
        # 1. Kiểm tra xác nhận nếu có pending confirmation
        normalized_text = text.strip().lower()
        if normalized_text in CONFIRM_WORDS:
            pending = pending_confirmations.get(user_id)
            if pending:
                return {
                    "success": True,
                    "user_id": user_id,
                    "intent": pending["intent"],
                    "status": "confirmed",
                    "payload": pending["payload"]
                }

        # 2. RAG Context (nếu có)
        knowledge = ""
        if self.rag:
            knowledge = await asyncio.to_thread(
                self.rag.build_context,
                text,
                3
            )

        # 3. LLM Analysis
        analysis = await asyncio.to_thread(
            self.llm.analyze_transaction,
            text
        )

        # 4. Kiểm tra format kết quả phân tích
        if not isinstance(analysis, dict):
            return {
                "success": False,
                "message": "LLM trả về không hợp lệ"
            }

        intent = analysis.get("intent")
        entities = analysis.get("entities", {}) or {}

        # 5. LLM Error
        if analysis.get("status") == "error":
            return {
                "success": False,
                "user_id": user_id,
                "intent": intent,
                "analysis": analysis
            }

        # 6. Intent Khác / Không xác định
        if intent == "khac":
            return {
                "success": False,
                "user_id": user_id,
                "intent": intent,
                "analysis": analysis,
                "message": "Không xác định được nghiệp vụ"
            }

        # 7. Router điều phối sang Intent Handler
        handler_result = await self.router.route(
            intent=intent,
            user_id=user_id,
            entities=entities,
            text=text
        )

        # 8. Lưu pending confirmation nếu handler trả về waiting_confirmation
        if handler_result.get("status") == "waiting_confirmation":
            pending_confirmations[user_id] = {
                "intent": intent,
                "payload": handler_result["payload"]
            }

        # 9. Return
        return {
            "success": True,
            "user_id": user_id,
            "intent": intent,
            "analysis": analysis,
            "mcp_result": handler_result
        }
