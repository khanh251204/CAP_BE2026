import asyncio
import importlib
import inspect
from typing import Any, Optional

from app.ai.core.router import IntentRouter
from app.services.ai_feature_service import UserAIConfig, get_user_ai_config, locked_intent_message
from app.ai.intents.missing_info import (
    clean_entities_for_intent,
    drop_unspoken_quantity,
    fill_missing_amount,
    missing_message,
    restore_negative_numbers,
)
from app.ai.core.multi_item import build_multi_item_draft, resolve_multi_intent
from app.services.session_store_service import SessionStoreService
from app.services.sales_policy import (
    resolve_amount_paid,
    resolve_credit_sale_intent,
    resolve_payment,
    resolve_total_price,
)

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

    def _missing_info(self, intent: str, entities: dict, analysis: dict) -> Optional[tuple[list, str]]:
        """
        LLM báo thiếu thông tin → kiểm tra lại bằng validator của intent (backend quyết định).
        - Validator báo thiếu → (missing_fields, câu nhắc tiếng Việt có ví dụ).
        - Validator thấy đủ → None: chuyển tiếp cho handler kiểm tra tiếp (vd: số tiền nợ),
          handler có câu nhắc cụ thể hơn.
        Không bao giờ trả nguyên câu LLM tự viết (có thể là tiếng Anh: "Missing required field: price").
        """
        llm_missing = analysis.get("missing_fields") or []
        handler = self.router.get_handler(intent)
        try:
            module = importlib.import_module(type(handler).__module__.rsplit(".", 1)[0] + ".validator")
            val = module.validate(resolve_total_price(intent, entities))
        except Exception:
            return llm_missing, missing_message(llm_missing)
        if isinstance(val, dict) and not val.get("success"):
            missing = val.get("missing_fields") or llm_missing
            return missing, val.get("message") or missing_message(missing)
        return None

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

        # 1b. Kiểm tra gói tính năng AI của tài khoản (cache RAM 30s)
        ai_config = get_user_ai_config(user_id)
        if ai_config.is_ai_locked:
            # Khóa toàn bộ AI (0 intent) -> chặn ngay, KHÔNG gọi LLM (0 token, < 1ms)
            return {
                "success": False,
                "status": "feature_locked",
                "code": "AI_FEATURE_LOCKED",
                "user_id": user_id,
                "intent": "khac",
                "message": "Tài khoản chưa được kích hoạt chức năng trợ lý AI. Vui lòng nâng cấp gói hoặc liên hệ quản trị viên.",
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

        # 3. LLM Analysis (truyền system_prompt rút gọn theo gói của user nếu có giới hạn)
        pruned_prompt = ai_config.build_system_prompt()
        if pruned_prompt is not None and "system_prompt" in inspect.signature(self.llm.analyze_transaction).parameters:
            analysis = await asyncio.to_thread(
                self.llm.analyze_transaction,
                input_to_model,
                knowledge,
                pruned_prompt,
            )
        else:
            analysis = await asyncio.to_thread(
                self.llm.analyze_transaction,
                input_to_model,
                knowledge
            )

        return await self._handle_analysis(user_id, text, input_to_model, analysis, ai_config=ai_config)

    async def run_structured(
        self,
        user_id: int,
        intent: str,
        entities: dict,
        text: str = "",
    ) -> dict:
        """
        Nhập bằng biểu mẫu (không qua LLM): app gửi sẵn intent + entities đã chọn.
        Đi qua đúng các bước sau LLM (chuẩn hóa, validator, handler, lưu bản nháp)
        nên kết quả cùng dạng với `run` và dùng chung màn Xác nhận.
        """
        analysis = {
            "intent": intent,
            "entities": dict(entities or {}),
            "status": "success",
            "original_text": text,
            "input_source": "FORM",
        }
        return await self._handle_analysis(
            user_id, text, text, analysis, structured=True, ai_config=get_user_ai_config(user_id)
        )

    async def _handle_analysis(
        self,
        user_id: int,
        text: str,
        input_to_model: str,
        analysis: Any,
        structured: bool = False,
        ai_config: Optional[UserAIConfig] = None,
    ) -> dict:
        # structured=True: dữ liệu từ biểu mẫu là chính xác, không cần các bước "sửa lỗi LLM" dựa trên câu chữ
        cfg = ai_config or get_user_ai_config(user_id)
        # 4. Kiểm tra format kết quả phân tích
        if not isinstance(analysis, dict):
            return {
                "success": False,
                "message": "LLM trả về không hợp lệ"
            }

        intent = analysis.get("intent")
        entities = analysis.get("entities", {}) or {}
        # LLM hay bỏ dấu âm ("chi tiền điện -1000000" -> 1000000): gắn lại để validator báo "phải lớn hơn 0"
        signed = entities if structured else restore_negative_numbers(entities, input_to_model)
        if signed != entities:
            entities = signed
            analysis = {**analysis, "entities": entities}
        # LLM bỏ trống số tiền ở nghiệp vụ chỉ có tiền (thu / trả / ghi nợ, chi phí): lấy số duy nhất trong câu.
        # Chạy trước bước 5 để không hỏi lại số tiền người dùng đã nói. Số âm giữ nguyên dấu để handler cảnh báo.
        filled = entities if structured else fill_missing_amount(intent, entities, input_to_model)
        if filled != entities:
            entities = filled
            analysis = {**analysis, "entities": entities}

        # 4b. Nhiều sản phẩm trong một câu ("bán 2 coca và 3 mì"): backend tự kiểm tra từng dòng,
        # không dựa vào status/missing_fields của LLM (top-level product / quantity để trống).
        multi_intent = resolve_multi_intent(intent, entities)
        if multi_intent:
            if not cfg.is_intent_allowed(multi_intent):
                return {
                    "success": False,
                    "status": "feature_locked",
                    "code": "INTENT_NOT_ALLOWED",
                    "user_id": user_id,
                    "intent": multi_intent,
                    "analysis": analysis,
                    "message": locked_intent_message(multi_intent, cfg.plan_code),
                }
            if not cfg.allow_multi_item:
                return {
                    "success": False,
                    "status": "feature_locked",
                    "code": "MULTI_ITEM_LOCKED",
                    "user_id": user_id,
                    "intent": multi_intent,
                    "analysis": analysis,
                    "message": "Gói hiện tại chưa hỗ trợ ghi nhiều sản phẩm trong một câu. Vui lòng nói từng sản phẩm một hoặc nâng cấp gói.",
                }
            intent = multi_intent
            analysis = {**analysis, "intent": intent, "llm_intent": analysis.get("intent")}
            # Tiền đã trả là của cả đơn ("bán 2 coca và 3 mì 80k, khách trả 50k")
            if not structured:
                entities = resolve_amount_paid(intent, entities, input_to_model)
            handler_result = await build_multi_item_draft(self.router, intent, user_id, entities, input_to_model)
            # Cùng dạng kết quả với handler một sản phẩm (bước 9) để app xử lý giống nhau
            if handler_result.get("status") == "waiting_confirmation":
                SessionStoreService.save_confirmation(
                    session_key=user_id,
                    data={"intent": intent, "payload": handler_result["payload"]},
                    user_id=user_id,
                )
            return {
                "success": True,
                "user_id": user_id,
                "intent": intent,
                "analysis": analysis,
                "mcp_result": handler_result,
            }

        # 4c. Chặn sớm nếu LLM trả về intent nằm ngoài gói được phép của tài khoản
        if intent and intent != "khac" and self.router.get_handler(intent) and not cfg.is_intent_allowed(intent):
            return {
                "success": False,
                "status": "feature_locked",
                "code": "INTENT_NOT_ALLOWED",
                "user_id": user_id,
                "intent": intent,
                "analysis": analysis,
                "message": locked_intent_message(intent, cfg.plan_code),
            }

        # 5. LLM Error (thiếu field) — intent lạ được xử lý ở bước 6
        missing_info = (
            self._missing_info(intent, entities, analysis)
            if analysis.get("status") == "error" and self.router.get_handler(intent)
            else None
        )
        if missing_info:
            missing_fields, message = missing_info
            return {
                "success": False,
                "status": "need_information",
                "user_id": user_id,
                "intent": intent,
                "missing_fields": missing_fields,
                "message": message,
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
        # LLM tự đoán quantity (vd "Bán lốc sữa chua 50000" -> 1): bỏ đi để validator hỏi lại số lượng.
        # Phải chạy trước resolve_total_price, nếu không đơn giá bị tính từ số lượng đoán.
        guessed_qty = entities.get("quantity")
        if not structured:
            entities = drop_unspoken_quantity(intent, entities, input_to_model)
        entities = clean_entities_for_intent(intent, entities, input_to_model)
        # Câu có "chưa trả tiền", "ghi nợ", "bán chịu"... -> bán / nhập NỢ (payment = PENDING), dù LLM bỏ sót.
        # Nhập bằng biểu mẫu giữ nguyên lựa chọn thanh toán của người dùng.
        if not structured and intent in ("ban_hang", "mua_hang", "nhap_hang"):
            entities = {**entities, "payment": resolve_payment(entities.get("payment"), input_to_model)}
        # "mới trả 20k", "đưa trước 200k còn lại ghi nợ", "trả một nửa" -> số tiền / tỉ lệ đã trả (phần còn lại ghi nợ)
        if not structured:
            entities = resolve_amount_paid(intent, entities, input_to_model)
        entities = resolve_total_price(intent, entities)
        llm_payment = (analysis.get("entities") or {}).get("payment")
        paid_found = entities.get("amount_paid") is not None or entities.get("amount_paid_ratio") is not None
        if (
            intent != llm_intent or entities.get("quantity") != guessed_qty
            or entities.get("payment") != llm_payment or paid_found
        ):
            analysis = {**analysis, "intent": intent, "entities": entities, "llm_intent": llm_intent}

        # 6c. Kiểm tra lại sau khi resolve_credit_sale_intent (tránh chuyển sang intent ngoài gói)
        if intent != llm_intent and not cfg.is_intent_allowed(intent):
            return {
                "success": False,
                "status": "feature_locked",
                "code": "INTENT_NOT_ALLOWED",
                "user_id": user_id,
                "intent": intent,
                "analysis": analysis,
                "message": locked_intent_message(intent, cfg.plan_code),
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
