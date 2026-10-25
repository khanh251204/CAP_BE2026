from typing import Optional, Dict, Any, List
from datetime import datetime
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.supplier_model import Supplier
from app.repositories.supplier_repository import SupplierRepository
from app.services.duplicate_guard import clean_name, ensure_unique_supplier
from app.schemas.supplier_schema import (
    SupplierCreateRequest,
    SupplierUpdateRequest,
)


class SupplierService:

    @staticmethod
    def create_supplier(
        user_id: int,
        request: SupplierCreateRequest,
        db: Session
    ) -> Dict[str, Any]:
        name = clean_name(request.supplier_name)
        if not name:
            raise HTTPException(status_code=400, detail="Tên nhà cung cấp không được để trống")
        # Không cho trùng tên, số điện thoại hoặc mã số thuế với nhà cung cấp đã có
        ensure_unique_supplier(db, user_id, name=name, phone=request.phone_number, tax_code=request.tax_code)

        supplier = Supplier(
            user_id=user_id,
            supplier_name=name,
            phone_number=request.phone_number.strip() if request.phone_number else None,
            email=request.email.strip() if request.email else None,
            address=request.address.strip() if request.address else None,
            product_group=request.product_group.strip() if request.product_group else None,
            tax_code=request.tax_code.strip() if request.tax_code else None,
            note=request.note.strip() if request.note else None,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        saved = SupplierRepository.create(supplier=supplier, db=db)
        return {
            "supplier_id": saved.supplier_id,
            "user_id": saved.user_id,
            "supplier_name": saved.supplier_name,
            "phone_number": saved.phone_number,
            "email": saved.email,
            "address": saved.address,
            "product_group": saved.product_group,
            "tax_code": saved.tax_code,
            "note": saved.note,
            "created_at": saved.created_at,
            "updated_at": saved.updated_at,
        }

    @staticmethod
    def get_suppliers(
        user_id: int,
        db: Session,
        search: Optional[str] = None,
        page: int = 1,
        limit: int = 20
    ) -> Dict[str, Any]:
        items, total = SupplierRepository.get_list_by_user(
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
                    "supplier_id": s.supplier_id,
                    "user_id": s.user_id,
                    "supplier_name": s.supplier_name,
                    "phone_number": s.phone_number,
                    "email": s.email,
                    "address": s.address,
                    "product_group": s.product_group,
                    "tax_code": s.tax_code,
                    "note": s.note,
                    "created_at": s.created_at,
                    "updated_at": s.updated_at,
                }
                for s in items
            ],
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "total_pages": total_pages,
            }
        }

    @staticmethod
    def get_supplier_detail(
        supplier_id: int,
        user_id: int,
        db: Session
    ) -> Dict[str, Any]:
        supplier = SupplierRepository.get_by_id_and_user(supplier_id=supplier_id, user_id=user_id, db=db)
        if not supplier:
            raise HTTPException(
                status_code=404,
                detail=f"Nhà cung cấp {supplier_id} không tồn tại hoặc không thuộc quyền quản lý"
            )

        summary = SupplierRepository.get_supplier_debt_summary(supplier_id=supplier_id, user_id=user_id, db=db)
        return {
            "supplier_id": supplier.supplier_id,
            "user_id": supplier.user_id,
            "supplier_name": supplier.supplier_name,
            "phone_number": supplier.phone_number,
            "email": supplier.email,
            "address": supplier.address,
            "product_group": supplier.product_group,
            "tax_code": supplier.tax_code,
            "note": supplier.note,
            "created_at": supplier.created_at,
            "updated_at": supplier.updated_at,
            "debt_summary": summary,
        }

    @staticmethod
    def update_supplier(
        supplier_id: int,
        user_id: int,
        request: SupplierUpdateRequest,
        db: Session
    ) -> Dict[str, Any]:
        supplier = SupplierRepository.get_by_id_and_user(supplier_id=supplier_id, user_id=user_id, db=db)
        if not supplier:
            raise HTTPException(
                status_code=404,
                detail=f"Nhà cung cấp {supplier_id} không tồn tại hoặc không thuộc quyền quản lý"
            )

        new_name = clean_name(request.supplier_name) if request.supplier_name is not None else None
        if request.supplier_name is not None and not new_name:
            raise HTTPException(status_code=400, detail="Tên nhà cung cấp không được để trống")
        ensure_unique_supplier(
            db, user_id,
            name=new_name,
            phone=request.phone_number if request.phone_number else None,
            tax_code=request.tax_code if request.tax_code else None,
            exclude_id=supplier.supplier_id,
        )

        if new_name is not None:
            supplier.supplier_name = new_name
        if request.phone_number is not None:
            supplier.phone_number = request.phone_number.strip() if request.phone_number else None
        if request.email is not None:
            supplier.email = request.email.strip() if request.email else None
        if request.address is not None:
            supplier.address = request.address.strip() if request.address else None
        if request.product_group is not None:
            supplier.product_group = request.product_group.strip() if request.product_group else None
        if request.tax_code is not None:
            supplier.tax_code = request.tax_code.strip() if request.tax_code else None
        if request.note is not None:
            supplier.note = request.note.strip() if request.note else None

        saved = SupplierRepository.update(supplier=supplier, db=db)
        return {
            "supplier_id": saved.supplier_id,
            "user_id": saved.user_id,
            "supplier_name": saved.supplier_name,
            "phone_number": saved.phone_number,
            "email": saved.email,
            "address": saved.address,
            "product_group": saved.product_group,
            "tax_code": saved.tax_code,
            "note": saved.note,
            "created_at": saved.created_at,
            "updated_at": saved.updated_at,
        }

    @staticmethod
    def delete_supplier(
        supplier_id: int,
        user_id: int,
        db: Session
    ) -> Dict[str, Any]:
        supplier = SupplierRepository.get_by_id_and_user(supplier_id=supplier_id, user_id=user_id, db=db)
        if not supplier:
            raise HTTPException(
                status_code=404,
                detail=f"Nhà cung cấp {supplier_id} không tồn tại hoặc không thuộc quyền quản lý"
            )

        if SupplierRepository.has_associated_records(supplier_id=supplier_id, user_id=user_id, db=db):
            raise HTTPException(
                status_code=400,
                detail="Không thể xóa nhà cung cấp đã phát sinh giao dịch hoặc công nợ"
            )

        SupplierRepository.delete(supplier=supplier, db=db)
        return {
            "success": True,
            "message": f"Đã xóa nhà cung cấp {supplier_id} thành công"
        }

    @staticmethod
    def get_supplier_debts(
        supplier_id: int,
        user_id: int,
        db: Session
    ) -> Dict[str, Any]:
        supplier = SupplierRepository.get_by_id_and_user(supplier_id=supplier_id, user_id=user_id, db=db)
        if not supplier:
            raise HTTPException(
                status_code=404,
                detail=f"Nhà cung cấp {supplier_id} không tồn tại hoặc không thuộc quyền quản lý"
            )

        summary = SupplierRepository.get_supplier_debt_summary(supplier_id=supplier_id, user_id=user_id, db=db)
        debts = SupplierRepository.get_supplier_debts_with_details(supplier_id=supplier_id, user_id=user_id, db=db)

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
                "customer": None,
                "supplier": {
                    "supplier_id": supplier.supplier_id,
                    "supplier_name": supplier.supplier_name,
                    "phone_number": supplier.phone_number,
                    "email": supplier.email,
                    "address": supplier.address,
                    "product_group": supplier.product_group,
                    "tax_code": supplier.tax_code,
                    "note": supplier.note,
                },
                "original_amount": orig,
                "paid_amount": paid,
                "remaining_debt": rem,
                "status": str(d.status),
                "transaction": tx_info,
                "created_at": d.created_at,
                "updated_at": d.updated_at,
                "supplier_id": supplier.supplier_id,
                "supplier_name": supplier.supplier_name,
            })

        return {
            "supplier": {
                "supplier_id": supplier.supplier_id,
                "supplier_name": supplier.supplier_name,
                "phone_number": supplier.phone_number,
                "email": supplier.email,
                "address": supplier.address,
                "product_group": supplier.product_group,
                "tax_code": supplier.tax_code,
                "note": supplier.note,
            },
            "debt_summary": summary,
            "debts": debt_items,
        }
