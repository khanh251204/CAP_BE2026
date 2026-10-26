from typing import Any
from decimal import Decimal

from app.configs.database import get_db_session
from app.models.customer_model import Customer
from app.services.account_service import AccountService
from app.repositories.debt_repository import DebtRepository
from app.ai.intents.missing_info import first_value
from .validator import validate
from .payload import build_payload


class ThuNoKhachHandler:
    """
    Business workflow cho intent: thu_no_khach / thu_no_khach_hang
    Xử lý:
    - Tìm khách hàng trong DB theo tên để lấy customer_id.
    - Tìm account_id bằng AccountService theo tên tài khoản hoặc phương thức thanh toán.
    - Kiểm tra các khoản nợ đang mở (status IN ('UNPAID', 'PARTIAL')) và kiểm tra số tiền thu.
    - Trả về waiting_confirmation để người dùng xác nhận.
    """

    async def handle(
        self,
        user_id: int,
        entities: dict[str, Any],
        text: str,
        intent: str = "thu_no_khach"
    ) -> dict:
        val_result = validate(entities, intent=intent)
        if not val_result["success"]:
            return {
                "success": False,
                "status": "need_information",
                "intent": intent,
                "missing_fields": val_result["missing_fields"],
                "message": val_result["message"]
            }

        customer_name = entities.get("customer") or entities.get("customer_name")
        if not customer_name:
            return {
                "success": False,
                "status": "need_information",
                "intent": intent,
                "missing_fields": ["customer"],
                "message": "Bạn chưa nói tên khách hàng cần thu nợ. Ví dụ: \"thu nợ chị Lan 300k\"."
            }

        raw_amount = first_value(entities.get("price"), entities.get("amount"), entities.get("total_price"))
        if raw_amount is None:
            return {
                "success": False,
                "status": "need_information",
                "intent": intent,
                "missing_fields": ["price"],
                "message": (
                    f"Bạn chưa nói số tiền thu nợ của {customer_name}. "
                    f"Ví dụ: \"thu nợ {customer_name} 300k\"."
                )
            }

        try:
            amount = float(raw_amount)
            if amount <= 0:
                raise ValueError()
        except (ValueError, TypeError):
            return {
                "success": False,
                "status": "invalid_amount",
                "intent": intent,
                "missing_fields": ["price"],
                "message": (
                    f"Số tiền thu nợ phải lớn hơn 0. Vui lòng nói lại số tiền {customer_name} trả. "
                    f"Ví dụ: \"thu nợ {customer_name} 300k\"."
                )
            }

        debt_id = entities.get("debt_id")
        customer_id = entities.get("customer_id")
        account_hint = (
            entities.get("account")
            or entities.get("account_name")
            or entities.get("payment")
        )

        db = get_db_session()
        try:
            # 1. Tìm customer_id nếu chưa có
            if not customer_id:
                db_customer = (
                    db.query(Customer)
                    .filter(
                        Customer.user_id == user_id,
                        Customer.customer_name.ilike(f"%{customer_name}%")
                    )
                    .first()
                )
                if not db_customer:
                    return {
                        "success": False,
                        "status": "customer_not_found",
                        "intent": intent,
                        "customer_name": customer_name,
                        "message": f"Không tìm thấy khách hàng '{customer_name}' trong hệ thống."
                    }
                customer_id = db_customer.customer_id
                customer_name = db_customer.customer_name

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

            # 3. Kiểm tra công nợ đang mở
            if debt_id:
                debt = DebtRepository.get_debt_by_id_and_user(
                    debt_id=int(debt_id),
                    user_id=user_id,
                    db=db,
                    direction="RECEIVABLE"
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
                if Decimal(str(amount)) > rem:
                    return {
                        "success": False,
                        "status": "overpayment",
                        "intent": intent,
                        "amount": amount,
                        "remaining_debt": float(rem),
                        "message": f"Số tiền thu ({amount:,.0f}đ) vượt quá số nợ còn lại ({float(rem):,.0f}đ) của khoản nợ #{debt_id}."
                    }
            else:
                open_debts = DebtRepository.get_open_debts_by_customer_and_user(
                    db=db,
                    customer_id=customer_id,
                    user_id=user_id,
                    direction="RECEIVABLE",
                )
                if not open_debts:
                    return {
                        "success": False,
                        "status": "no_open_debts",
                        "intent": intent,
                        "customer_name": customer_name,
                        "message": f"Khách hàng '{customer_name}' hiện không có khoản nợ nào đang mở."
                    }
                total_remaining = sum(
                    Decimal(str(d.remaining_debt if d.remaining_debt is not None else d.original_amount or 0))
                    for d in open_debts
                )
                if Decimal(str(amount)) > total_remaining:
                    return {
                        "success": False,
                        "status": "overpayment",
                        "intent": intent,
                        "amount": amount,
                        "total_remaining": float(total_remaining),
                        "message": (
                            f"Số tiền thu ({amount:,.0f}đ) vượt quá tổng số nợ hiện có "
                            f"({float(total_remaining):,.0f}đ) của khách hàng '{customer_name}'."
                        )
                    }

        finally:
            db.close()

        payload = build_payload(entities=entities, text=text)
        payload["customer_id"] = customer_id
        payload["customer_name"] = customer_name
        payload["account_id"] = account_id
        payload["account_name"] = account_name
        payload["amount"] = amount
        payload["total_amount"] = amount
        if debt_id:
            payload["debt_id"] = int(debt_id)

        return {
            "success": True,
            "status": "waiting_confirmation",
            "intent": intent,
            "action": "thu_no_khach_hang",
            "payload": payload,
            "message": (
                f"Bạn có chắc muốn thu nợ từ khách hàng {customer_name} "
                f"số tiền {amount:,.0f}đ vào tài khoản '{account_name}' không?"
            )
        }
