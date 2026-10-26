import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import or_
from fastapi import HTTPException, status

from app.models.transaction_model import Transaction
from app.models.category_model import Category
from app.models.intent_model import Intent
from app.models.account_model import Account
from app.services.websocket_manager import ws_manager

logger = logging.getLogger(__name__)

# Từ khóa ánh xạ nhanh các danh mục chi phí phổ biến
COMMON_EXPENSE_KEYWORDS = {
    "điện": "Chi phí điện",
    "tiền điện": "Chi phí điện",
    "nước": "Chi phí nước",
    "tiền nước": "Chi phí nước",
    "mặt bằng": "Chi phí thuê mặt bằng",
    "tiền nhà": "Chi phí thuê mặt bằng",
    "thuê nhà": "Chi phí thuê mặt bằng",
    "thuê mặt bằng": "Chi phí thuê mặt bằng",
    "vận chuyển": "Chi phí vận chuyển",
    "ship": "Chi phí vận chuyển",
    "tiền ship": "Chi phí vận chuyển",
    "xăng": "Chi phí khác",
    "xăng xe": "Chi phí khác",
}


class ExpenseService:
    """
    Expense Service — Quản lý và ghi nhận chi phí hoạt động cho cửa hàng:
    - Tìm kiếm hoặc tự động ánh xạ Category loại EXPENSE
    - Tạo Transaction với intent chi_tien / chi_phi
    - Cập nhật số dư tài khoản Account (nếu PAID)
    - Kích hoạt WebSocket REPORT_UPDATED để UI/báo cáo tự động làm mới
    """

    @classmethod
    def list_expense_categories(cls, db: Session, user_id: int) -> List[Category]:
        """Danh mục chi (EXPENSE) user được dùng: của chính user + danh mục hệ thống."""
        return db.query(Category).filter(
            Category.category_type == "EXPENSE",
            or_(Category.user_id == user_id, Category.user_id == None),
        ).order_by(Category.user_id.is_(None), Category.category_id).all()

    @staticmethod
    def _norm(text: Optional[str]) -> str:
        t = " ".join(str(text or "").lower().split())
        for prefix in ("chi phí ", "tiền ", "trả tiền ", "thanh toán "):
            if t.startswith(prefix):
                t = t[len(prefix):]
        return t.strip()

    @classmethod
    def match_category(
        cls,
        db: Session,
        user_id: int,
        category_name: Optional[str] = None,
        category_id: Optional[int] = None,
    ) -> Optional[Category]:
        """
        Tìm danh mục chi phù hợp, KHÔNG tạo mới (dùng được ở bước bản nháp):
        1. Theo category_id (chỉ danh mục của user hoặc hệ thống)
        2. Theo tên: từ khóa phổ biến ("tiền điện" -> "Chi phí điện"), rồi so khớp tên
        3. Danh mục "Chi phí khác"
        """
        categories = cls.list_expense_categories(db, user_id)

        if category_id:
            for cat in categories:
                if cat.category_id == int(category_id):
                    return cat

        clean_name = str(category_name or "").strip().lower()
        if clean_name:
            target_name = next(
                (mapped for kw, mapped in COMMON_EXPENSE_KEYWORDS.items() if kw in clean_name), None
            )
            wanted = [cls._norm(n) for n in (target_name, clean_name) if n]
            # Khớp đúng tên trước, rồi tới chứa nhau ("internet" ~ "Chi phí internet")
            for cat in categories:
                if cls._norm(cat.category_name) in wanted:
                    return cat
            for cat in categories:
                name = cls._norm(cat.category_name)
                if name and any(w and (w in name or name in w) for w in wanted):
                    return cat

        return next((c for c in categories if "chi phí khác" in c.category_name.lower()), None)

    @classmethod
    def resolve_category(
        cls,
        db: Session,
        user_id: int,
        category_name: Optional[str] = None,
        category_id: Optional[int] = None
    ) -> Optional[Category]:
        """Như match_category; không có danh mục nào phù hợp thì tạo mới cho user."""
        cat = cls.match_category(db, user_id, category_name=category_name, category_id=category_id)
        if cat:
            return cat

        new_cat = Category(
            user_id=user_id,
            category_name=category_name or "Chi phí khác",
            category_type="EXPENSE",
            created_at=datetime.now()
        )
        db.add(new_cat)
        db.flush()
        return new_cat

    @classmethod
    def get_intent_id(cls, db: Session) -> Optional[int]:
        """
        Lấy intent_id cho chi phí: ưu tiên 'chi_tien' hoặc 'chi_phi'.
        """
        for name in ["chi_tien", "chi_phi"]:
            intent = db.query(Intent).filter(Intent.intent_name == name).first()
            if intent:
                return intent.intent_id
        
        # Fallback theo intent_type EXPENSE
        intent = db.query(Intent).filter(Intent.intent_type == "EXPENSE").first()
        return intent.intent_id if intent else None

    @classmethod
    def get_default_account(cls, db: Session, user_id: int, account_id: Optional[int] = None) -> Optional[Account]:
        """
        Lấy tài khoản nguồn chi tiền (tiền mặt / tài khoản ngân hàng).
        """
        if account_id:
            acc = db.query(Account).filter(Account.account_id == account_id, Account.user_id == user_id).first()
            if acc:
                return acc

        # Ưu tiên tài khoản chính (is_active) hoặc tài khoản đầu tiên của user
        return db.query(Account).filter(
            Account.user_id == user_id,
            Account.is_active == True
        ).first() or db.query(Account).filter(Account.user_id == user_id).first()

    @classmethod
    def create_expense(
        cls,
        db: Session,
        user_id: int,
        amount: float,
        category_name: Optional[str] = None,
        category_id: Optional[int] = None,
        account_id: Optional[int] = None,
        note: Optional[str] = None,
        payment_status: Optional[str] = "PAID",
        transaction_date: Optional[datetime] = None,
        input_text: Optional[str] = None,
        input_method: Optional[str] = "MANUAL",
    ) -> Dict[str, Any]:
        """
        Tạo giao dịch ghi nhận chi phí.
        """
        amount_dec = Decimal(str(amount))
        if amount_dec <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Số tiền chi phí phải lớn hơn 0"
            )

        category = cls.resolve_category(db, user_id, category_name=category_name, category_id=category_id)
        intent_id = cls.get_intent_id(db)
        account = cls.get_default_account(db, user_id, account_id=account_id)

        status_clean = (payment_status or "PAID").upper()
        if status_clean not in ["PAID", "PENDING", "PARTIAL"]:
            status_clean = "PAID"

        raw_method = (input_method or "MANUAL").upper().strip()
        method_clean = raw_method if raw_method in {"VOICE", "MANUAL"} else "MANUAL"

        tx_date = transaction_date or datetime.now()

        # Quy tắc chốt sổ: không ghi chi phí mới vào kỳ đã chốt
        from app.services.closing.closing_guard import assert_date_open
        assert_date_open(db, user_id, tx_date)

        # Tạo Transaction
        tx = Transaction(
            user_id=user_id,
            intent_id=intent_id,
            category_id=category.category_id if category else None,
            account_id=account.account_id if account else None,
            customer_id=None,
            supplier_id=None,
            total_amount=amount_dec,
            payment_status=status_clean,
            input_method=method_clean,
            input_text=input_text or note or f"Chi phí: {category.category_name if category else 'Khác'}",
            note=note or (category.category_name if category else "Chi phí"),
            transaction_date=tx_date,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        db.add(tx)
        db.flush()

        # Trừ tiền tài khoản nếu đã thanh toán
        if status_clean == "PAID" and account:
            curr_balance = Decimal(str(account.balance or 0))
            account.balance = curr_balance - amount_dec
            account.updated_at = datetime.now()

        db.commit()
        db.refresh(tx)

        # Trigger Realtime WebSocket Report Notification
        try:
            from app.services.websocket_manager import trigger_report_update
            trigger_report_update(
                user_id=user_id,
                transaction_id=tx.transaction_id,
                affected=["expense", "cash_flow", "balance"]
            )
        except Exception as e:
            logger.warning(f"Failed to push websocket event for expense: {e}")

        return {
            "success": True,
            "status": "success",
            "transaction_id": tx.transaction_id,
            "category_id": category.category_id if category else None,
            "category_name": category.category_name if category else "Chi phí khác",
            "amount": float(tx.total_amount),
            "payment_status": tx.payment_status,
            "account_id": tx.account_id,
            "account_name": account.account_name if account else None,
            "transaction_date": tx.transaction_date.isoformat() if tx.transaction_date else None,
            "note": tx.note,
            "message": f"Đã ghi nhận chi phí '{category.category_name if category else 'Khác'}' số tiền {float(amount_dec):,.0f}đ thành công."
        }
