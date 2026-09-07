from mcp.server.fastmcp import FastMCP
from sqlalchemy.orm import Session

from app.configs.database import get_db_session
from app.controllers.debt_controller import DebtController
from app.ai.mcp.debt.tools import (
    GhiNoKhachHangInput,
    GhiNoKhachHangOutput,
    ThuNoKhachHangInput,
    ThuNoKhachHangOutput,
    GhiNoNhaCungCapInput,
    GhiNoNhaCungCapOutput,
    ThuNoNhaCungCapInput,
    ThuNoNhaCungCapOutput,
)

mcp = FastMCP("debt")
server = mcp  # alias for client.py MCP_SERVERS consistency


@mcp.tool()
def ghi_no_khach_hang(input: GhiNoKhachHangInput, user_id: int) -> GhiNoKhachHangOutput:
    """
    Ghi nhận khoản nợ phải thu (receivable) mới cho một khách hàng.
    Dùng khi khách mua hàng nhưng chưa trả đủ tiền.
    """
    db: Session = get_db_session()
    try:
        result = DebtController.create_customer_debt(
            db=db,
            user_id=user_id,
            customer_id=input.customer_id,
            total_debt=input.original_amount,
            transaction_id=input.transaction_id,
        )
        return GhiNoKhachHangOutput(**result)
    finally:
        db.close()


@mcp.tool()
def thu_no_khach_hang(input: ThuNoKhachHangInput, user_id: int) -> ThuNoKhachHangOutput:
    """
    Ghi nhận việc thu tiền từ khách hàng đang có nợ.
    - Nếu input.debt_id có giá trị: thu đích danh 1 khoản nợ.
    - Nếu input.customer_id có giá trị: thu tổng, tự động phân bổ FIFO
      qua các khoản nợ đang mở của khách hàng đó (khoản cũ nhất trả trước).
    """
    db: Session = get_db_session()
    try:
        result = DebtController.collect_customer_debt(
            db=db,
            user_id=user_id,
            account_id=input.account_id,
            amount=input.amount,
            debt_id=input.debt_id,
            customer_id=input.customer_id,
        )
        return ThuNoKhachHangOutput(**result)
    finally:
        db.close()


@mcp.tool()
def ghi_no_nha_cung_cap(input: GhiNoNhaCungCapInput, user_id: int) -> GhiNoNhaCungCapOutput:
    """
    Ghi nhận khoản nợ phải trả (payable) mới cho nhà cung cấp.
    Dùng khi nhập hàng nhưng chưa trả đủ tiền.
    """
    db: Session = get_db_session()
    try:
        result = DebtController.create_supplier_debt(
            db=db,
            user_id=user_id,
            supplier_id=input.supplier_id,
            total_debt=input.original_amount,
            transaction_id=input.transaction_id,
            note=input.note,
        )
        return GhiNoNhaCungCapOutput(**result)
    finally:
        db.close()


@mcp.tool()
def thu_no_nha_cung_cap(input: ThuNoNhaCungCapInput, user_id: int) -> ThuNoNhaCungCapOutput:
    """
    Ghi nhận việc trả tiền nợ cho nhà cung cấp đang có nợ phải trả (PAYABLE).
    - Nếu input.debt_id có giá trị: trả đích danh 1 khoản nợ.
    - Nếu input.supplier_id có giá trị: trả tổng, tự động phân bổ FIFO
      qua các khoản nợ đang mở của nhà cung cấp đó (khoản cũ nhất trả trước).
    """
    db: Session = get_db_session()
    try:
        result = DebtController.pay_supplier_debt(
            db=db,
            user_id=user_id,
            account_id=input.account_id,
            amount=input.amount,
            debt_id=input.debt_id,
            supplier_id=input.supplier_id,
            note=input.note,
        )
        return ThuNoNhaCungCapOutput(**result)
    finally:
        db.close()



if __name__ == "__main__":
    server.run(
        transport="streamable-http"
    )
