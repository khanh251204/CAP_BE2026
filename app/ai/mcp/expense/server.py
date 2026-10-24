from typing import Optional, Dict, Any
# pyrefly: ignore [missing-import]
from mcp.server.fastmcp import FastMCP
from sqlalchemy.orm import Session
from datetime import datetime

from app.configs.database import get_db_session
from app.controllers.expense_controller import ExpenseController
from app.ai.mcp.expense.tools import CreateExpenseInput, CreateExpenseOutput

mcp = FastMCP("expense")


def _normalize_payment_status(raw: Any) -> str:
    """
    App/AI có thể gửi phương thức ('cash', 'transfer', 'debt', 'Tiền mặt'...) thay vì trạng thái.
    Ghi nợ / chưa trả → PENDING; trả một phần → PARTIAL; còn lại → PAID.
    """
    v = str(raw or "").strip().lower()
    if v in ("pending", "unpaid", "debt") or "nợ" in v or "chưa" in v:
        return "PENDING"
    if v == "partial" or "một phần" in v:
        return "PARTIAL"
    return "PAID"


def _parse_date(raw: Any) -> Optional[datetime]:
    """Nhận 'YYYY-MM-DD', ISO datetime hoặc 'DD/MM/YYYY'. Sai định dạng → None (dùng hôm nay)."""
    if not raw:
        return None
    if isinstance(raw, datetime):
        return raw
    s = str(raw).strip()
    for fmt in ("%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None
server = mcp  # alias for client.py MCP_SERVERS consistency


@mcp.tool()
def create_expense(
    user_id: int,
    payload: Optional[Dict[str, Any]] = None,
    input: Optional[CreateExpenseInput] = None,
    amount: Optional[float] = None,
    category_name: Optional[str] = None,
    category_id: Optional[int] = None,
    account_id: Optional[int] = None,
    note: Optional[str] = None,
    payment_status: Optional[str] = "PAID",
    date: Optional[str] = None,
    input_text: Optional[str] = None
) -> Dict[str, Any]:
    """
    Ghi nhận chi phí hoạt động vào sổ quỹ (Transaction & Category & Account).
    """
    # 1. Trích xuất tham số linh hoạt từ payload, input hoặc trực tiếp
    p_data = {}
    if payload and isinstance(payload, dict):
        p_data = payload
    elif input and isinstance(input, CreateExpenseInput):
        p_data = input.model_dump()

    amt = p_data.get("amount") or p_data.get("price") or amount
    if amt is None:
        raise ValueError("Số tiền chi phí (amount/price) không được để trống")
    try:
        amt = float(amt)
    except (ValueError, TypeError):
        raise ValueError(f"Số tiền '{amt}' không hợp lệ")

    cat_name = p_data.get("category_name") or p_data.get("category") or category_name
    cat_id = p_data.get("category_id") or category_id
    acc_id = p_data.get("account_id") or account_id
    note_text = p_data.get("note") or p_data.get("description") or note or cat_name
    pay_status = _normalize_payment_status(
        p_data.get("payment_status") or p_data.get("payment") or payment_status
    )
    in_text = p_data.get("input_text") or input_text
    raw_date = p_data.get("date") or date

    tx_date = _parse_date(raw_date)

    raw_method = p_data.get("input_method") or "MANUAL"
    input_method = "VOICE" if str(raw_method).upper() == "VOICE" else "MANUAL"

    db: Session = get_db_session()
    try:
        result = ExpenseController.create_expense(
            db=db,
            user_id=user_id,
            amount=amt,
            category_name=cat_name,
            category_id=cat_id,
            account_id=acc_id,
            note=note_text,
            payment_status=pay_status,
            transaction_date=tx_date,
            input_text=in_text,
            input_method=input_method
        )
        return result
    finally:
        db.close()
