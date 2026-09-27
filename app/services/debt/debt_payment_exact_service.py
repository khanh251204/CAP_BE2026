from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.transaction_model import Transaction
from app.models.debt_payment_model import DebtPayment
from app.repositories.debt_repository import DebtRepository
from app.services.debt.debt_helper import _get_intent_id


class DebtPaymentExactMixin:
    @staticmethod
    def pay_debt_exact(
        debt_id: int,
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
            debt = DebtRepository.get_debt_by_id_and_user(
                debt_id=debt_id, user_id=user_id, db=db, for_update=True
            )
            if not debt:
                raise HTTPException(
                    status_code=404,
                    detail=f"Công nợ {debt_id} không tồn tại hoặc không thuộc quyền quản lý"
                )

            remaining_dec = Decimal(str(debt.remaining_debt or 0))
            if str(debt.status).upper() == "PAID" or remaining_dec <= Decimal("0"):
                raise HTTPException(status_code=400, detail="Công nợ này đã được thanh toán đầy đủ")

            if amount_dec > remaining_dec:
                raise HTTPException(
                    status_code=400,
                    detail=f"Số tiền thanh toán ({amount_dec}) vượt quá số nợ còn lại ({remaining_dec})"
                )

            account = DebtRepository.get_account_by_id_and_user(
                account_id=account_id, user_id=user_id, db=db, for_update=True
            )
            if not account or not account.is_active:
                raise HTTPException(
                    status_code=404,
                    detail=f"Tài khoản {account_id} không tồn tại hoặc đã bị vô hiệu hóa"
                )

            current_balance = Decimal(str(account.balance or 0))
            direction = str(debt.direction).upper()

            if direction == "RECEIVABLE":
                account.balance = current_balance + amount_dec
                intent_name = "thu_no_khach_hang"
                default_note = note or "Thu nợ khách hàng"
            elif direction == "PAYABLE":
                if current_balance < amount_dec:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Số dư tài khoản ({current_balance}) không đủ để thanh toán ({amount_dec})"
                    )
                account.balance = current_balance - amount_dec
                intent_name = "tra_no_nha_cung_cap"
                default_note = note or "Trả nợ nhà cung cấp"
            else:
                raise HTTPException(status_code=400, detail=f"Chiều công nợ không hợp lệ: {direction}")

            intent_id = _get_intent_id(db, intent_name)

            new_tx = Transaction(
                user_id=user_id,
                intent_id=intent_id,
                account_id=account_id,
                customer_id=debt.customer_id,
                supplier_id=debt.supplier_id,
                total_amount=amount_dec,
                payment_status="PAID",
                input_method="MANUAL",
                input_text=default_note,
                transaction_date=payment_date,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            db.add(new_tx)
            db.flush()

            orig_dec = Decimal(str(debt.original_amount or 0))
            pct = (
                (amount_dec / orig_dec * 100).quantize(Decimal("0.01"))
                if orig_dec > 0 else Decimal("0.00")
            )

            debt_payment = DebtPayment(
                debt_id=debt.debt_id,
                transaction_id=new_tx.transaction_id,
                account_id=account_id,
                amount=amount_dec,
                payment_percentage=pct,
                payment_date=payment_date,
                note=note,
                created_at=datetime.now(),
            )
            db.add(debt_payment)
            db.flush()

            new_remaining = remaining_dec - amount_dec
            debt.remaining_debt = max(Decimal("0.00"), new_remaining)
            debt.status = "PAID" if debt.remaining_debt == 0 else "PARTIAL"
            debt.updated_at = datetime.now()

            if getattr(debt, "transaction", None):
                debt.transaction.payment_status = debt.status
                debt.transaction.updated_at = datetime.now()

            account.updated_at = datetime.now()

            db.commit()
            db.refresh(debt_payment)
            db.refresh(debt)
            db.refresh(account)

            orig_val = float(debt.original_amount)
            rem_val = float(debt.remaining_debt)
            paid_val = max(0.0, orig_val - rem_val)

            return {
                "payment_id": debt_payment.payment_id,
                "debt_id": debt.debt_id,
                "transaction_id": new_tx.transaction_id,
                "amount_paid": float(amount_dec),
                "debt": {
                    "original_amount": orig_val,
                    "paid_amount": paid_val,
                    "remaining_debt": rem_val,
                    "status": str(debt.status),
                },
                "account": {
                    "account_id": account.account_id,
                    "account_name": account.account_name,
                    "balance": float(account.balance),
                }
            }
        except HTTPException:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Lỗi khi thanh toán công nợ: {str(e)}")
