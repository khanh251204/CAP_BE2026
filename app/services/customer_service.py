from typing import Optional, Dict, Any, List
from datetime import datetime
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.customer_model import Customer
from app.repositories.customer_repository import CustomerRepository
from app.schemas.customer_schema import (
    CustomerCreateRequest,
    CustomerUpdateRequest,
)


class CustomerService:

    @staticmethod
    def create_customer(
        user_id: int,
        request: CustomerCreateRequest,
        db: Session
    ) -> Dict[str, Any]:
        customer = Customer(
            user_id=user_id,
            customer_name=request.customer_name.strip(),
            phone_number=request.phone_number.strip() if request.phone_number else None,
            email=request.email.strip() if request.email else None,
            address=request.address.strip() if request.address else None,
            customer_type=request.customer_type.strip() if request.customer_type else "REGULAR",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        saved = CustomerRepository.create(customer=customer, db=db)
        return {
            "customer_id": saved.customer_id,
            "user_id": saved.user_id,
            "customer_name": saved.customer_name,
            "phone_number": saved.phone_number,
            "email": saved.email,
            "address": saved.address,
            "customer_type": saved.customer_type,
            "created_at": saved.created_at,
            "updated_at": saved.updated_at,
        }

    @staticmethod
    def get_customers(
        user_id: int,
        db: Session,
        search: Optional[str] = None,
        page: int = 1,
        limit: int = 20
    ) -> Dict[str, Any]:
        items, total = CustomerRepository.get_list_by_user(
            user_id=user_id,
            db=db,
            search=search,
            page=page,
            limit=limit
        )
        total_pages = (total + limit - 1) // limit if total > 0 else 1

        return {
            "items": [
                {
                    "customer_id": c.customer_id,
                    "user_id": c.user_id,
                    "customer_name": c.customer_name,
                    "phone_number": c.phone_number,
                    "email": c.email,
                    "address": c.address,
                    "customer_type": c.customer_type,
                    "created_at": c.created_at,
                    "updated_at": c.updated_at,
                }
                for c in items
            ],
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "total_pages": total_pages,
            }
        }

    @staticmethod
    def get_customer_detail(
        customer_id: int,
        user_id: int,
        db: Session
    ) -> Dict[str, Any]:
        customer = CustomerRepository.get_by_id_and_user(customer_id=customer_id, user_id=user_id, db=db)
        if not customer:
            raise HTTPException(
                status_code=404,
                detail=f"Khách hàng {customer_id} không tồn tại hoặc không thuộc quyền quản lý"
            )

        summary = CustomerRepository.get_customer_debt_summary(customer_id=customer_id, user_id=user_id, db=db)
        return {
            "customer_id": customer.customer_id,
            "user_id": customer.user_id,
            "customer_name": customer.customer_name,
            "phone_number": customer.phone_number,
            "email": customer.email,
            "address": customer.address,
            "customer_type": customer.customer_type,
            "created_at": customer.created_at,
            "updated_at": customer.updated_at,
            "debt_summary": summary,
        }

    @staticmethod
    def update_customer(
        customer_id: int,
        user_id: int,
        request: CustomerUpdateRequest,
        db: Session
    ) -> Dict[str, Any]:
        customer = CustomerRepository.get_by_id_and_user(customer_id=customer_id, user_id=user_id, db=db)
        if not customer:
            raise HTTPException(
                status_code=404,
                detail=f"Khách hàng {customer_id} không tồn tại hoặc không thuộc quyền quản lý"
            )

        if request.customer_name is not None:
            customer.customer_name = request.customer_name.strip()
        if request.phone_number is not None:
            customer.phone_number = request.phone_number.strip() if request.phone_number else None
        if request.email is not None:
            customer.email = request.email.strip() if request.email else None
        if request.address is not None:
            customer.address = request.address.strip() if request.address else None
        if request.customer_type is not None:
            customer.customer_type = request.customer_type.strip() if request.customer_type else None

        saved = CustomerRepository.update(customer=customer, db=db)
        return {
            "customer_id": saved.customer_id,
            "user_id": saved.user_id,
            "customer_name": saved.customer_name,
            "phone_number": saved.phone_number,
            "email": saved.email,
            "address": saved.address,
            "customer_type": saved.customer_type,
            "created_at": saved.created_at,
            "updated_at": saved.updated_at,
        }

    @staticmethod
    def delete_customer(
        customer_id: int,
        user_id: int,
        db: Session
    ) -> Dict[str, Any]:
        customer = CustomerRepository.get_by_id_and_user(customer_id=customer_id, user_id=user_id, db=db)
        if not customer:
            raise HTTPException(
                status_code=404,
                detail=f"Khách hàng {customer_id} không tồn tại hoặc không thuộc quyền quản lý"
            )

        if CustomerRepository.has_associated_records(customer_id=customer_id, user_id=user_id, db=db):
            raise HTTPException(
                status_code=400,
                detail="Không thể xóa khách hàng đã phát sinh giao dịch hoặc công nợ"
            )

        CustomerRepository.delete(customer=customer, db=db)
        return {
            "success": True,
            "message": f"Đã xóa khách hàng {customer_id} thành công"
        }

    @staticmethod
    def get_customer_debts(
        customer_id: int,
        user_id: int,
        db: Session
    ) -> Dict[str, Any]:
        customer = CustomerRepository.get_by_id_and_user(customer_id=customer_id, user_id=user_id, db=db)
        if not customer:
            raise HTTPException(
                status_code=404,
                detail=f"Khách hàng {customer_id} không tồn tại hoặc không thuộc quyền quản lý"
            )

        summary = CustomerRepository.get_customer_debt_summary(customer_id=customer_id, user_id=user_id, db=db)
        debts = CustomerRepository.get_customer_debts_with_details(customer_id=customer_id, user_id=user_id, db=db)

        debt_items = []
        for d in debts:
            orig = float(d.original_amount) if d.original_amount is not None else 0.0
            rem = float(d.remaining_debt) if d.remaining_debt is not None else 0.0
            paid = max(0.0, orig - rem)

            tx_info = None
            if d.transaction:
                details = []
                if hasattr(d.transaction, "transaction_detail") and d.transaction.transaction_detail:
                    for td in d.transaction.transaction_detail:
                        pname = td.product_name or (td.product.product_name if td.product else None)
                        details.append({
                            "detail_id": td.detail_id,
                            "product_id": td.product_id,
                            "product_name": pname,
                            "quantity": float(td.quantity or 0),
                            "unit": td.unit,
                            "unit_price": float(td.unit_price or 0),
                            "subtotal": float(td.subtotal or 0),
                        })
                tx_info = {
                    "transaction_id": d.transaction.transaction_id,
                    "transaction_date": d.transaction.transaction_date,
                    "intent_name": d.transaction.intent.intent_name if d.transaction.intent else None,
                    "input_text": d.transaction.input_text,
                    "total_amount": float(d.transaction.total_amount or 0),
                    "payment_status": str(d.transaction.payment_status) if d.transaction.payment_status else None,
                    "details": details,
                }

            debt_items.append({
                "debt_id": d.debt_id,
                "transaction_id": d.transaction_id,
                "direction": str(d.direction),
                "customer": {
                    "customer_id": customer.customer_id,
                    "customer_name": customer.customer_name,
                    "phone_number": customer.phone_number,
                    "email": customer.email,
                    "address": customer.address,
                    "customer_type": customer.customer_type,
                },
                "supplier": None,
                "original_amount": orig,
                "paid_amount": paid,
                "remaining_debt": rem,
                "status": str(d.status),
                "transaction": tx_info,
                "created_at": d.created_at,
                "updated_at": d.updated_at,
                "customer_id": customer.customer_id,
                "customer_name": customer.customer_name,
            })

        return {
            "customer": {
                "customer_id": customer.customer_id,
                "customer_name": customer.customer_name,
                "phone_number": customer.phone_number,
                "email": customer.email,
                "address": customer.address,
                "customer_type": customer.customer_type,
            },
            "debt_summary": summary,
            "debts": debt_items,
        }
