from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.transaction_model import Transaction
from app.models.debt_model import Debt
from app.models.debt_payment_model import DebtPayment
from app.repositories.debt_repository import DebtRepository
from app.services.debt.debt_helper import _get_intent_id, DebtHelperMixin


class SupplierDebtMixin:
    format_debt: Any

    @staticmethod
    def create_supplier_debt(
        db: Session,
        user_id: int,
        supplier_id: int,
        total_debt: float,
        transaction_id: Optional[int] = None,
        note: Optional[str] = None,
        input_method: Optional[str] = "MANUAL",
    ) -> Dict[str, Any]:
        supplier = DebtRepository.get_supplier_by_id_and_user(supplier_id=supplier_id, user_id=user_id, db=db)
        if not supplier:
            raise HTTPException(
                status_code=404,
                detail=f"Nhà cung cấp {supplier_id} không tồn tại hoặc không thuộc quyền quản lý"
            )

        total_debt_dec = Decimal(str(total_debt))
        if total_debt_dec <= 0:
            raise HTTPException(status_code=400, detail="Số tiền công nợ phải lớn hơn 0")

        clean_method = "VOICE" if str(input_method or "").upper().strip() == "VOICE" else "MANUAL"

        try:
            if transaction_id is None:
                intent_id = _get_intent_id(db, "ghi_no_nha_cung_cap")
                new_tx = Transaction(
                    user_id=user_id,
                    intent_id=intent_id,
                    account_id=None,
                    customer_id=None,
                    supplier_id=supplier_id,
                    total_amount=total_debt_dec,
                    payment_status="PENDING",
                    input_method=clean_method,
                    input_text=note or "Ghi nợ nhà cung cấp",
                    transaction_date=datetime.now(),
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )
                db.add(new_tx)
                db.flush()
                transaction_id = new_tx.transaction_id
            else:
                existing_tx = db.query(Transaction).filter(
                    Transaction.transaction_id == transaction_id,
                    Transaction.user_id == user_id
                ).first()
                if not existing_tx:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Giao dịch {transaction_id} không tồn tại hoặc không thuộc quyền quản lý"
                    )

            debt = Debt(
                transaction_id=transaction_id,
                user_id=user_id,
                customer_id=None,
                supplier_id=supplier_id,
                direction="PAYABLE",
                original_amount=total_debt_dec,
                remaining_debt=total_debt_dec,
                status="UNPAID",
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            db.add(debt)
            db.commit()
            db.refresh(debt)

            return {
                "debt_id": debt.debt_id,
                "status": debt.status,
                "total_debt": float(debt.original_amount),
                "original_amount": float(debt.original_amount),
                "remaining_debt": float(debt.remaining_debt),
            }
        except HTTPException:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Lỗi khi tạo công nợ nhà cung cấp: {str(e)}")

    @staticmethod
    def pay_supplier_debt(
        db: Session,
        user_id: int,
        account_id: int,
        amount: float,
        debt_id: Optional[int] = None,
        supplier_id: Optional[int] = None,
        payment_date: Optional[datetime] = None,
        note: Optional[str] = None,
        input_method: Optional[str] = "MANUAL",
    ) -> Dict[str, Any]:
        if payment_date is None:
            payment_date = datetime.now()

        amount_dec = Decimal(str(amount))
        if amount_dec <= 0:
            raise HTTPException(status_code=400, detail="Số tiền thanh toán phải lớn hơn 0")

        clean_method = "VOICE" if str(input_method or "").upper().strip() == "VOICE" else "MANUAL"

        if not debt_id and not supplier_id:
            raise HTTPException(
                status_code=400,
                detail="Phải truyền debt_id (trả 1 khoản cụ thể) hoặc supplier_id (trả tổng, tự phân bổ FIFO)"
            )

        try:
            if debt_id:
                debt = DebtRepository.get_debt_by_id_and_user(
                    debt_id=debt_id, user_id=user_id, db=db, direction="PAYABLE", for_update=True
                )
                if not debt:
                    raise HTTPException(status_code=404, detail=f"Công nợ {debt_id} không tồn tại hoặc không thuộc về bạn")
                if str(debt.status).upper() == "PAID" or (debt.remaining_debt is not None and Decimal(str(debt.remaining_debt)) <= Decimal("0")):
                    raise HTTPException(status_code=400, detail="Công nợ này đã được thanh toán đầy đủ")
                debts_to_pay = [debt]
            else:
                supplier = DebtRepository.get_supplier_by_id_and_user(supplier_id=supplier_id, user_id=user_id, db=db)
                if not supplier:
                    raise HTTPException(status_code=404, detail=f"Nhà cung cấp {supplier_id} không tồn tại hoặc không thuộc quyền quản lý")

                debts_to_pay = DebtRepository.get_open_debts_by_supplier_and_user(
                    db=db, supplier_id=supplier_id, user_id=user_id, direction="PAYABLE", order_by="created_at asc", for_update=True
                )
                if not debts_to_pay:
                    raise HTTPException(status_code=404, detail=f"Nhà cung cấp {supplier_id} hiện không có khoản nợ nào đang mở")

            remaining_map = {}
            total_remaining = Decimal("0")
            for d in debts_to_pay:
                r = Decimal(str(d.remaining_debt)) if d.remaining_debt is not None else Decimal(str(d.original_amount or 0))
                remaining_map[d.debt_id] = r
                total_remaining += r

            if total_remaining <= Decimal("0"):
                raise HTTPException(status_code=400, detail="Các khoản công nợ này đã được thanh toán đầy đủ")

            if amount_dec > total_remaining:
                raise HTTPException(
                    status_code=400,
                    detail=f"Số tiền thanh toán ({amount_dec}) vượt quá tổng số nợ hiện có ({total_remaining}). Vui lòng nhập số tiền nhỏ hơn hoặc bằng {total_remaining}."
                )

            account = DebtRepository.get_account_by_id_and_user(account_id=account_id, user_id=user_id, db=db, for_update=True)
            if not account or not account.is_active:
                raise HTTPException(status_code=404, detail=f"Tài khoản {account_id} không tồn tại hoặc đã bị vô hiệu hóa")

            current_balance = Decimal(str(account.balance)) if account.balance is not None else Decimal("0")
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
                supplier_id=supplier_id if supplier_id else debts_to_pay[0].supplier_id,
                total_amount=amount_dec,
                payment_status="PAID",
                input_method=clean_method,
                input_text=note or "Trả nợ nhà cung cấp",
                transaction_date=payment_date,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            db.add(new_tx)
            db.flush()

            amount_left = amount_dec
            payments_created = []
            debts_summary = []

            for d in debts_to_pay:
                if amount_left <= Decimal("0"):
                    break
                remaining_before = remaining_map[d.debt_id]
                if remaining_before <= Decimal("0"):
                    continue

                allocated = min(amount_left, remaining_before)
                orig_amount = Decimal(str(d.original_amount)) if d.original_amount else allocated
                payment_percentage = (
                    (allocated / orig_amount * 100).quantize(Decimal("0.01")) if orig_amount > 0 else Decimal("0.00")
                )

                debt_payment = DebtPayment(
                    debt_id=d.debt_id,
                    transaction_id=new_tx.transaction_id,
                    account_id=account_id,
                    amount=allocated,
                    payment_percentage=payment_percentage,
                    payment_date=payment_date,
                    note=note,
                    created_at=datetime.now(),
                )
                db.add(debt_payment)
                db.flush()
                payments_created.append(debt_payment)

                remaining_after = remaining_before - allocated
                if remaining_after <= Decimal("0"):
                    d.remaining_debt = Decimal("0.00")
                    d.status = "PAID"
                else:
                    d.remaining_debt = remaining_after
                    d.status = "PARTIAL"
                d.updated_at = datetime.now()

                if getattr(d, "transaction", None):
                    d.transaction.payment_status = d.status
                    d.transaction.updated_at = datetime.now()

                debts_summary.append({
                    "debt_id": d.debt_id,
                    "payment_id": debt_payment.payment_id,
                    "amount_applied": float(allocated),
                    "remaining_debt": float(max(d.remaining_debt, Decimal("0"))),
                    "debt_status": d.status,
                })
                amount_left -= allocated

            account.balance = current_balance - amount_dec
            account.updated_at = datetime.now()

            db.commit()
            for p in payments_created:
                db.refresh(p)

            if debt_id:
                d = debts_to_pay[0]
                return {
                    "payment_id": payments_created[0].payment_id if payments_created else None,
                    "debt_id": d.debt_id,
                    "remaining_debt": float(max(d.remaining_debt, Decimal("0"))),
                    "debt_status": d.status,
                    "amount_paid": float(amount_dec),
                }

            remaining_final = max(total_remaining - amount_dec, Decimal("0"))
            return {
                "supplier_id": supplier_id,
                "payment_id": payments_created[0].payment_id if payments_created else None,
                "amount_paid": float(amount_dec),
                "total_remaining_before": float(total_remaining),
                "total_remaining_after": float(remaining_final),
                "remaining_debt": float(remaining_final),
                "debt_status": "PAID" if remaining_final <= Decimal("0") else "PARTIAL",
                "debts": debts_summary,
            }
        except HTTPException:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Lỗi khi thanh toán công nợ: {str(e)}")

    @classmethod
    def get_supplier_debts(
        cls,
        user_id: int,
        db: Session,
        supplier_id: Optional[int] = None,
        status: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        results = DebtRepository.get_supplier_debts(
            user_id=user_id, db=db, supplier_id=supplier_id, status=status, search=search
        )
        return [DebtHelperMixin.format_debt(result) for result in results]
