from typing import Optional, Dict, Any
from mcp.server.fastmcp import FastMCP
from sqlalchemy.orm import Session
from datetime import datetime

from app.configs.database import get_db_session
from app.controllers.expense_controller import ExpenseController
from app.ai.mcp.expense.tools import CreateExpenseInput, CreateExpenseOutput

mcp = FastMCP("expense")
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
    pay_status = p_data.get("payment_status") or p_data.get("payment") or payment_status or "PAID"
    in_text = p_data.get("input_text") or input_text
    raw_date = p_data.get("date") or date

    tx_date = None
    if raw_date:
        try:
            if isinstance(raw_date, str):
                tx_date = datetime.fromisoformat(raw_date)
        except Exception:
            tx_date = None

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
            input_text=in_text
        )
        return result
    finally:
        db.close()
