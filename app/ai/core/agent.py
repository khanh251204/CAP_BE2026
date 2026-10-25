import asyncio
from typing import Any

from app.ai.core.router import IntentRouter
from app.services.session_store_service import SessionStoreService
from app.services.sales_policy import resolve_credit_sale_intent, resolve_total_price

UNKNOWN_INTENT_MESSAGE = (
    "Mình chưa hiểu bạn muốn ghi nghiệp vụ gì. Bạn nói rõ hơn giúp mình, ví dụ: "
    "\"bán 5 lon coca\", \"nhập 10 thùng bia giá 200k\", \"khách An trả nợ 500k tiền mặt\", "
    "\"chi tiền điện 500k\"."
)


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
            pending = SessionStoreService.get_confirmation(user_id)
            if pending:
                return {
                    "success": True,
                    "user_id": user_id,
                    "intent": pending["intent"],
                    "status": "confirmed",
                    "payload": pending["payload"]
                }

        # 2. Normalization RAG (Kiến trúc mới nhất)
        knowledge = ""
        input_to_model = text
        
        if self.rag:
            try:
                # Chuẩn hóa regex thay vì dùng nhúng vector chậm chạp
                normalized_text, _ = await asyncio.to_thread(
                    self.rag.normalize,
                    text
                )
                input_to_model = normalized_text
            except AttributeError:
                # Dự phòng nếu self.rag là phiên bản quá cũ chưa có hàm normalize
                pass

        # 3. LLM Analysis
        analysis = await asyncio.to_thread(
            self.llm.analyze_transaction,
            input_to_model,
            knowledge
        )

        # 4. Kiểm tra format kết quả phân tích
        if not isinstance(analysis, dict):
            return {
                "success": False,
                "message": "LLM trả về không hợp lệ"
            }

        intent = analysis.get("intent")
        entities = analysis.get("entities", {}) or {}

        # 5. LLM Error (thiếu field) — intent lạ được xử lý ở bước 6
        if analysis.get("status") == "error" and self.router.get_handler(intent):
            return {
                "success": False,
                "user_id": user_id,
                "intent": intent,
                "analysis": analysis
            }

        # 6. Intent Khác / Không xác định / LLM tự đặt ra intent không tồn tại
        if intent == "khac" or not self.router.get_handler(intent):
            if intent != "khac":
                analysis = {**analysis, "intent": "khac", "llm_intent": intent}
            return {
                "success": False,
                "status": "unknown_intent",
                "user_id": user_id,
                "intent": "khac",
                "analysis": analysis,
                "message": UNKNOWN_INTENT_MESSAGE
            }

        # 6b. Bán nợ có hàng (product + quantity) luôn đi qua ban_hang để trừ kho,
        # kể cả khi LLM phân loại là khach_ghi_no
        llm_intent = intent
        intent, entities = resolve_credit_sale_intent(intent, entities)
        entities = resolve_total_price(intent, entities)
        if intent != llm_intent:
            analysis = {**analysis, "intent": intent, "entities": entities, "llm_intent": llm_intent}

        # 7. Router điều phối sang Intent Handler
        handler_result = await self.router.route(
            intent=intent,
            user_id=user_id,
            entities=entities,
            text=text
        )

        # 8. Lưu pending confirmation nếu handler trả về waiting_confirmation
        if handler_result.get("status") == "waiting_confirmation":
            SessionStoreService.save_confirmation(
                session_key=user_id,
                data={
                    "intent": intent,
                    "payload": handler_result["payload"]
                },
                user_id=user_id
            )

        # 9. Return
        return {
            "success": True,
            "user_id": user_id,
            "intent": intent,
            "analysis": analysis,
            "mcp_result": handler_result
        }
