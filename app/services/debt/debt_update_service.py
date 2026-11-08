from decimal import Decimal
from typing import Any, Dict, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.customer_model import Customer
from app.models.debt_model import Debt
from app.models.debt_payment_model import DebtPayment
from app.models.supplier_model import Supplier


class DebtUpdateMixin:
    @staticmethod
    def update_debt(
        debt_id: int,
        user_id: int,
        db: Session,
        customer_id: Optional[int] = None,
        supplier_id: Optional[int] = None,
        original_amount: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Sửa khoản nợ nhập tay:
        - Đổi đối tác: chỉ trong cùng chiều nợ (khách <-> khách, NCC <-> NCC).
        - Đổi số tiền gốc: chỉ khi chưa có lần thu / trả nào.
        Khoản nợ sinh từ giao dịch phải sửa ở giao dịch gốc (tránh lệch số liệu).
        """
        if customer_id is None and supplier_id is None and original_amount is None:
            raise HTTPException(status_code=400, detail="Không có thông tin nào để cập nhật")

        debt = db.query(Debt).filter(Debt.debt_id == debt_id, Debt.user_id == user_id).first()
        if not debt:
            raise HTTPException(status_code=404, detail="Không tìm thấy khoản nợ")
        if debt.transaction_id is not None:
            raise HTTPException(
                status_code=409,
                detail="Khoản nợ sinh từ giao dịch, vui lòng sửa ở giao dịch gốc",
            )

        is_receivable = debt.direction == "RECEIVABLE"
        if (is_receivable and supplier_id is not None) or (not is_receivable and customer_id is not None):
            raise HTTPException(status_code=400, detail="Không thể đổi sang loại đối tác khác chiều nợ")

        try:
            if is_receivable and customer_id is not None:
                owned = db.query(Customer.customer_id).filter(
                    Customer.customer_id == customer_id, Customer.user_id == user_id
                ).first()
                if not owned:
                    raise HTTPException(status_code=404, detail="Không tìm thấy khách hàng")
                debt.customer_id = customer_id

            if not is_receivable and supplier_id is not None:
                owned = db.query(Supplier.supplier_id).filter(
                    Supplier.supplier_id == supplier_id, Supplier.user_id == user_id
                ).first()
                if not owned:
                    raise HTTPException(status_code=404, detail="Không tìm thấy nhà cung cấp")
                debt.supplier_id = supplier_id

            if original_amount is not None:
                new_amount = Decimal(str(original_amount))
                if new_amount != Decimal(str(debt.original_amount or 0)):
                    has_payment = db.query(DebtPayment.payment_id).filter(DebtPayment.debt_id == debt_id).first()
                    if has_payment:
                        raise HTTPException(
                            status_code=409,
                            detail="Khoản nợ đã có thanh toán, không thể sửa số tiền. Hãy xóa và tạo lại",
                        )
                    debt.original_amount = new_amount
                    debt.remaining_debt = new_amount
                    debt.status = "UNPAID"

            db.commit()
        except Exception:
            db.rollback()
            raise

        return DebtUpdateMixin._detail(debt_id, user_id, db)

    @staticmethod
    def _detail(debt_id: int, user_id: int, db: Session) -> Dict[str, Any]:
        from app.services.debt_service import DebtService
        return DebtService.get_debt_detail(debt_id=debt_id, user_id=user_id, db=db)
