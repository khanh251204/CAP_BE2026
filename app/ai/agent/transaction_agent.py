# app/ai/agent/transaction_agent.py

import asyncio

from app.ai.llm.groq_service import GroqService
from app.ai.agent.agent_router import AgentRouter
from app.ai.agent.state import pending_confirmations


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


class TransactionAgent:

    def __init__(
        self,
        llm: GroqService,
        rag=None
    ):
        self.llm = llm
        self.rag = rag

    async def run(
        self,
        user_id: int,
        text: str
    ):

        # ====================================================
        # 1. KIỂM TRA XÁC NHẬN
        # ====================================================

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

        # ====================================================
        # 2. RAG
        # ====================================================

        knowledge = ""

        if self.rag:

            knowledge = await asyncio.to_thread(
                self.rag.build_context,
                text,
                3
            )

        # ====================================================
        # 3. LLM
        # ====================================================

        analysis = await asyncio.to_thread(
            self.llm.analyze_transaction,
            text
        )

        # ====================================================
        # 4. VALIDATE
        # ====================================================

        if not isinstance(analysis, dict):

            return {
                "success": False,
                "message": "LLM trả về không hợp lệ"
            }

        intent = analysis.get("intent")

        entities = analysis.get(
            "entities",
            {}
        ) or {}

        # ====================================================
        # 5. LLM ERROR
        # ====================================================

        if analysis.get("status") == "error":

            return {
                "success": False,
                "user_id": user_id,
                "intent": intent,
                "analysis": analysis
            }

        # ====================================================
        # 6. INTENT KHÁC
        # ====================================================

        if intent == "khac":

            return {
                "success": False,
                "user_id": user_id,
                "intent": intent,
                "analysis": analysis,
                "message": "Không xác định được nghiệp vụ"
            }

        # ====================================================
        # 7. AGENT ROUTER
        # ====================================================

        router_result = await AgentRouter.execute(
            intent=intent,
            user_id=user_id,
            entities=entities,
            text=text
        )

        # ====================================================
        # 8. LƯU PENDING CONFIRMATION
        # ====================================================

        if (
            router_result.get("status")
            == "waiting_confirmation"
        ):

            pending_confirmations[user_id] = {
                "intent": intent,
                "payload": router_result["payload"]
            }

        # ====================================================
        # 9. RETURN
        # ====================================================

        return {
            "success": True,
            "user_id": user_id,
            "intent": intent,
            "analysis": analysis,
            "mcp_result": router_result
        }