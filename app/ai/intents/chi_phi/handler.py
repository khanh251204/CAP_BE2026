from typing import Any

from app.configs.database import get_db_session
from app.services.expense_service import ExpenseService
from .validator import validate
from .payload import build_payload


def _attach_category(user_id: int, payload: dict) -> None:
    """
    Khớp khoản chi với danh mục chi thật của user (chỉ đọc, không tạo mới) và gửi kèm
    danh sách danh mục để giao diện cho chọn lại.
    """
    db = get_db_session()
    try:
        spoken = payload.get("category_name")
        matched = ExpenseService.match_category(db, user_id, category_name=spoken)
        payload["category_options"] = [
            {"category_id": c.category_id, "category_name": c.category_name.strip()}
            for c in ExpenseService.list_expense_categories(db, user_id)
        ]
    finally:
        db.close()
    if matched:
        payload["category_id"] = matched.category_id
        payload["category_name"] = matched.category_name.strip()
        payload["category"] = payload["category_name"]
        # Ghi chú giữ lời người dùng nói ("Tiền internet"); không nói khoản chi thì lấy tên danh mục
        if payload.get("note") in (None, "", "Chi phí"):
            payload["note"] = payload["category_name"]


class ChiPhiHandler:
    """
    Business workflow cho intent: chi_phi
    Xử lý:
    - Validate bắt buộc có trường 'price' (số tiền chi phí).
    - Gọi MCP create_expense.
    - Trả về kết quả ghi nhận chi phí.
    """

    async def handle(
        self,
        user_id: int,
        entities: dict[str, Any],
        text: str,
        intent: str = "chi_phi"
    ) -> dict:
        val_result = validate(entities)
        if not val_result["success"]:
            return {
                "success": False,
                "status": val_result.get("status", "need_information"),
                "intent": intent,
                "missing_fields": val_result["missing_fields"],
                "message": val_result["message"]
            }

        payload = build_payload(entities=entities, text=text)
        _attach_category(user_id, payload)
        cat_label = payload.get("category_name") or "Khác"
        amt = payload.get("amount", 0.0)

        return {
            "success": True,
            "status": "waiting_confirmation",
            "intent": intent,
            "action": "create_expense",
            "payload": payload,
            "message": f"Bạn có chắc muốn ghi nhận chi phí '{cat_label}' với số tiền {amt:,.0f}đ không?"
        }
