from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.repositories.debt_repository import DebtRepository
from app.services.debt.debt_helper import DebtHelperMixin


class DebtQueryMixin:
    format_debt: Any

    @classmethod
    def get_all_debts(
        cls,
        user_id: int,
        db: Session,
        name: Optional[str] = None,
        direction: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        results = DebtRepository.get_all_by_user(
            user_id=user_id, db=db, name=name, direction=direction, status=status
        )
        return [DebtHelperMixin.format_debt(result) for result in results]

    @staticmethod
    def get_summary(user_id: int, db: Session) -> Dict[str, Any]:
        return DebtRepository.get_summary_by_user(user_id=user_id, db=db)

    @staticmethod
    def get_debts_paginated(
        user_id: int,
        db: Session,
        direction: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        customer_id: Optional[int] = None,
        supplier_id: Optional[int] = None,
        page: int = 1,
        limit: int = 20,
    ) -> Dict[str, Any]:
        debts, total = DebtRepository.get_debts_paginated(
            user_id=user_id,
            db=db,
            direction=direction,
            status=status,
            search=search,
            customer_id=customer_id,
            supplier_id=supplier_id,
            page=page,
            limit=limit,
        )
        total_pages = (total + limit - 1) // limit if total > 0 else 1

        items = []
        for debt in debts:
            orig = float(debt.original_amount) if debt.original_amount is not None else 0.0
            rem = float(debt.remaining_debt) if debt.remaining_debt is not None else 0.0
            paid = max(0.0, orig - rem)

            cust_info = None
            if debt.customer:
                cust_info = {
                    "customer_id": debt.customer.customer_id,
                    "customer_name": debt.customer.customer_name,
                    "phone_number": debt.customer.phone_number,
                    "email": debt.customer.email,
                    "address": debt.customer.address,
                    "customer_type": debt.customer.customer_type,
                }

            supp_info = None
            if debt.supplier:
                supp_info = {
                    "supplier_id": debt.supplier.supplier_id,
                    "supplier_name": debt.supplier.supplier_name,
                    "phone_number": debt.supplier.phone_number,
                    "email": debt.supplier.email,
                    "address": debt.supplier.address,
                    "product_group": debt.supplier.product_group,
                    "tax_code": debt.supplier.tax_code,
                    "note": debt.supplier.note,
                }

            tx_info = None
            if debt.transaction:
                details = []
                if hasattr(debt.transaction, "transaction_detail") and debt.transaction.transaction_detail:
                    for td in debt.transaction.transaction_detail:
                        pname = td.product.product_name if td.product else None
                        details.append({
                            "detail_id": td.detail_id,
                            "product_id": td.product_id,
                            "product_name": pname,
                            "quantity": float(td.quantity or 0),
                            "unit": td.unit,
                            "unit_price": float(td.unit_price or 0),
                            "subtotal": float(td.subtotal or 0),
                        })
                tx_intent_name = debt.transaction.intent.intent_name if debt.transaction.intent else None
                tx_intent_type = str(debt.transaction.intent.intent_type) if (debt.transaction.intent and debt.transaction.intent.intent_type) else None
                tx_info = {
                    "transaction_id": debt.transaction.transaction_id,
                    "transaction_date": debt.transaction.transaction_date,
                    "intent_name": tx_intent_name,
                    "intent_type": tx_intent_type,
                    "type": tx_intent_type,
                    "input_text": debt.transaction.input_text,
                    "total_amount": float(debt.transaction.total_amount or 0),
                    "payment_status": str(debt.transaction.payment_status) if debt.transaction.payment_status else None,
                    "details": details,
                }

            items.append({
                "debt_id": debt.debt_id,
                "transaction_id": debt.transaction_id,
                "direction": str(debt.direction),
                "customer": cust_info,
                "supplier": supp_info,
                "original_amount": orig,
                "paid_amount": paid,
                "remaining_debt": rem,
                "status": str(debt.status),
                "transaction": tx_info,
                "created_at": debt.created_at,
                "updated_at": debt.updated_at,
                "customer_id": debt.customer_id,
                "customer_name": debt.customer.customer_name if debt.customer else None,
                "supplier_id": debt.supplier_id,
                "supplier_name": debt.supplier.supplier_name if debt.supplier else None,
            })

        return {
            "items": items,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "total_pages": total_pages,
            },
        }

    @staticmethod
    def get_debt_detail(debt_id: int, user_id: int, db: Session) -> Dict[str, Any]:
        debt = DebtRepository.get_debt_by_id_and_user(debt_id=debt_id, user_id=user_id, db=db)
        if not debt:
            raise HTTPException(
                status_code=404,
                detail=f"Công nợ {debt_id} không tồn tại hoặc không thuộc quyền quản lý"
            )

        orig = float(debt.original_amount) if debt.original_amount is not None else 0.0
        rem = float(debt.remaining_debt) if debt.remaining_debt is not None else 0.0
        paid = max(0.0, orig - rem)

        cust_info = None
        if debt.customer:
            cust_info = {
                "customer_id": debt.customer.customer_id,
                "customer_name": debt.customer.customer_name,
                "phone_number": debt.customer.phone_number,
                "email": debt.customer.email,
                "address": debt.customer.address,
                "customer_type": debt.customer.customer_type,
            }

        supp_info = None
        if debt.supplier:
            supp_info = {
                "supplier_id": debt.supplier.supplier_id,
                "supplier_name": debt.supplier.supplier_name,
                "phone_number": debt.supplier.phone_number,
                "email": debt.supplier.email,
                "address": debt.supplier.address,
                "product_group": debt.supplier.product_group,
                "tax_code": debt.supplier.tax_code,
                "note": debt.supplier.note,
            }

        debt_info = {
            "original_amount": orig,
            "paid_amount": paid,
            "remaining_debt": rem,
            "status": str(debt.status),
        }

        tx_info = None
        if debt.transaction:
            details = []
            if hasattr(debt.transaction, "transaction_detail") and debt.transaction.transaction_detail:
                for td in debt.transaction.transaction_detail:
                    pname = td.product.product_name if td.product else None
                    details.append({
                        "detail_id": td.detail_id,
                        "product_id": td.product_id,
                        "product_name": pname,
                        "quantity": float(td.quantity or 0),
                        "unit": td.unit,
                        "unit_price": float(td.unit_price or 0),
                        "subtotal": float(td.subtotal or 0),
                    })
                tx_intent_name = debt.transaction.intent.intent_name if debt.transaction.intent else None
                tx_intent_type = str(debt.transaction.intent.intent_type) if (debt.transaction.intent and debt.transaction.intent.intent_type) else None
                tx_info = {
                    "transaction_id": debt.transaction.transaction_id,
                    "transaction_date": debt.transaction.transaction_date,
                    "intent_name": tx_intent_name,
                    "intent_type": tx_intent_type,
                    "type": tx_intent_type,
                    "input_text": debt.transaction.input_text,
                    "total_amount": float(debt.transaction.total_amount or 0),
                    "payment_status": str(debt.transaction.payment_status) if debt.transaction.payment_status else None,
                    "details": details,
                }

        payments_list = []
        if debt.payments:
            sorted_payments = sorted(
                debt.payments,
                key=lambda p: (p.payment_date or datetime.min, p.created_at or datetime.min),
                reverse=True
            )
            for p in sorted_payments:
                acc_info = None
                if p.account:
                    acc_info = {
                        "account_id": p.account.account_id,
                        "account_name": p.account.account_name,
                        "account_type": str(p.account.account_type) if p.account.account_type else None,
                    }
                payments_list.append({
                    "payment_id": p.payment_id,
                    "debt_id": p.debt_id,
                    "transaction_id": p.transaction_id,
                    "account_id": p.account_id,
                    "account": acc_info,
                    "amount": float(p.amount) if p.amount is not None else 0.0,
                    "payment_percentage": float(p.payment_percentage) if p.payment_percentage is not None else None,
                    "payment_date": p.payment_date,
                    "note": p.note,
                    "created_at": p.created_at,
                })

        return {
            "debt_id": debt.debt_id,
            "direction": str(debt.direction),
            "customer": cust_info,
            "supplier": supp_info,
            "debt": debt_info,
            "transaction": tx_info,
            "payments": payments_list,
            "original_amount": orig,
            "paid_amount": paid,
            "remaining_debt": rem,
            "status": str(debt.status),
            "transaction_id": debt.transaction_id,
            "created_at": debt.created_at,
            "updated_at": debt.updated_at,
        }

    @staticmethod
    def get_payment_history(debt_id: int, user_id: int, db: Session) -> List[Dict[str, Any]]:
        payments = DebtRepository.get_payments_by_debt_id(debt_id=debt_id, user_id=user_id, db=db)
        if payments is None:
            raise HTTPException(
                status_code=404,
                detail=f"Công nợ {debt_id} không tồn tại hoặc không thuộc quyền quản lý"
            )

        res = []
        for p in payments:
            acc_info = None
            if p.account:
                acc_info = {
                    "account_id": p.account.account_id,
                    "account_name": p.account.account_name,
                    "account_type": str(p.account.account_type) if p.account.account_type else None,
                }
            res.append({
                "payment_id": p.payment_id,
                "debt_id": p.debt_id,
                "transaction_id": p.transaction_id,
                "account_id": p.account_id,
                "account": acc_info,
                "amount": float(p.amount) if p.amount is not None else 0.0,
                "payment_percentage": float(p.payment_percentage) if p.payment_percentage is not None else None,
                "payment_date": p.payment_date,
                "note": p.note,
                "created_at": p.created_at,
            })
        return res
