from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.transaction_model import Transaction
from app.models.debt_model import Debt
from app.models.debt_payment_model import DebtPayment
from app.repositories.debt_repository import DebtRepository
from app.services.debt.debt_helper import _get_intent_id


class SupplierFifoMixin:
    @staticmethod
    def pay_supplier_debts_fifo(
        supplier_id: int,
        account_id: int,
        amount: float,
        payment_date: Optional[datetime],
        note: Optional[str],
        user_id: int,
        db: Session,
    ) -> Dict[str, Any]:
        amount_dec = Decimal(str(amount))
        if amount_dec <= Decimal("0"):
            raise HTTPException(status_code=400, detail="Số tiền thanh toán phải lớn hơn 0")

        if payment_date is None:
            payment_date = datetime.now()

        try:
            supplier = DebtRepository.get_supplier_by_id_and_user(supplier_id=supplier_id, user_id=user_id, db=db)
            if not supplier:
                raise HTTPException(status_code=404, detail=f"Nhà cung cấp {supplier_id} không tồn tại hoặc không thuộc quyền quản lý")

            debts = (
                db.query(Debt)
                .filter(
                    Debt.supplier_id == supplier_id,
                    Debt.user_id == user_id,
                    Debt.direction == "PAYABLE",
                    Debt.status != "PAID",
                    Debt.remaining_debt > 0
                )
                .order_by(Debt.created_at.asc(), Debt.debt_id.asc())
                .with_for_update()
                .all()
            )
            if not debts:
                raise HTTPException(status_code=404, detail=f"Nhà cung cấp {supplier_id} hiện không có khoản nợ nào đang mở")

            total_remaining = sum(Decimal(str(d.remaining_debt or 0)) for d in debts)
            if total_remaining <= Decimal("0"):
                raise HTTPException(status_code=400, detail="Các khoản công nợ này đã được thanh toán đầy đủ")

            if amount_dec > total_remaining:
                raise HTTPException(
                    status_code=400,
                    detail=f"Số tiền thanh toán ({amount_dec}) vượt quá tổng số nợ hiện có ({total_remaining})"
                )

            account = DebtRepository.get_account_by_id_and_user(account_id=account_id, user_id=user_id, db=db, for_update=True)
            if not account or not account.is_active:
                raise HTTPException(status_code=404, detail=f"Tài khoản {account_id} không tồn tại hoặc đã bị vô hiệu hóa")

            current_balance = Decimal(str(account.balance or 0))
            if current_balance < amount_dec:
                raise HTTPException(
                    status_code=400,
                    detail=f"Số dư tài khoản ({current_balance}) không đủ để thanh toán ({amount_dec})"
                )

            intent_id = _get_intent_id(db, "tra_no_nha_cung_cap")

            new_tx = Transaction(
                user_id=user_id,
                intent_id=intent_id,
                account_id=account_id,
                customer_id=None,
                supplier_id=supplier_id,
                total_amount=amount_dec,
                payment_status="PAID",
                input_method="MANUAL",
                input_text=note or "Thanh toán công nợ NCC",
                transaction_date=payment_date,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            db.add(new_tx)
            db.flush()

            amount_left = amount_dec
            allocations = []
            for d in debts:
                if amount_left <= Decimal("0"):
                    break
                rem = Decimal(str(d.remaining_debt or 0))
                if rem <= Decimal("0"):
                    continue

                applied = min(amount_left, rem)
                orig = Decimal(str(d.original_amount or 0))
                pct = ((applied / orig * 100).quantize(Decimal("0.01")) if orig > 0 else Decimal("0.00"))

                dp = DebtPayment(
                    debt_id=d.debt_id,
                    transaction_id=new_tx.transaction_id,
                    account_id=account_id,
                    amount=applied,
                    payment_percentage=pct,
                    payment_date=payment_date,
                    note=note,
                    created_at=datetime.now(),
                )
                db.add(dp)

                rem_after = rem - applied
                d.remaining_debt = max(Decimal("0.00"), rem_after)
                d.status = "PAID" if d.remaining_debt == 0 else "PARTIAL"
                d.updated_at = datetime.now()
                if getattr(d, "transaction", None):
                    d.transaction.payment_status = d.status

                allocations.append({
                    "debt_id": d.debt_id,
                    "transaction_id": d.transaction_id or new_tx.transaction_id,
                    "amount_applied": float(applied),
                    "remaining_debt": float(d.remaining_debt),
                    "status": str(d.status),
                })
                amount_left -= applied

            account.balance = current_balance - amount_dec
            account.updated_at = datetime.now()

            db.commit()

            final_remaining = max(Decimal("0.00"), total_remaining - amount_dec)
            return {
                "supplier_id": supplier_id,
                "amount_paid": float(amount_dec),
                "before": {
                    "total_remaining": float(total_remaining)
                },
                "after": {
                    "total_remaining": float(final_remaining)
                },
                "allocations": allocations
            }
        except HTTPException:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Lỗi khi xử lý FIFO công nợ NCC: {str(e)}")
