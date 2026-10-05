from typing import Any
from decimal import Decimal

from app.configs.database import get_db_session
from app.models.supplier_model import Supplier
from app.services.account_service import AccountService
from app.repositories.debt_repository import DebtRepository
from .validator import validate
from .payload import build_payload


class TraNoNhaCungCapHandler:
    """
    Business workflow cho intent: tra_no_nha_cung_cap (hoặc thu_no_nha_cung_cap, tra_no_ncc)
    Xử lý:
    - Tìm nhà cung cấp trong DB theo tên để lấy supplier_id.
    - Tìm account_id nguồn trích tiền bằng AccountService (mặc định tiền mặt).
    - Kiểm tra các khoản nợ PAYABLE đang mở (status IN ('UNPAID', 'PARTIAL')).
    - Hỗ trợ nói 'trả hết'/'tất toán' -> amount = remaining_debt.
    - Trả về waiting_confirmation để người dùng xác nhận.
    """

    async def handle(
        self,
        user_id: int,
        entities: dict[str, Any],
        text: str,
        intent: str = "tra_no_nha_cung_cap"
    ) -> dict:
        val_result = validate(entities)
        if not val_result["success"]:
            return {
                "success": False,
                "status": "need_information",
                "intent": intent,
                "missing_fields": val_result["missing_fields"],
                "message": val_result["message"]
            }

        supplier_name = entities.get("supplier") or entities.get("supplier_name")
        if not supplier_name:
            return {
                "success": False,
                "status": "need_information",
                "intent": intent,
                "missing_fields": ["supplier"],
                "message": "Thiếu thông tin nhà cung cấp cần trả nợ"
            }

        raw_amount = (
            entities.get("price")
            or entities.get("amount")
            or entities.get("total_price")
        )

        debt_id = entities.get("debt_id")
        supplier_id = entities.get("supplier_id")
        account_hint = (
            entities.get("account")
            or entities.get("account_name")
            or entities.get("payment")
        )

        is_settle_all = any(
            k in text.lower()
            for k in ("tất toán", "tat toan", "trả hết", "tra het", "thanh toán hết", "toàn bộ", "hết nợ", "trả sạch")
        )
        if raw_amount is None and not is_settle_all and not debt_id:
            return {
                "success": False,
                "status": "need_information",
                "intent": intent,
                "missing_fields": ["price"],
                "message": "Thiếu thông tin số tiền cần trả nợ"
            }

        db = get_db_session()
        try:
            # 1. Tìm supplier_id nếu chưa có
            if not supplier_id:
                db_supplier = (
                    db.query(Supplier)
                    .filter(
                        Supplier.user_id == user_id,
                        Supplier.supplier_name.ilike(f"%{supplier_name}%")
                    )
                    .first()
                )
                if not db_supplier:
                    return {
                        "success": False,
                        "status": "supplier_not_found",
                        "intent": intent,
                        "supplier_name": supplier_name,
                        "message": f"Không tìm thấy nhà cung cấp '{supplier_name}' trong hệ thống."
                    }
                supplier_id = db_supplier.supplier_id
                supplier_name = db_supplier.supplier_name

            # 2. Tìm account_id bằng AccountService
            account = AccountService.get_account_by_name(
                db=db,
                user_id=user_id,
                account_name=account_hint,
                fallback_to_default=True,
            )
            if not account:
                account = AccountService.get_or_create_account_by_name(
                    db=db,
                    user_id=user_id,
                    account_name="Tiền mặt",
                    account_type="CASH",
                )
            account_id = account.account_id
            account_name = account.account_name

            # 3. Kiểm tra công nợ PAYABLE đang mở
            if debt_id:
                debt = DebtRepository.get_debt_by_id_and_user(
                    debt_id=int(debt_id),
                    user_id=user_id,
                    db=db,
                    direction="PAYABLE"
                )
                if not debt:
                    return {
                        "success": False,
                        "status": "debt_not_found",
                        "intent": intent,
                        "debt_id": debt_id,
                        "message": f"Khoản nợ #{debt_id} không tồn tại hoặc không thuộc về bạn."
                    }
                rem = Decimal(str(debt.remaining_debt if debt.remaining_debt is not None else debt.original_amount))
                if raw_amount is None:
                    amount = float(rem)
                else:
                    try:
                        amount = float(raw_amount)
                        if amount <= 0:
                            raise ValueError()
                    except (ValueError, TypeError):
                        return {
                            "success": False,
                            "status": "invalid_amount",
                            "intent": intent,
                            "message": "Số tiền trả nợ phải lớn hơn 0"
                        }
                    if Decimal(str(amount)) > rem:
                        return {
                            "success": False,
                            "status": "overpayment",
                            "intent": intent,
                            "amount": amount,
                            "remaining_debt": float(rem),
                            "message": f"Số tiền trả ({amount:,.0f}đ) vượt quá số nợ còn lại ({float(rem):,.0f}đ) của khoản nợ #{debt_id}."
                        }
            else:
                open_debts = DebtRepository.get_open_debts_by_supplier_and_user(
                    db=db,
                    supplier_id=supplier_id,
                    user_id=user_id,
                    direction="PAYABLE",
                )
                if not open_debts:
                    return {
                        "success": False,
                        "status": "no_open_debts",
                        "intent": intent,
                        "supplier_name": supplier_name,
                        "message": f"Nhà cung cấp '{supplier_name}' hiện không có khoản nợ nào cần trả."
                    }
                total_remaining = sum(
                    Decimal(str(d.remaining_debt if d.remaining_debt is not None else d.original_amount or 0))
                    for d in open_debts
                )
                if raw_amount is None:
                    amount = float(total_remaining)
                else:
                    try:
                        amount = float(raw_amount)
                        if amount <= 0:
                            raise ValueError()
                    except (ValueError, TypeError):
                        return {
                            "success": False,
                            "status": "invalid_amount",
                            "intent": intent,
                            "message": "Số tiền trả nợ phải lớn hơn 0"
                        }
                    if Decimal(str(amount)) > total_remaining:
                        return {
                            "success": False,
                            "status": "overpayment",
                            "intent": intent,
                            "amount": amount,
                            "total_remaining": float(total_remaining),
                            "message": (
                                f"Số tiền trả ({amount:,.0f}đ) vượt quá tổng số nợ hiện có "
                                f"({float(total_remaining):,.0f}đ) của nhà cung cấp '{supplier_name}'."
                            )
                        }

        finally:
            db.close()

        payload = build_payload(entities=entities, text=text)
        payload["supplier_id"] = supplier_id
        payload["supplier_name"] = supplier_name
        payload["account_id"] = account_id
        payload["account_name"] = account_name
        payload["amount"] = amount
        if debt_id:
            payload["debt_id"] = int(debt_id)

        return {
            "success": True,
            "status": "waiting_confirmation",
            "intent": intent,
            "action": "thu_no_nha_cung_cap",
            "payload": payload,
            "message": (
                f"Bạn có chắc muốn trả nợ cho nhà cung cấp {supplier_name} "
                f"số tiền {amount:,.0f}đ từ tài khoản '{account_name}' không?"
            )
        }
