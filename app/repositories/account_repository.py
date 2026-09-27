from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.account_model import Account


class AccountRepository:
    """
    Repository truy vấn và quản lý bảng Account theo chuẩn ERD.
    """

    @staticmethod
    def get_by_id_and_user(
        db: Session,
        account_id: int,
        user_id: int
    ) -> Optional[Account]:
        """
        Lấy tài khoản theo account_id và user_id (chỉ lấy tài khoản đang kích hoạt).
        """
        return (
            db.query(Account)
            .filter(
                Account.account_id == account_id,
                Account.user_id == user_id,
                Account.is_active == True,
            )
            .first()
        )

    @staticmethod
    def get_by_exact_name(
        db: Session,
        user_id: int,
        name: str
    ) -> Optional[Account]:
        """
        Tìm tài khoản theo tên chính xác (không phân biệt hoa thường, đã trim khoảng trắng).
        """
        clean_name = name.strip().lower()
        return (
            db.query(Account)
            .filter(
                Account.user_id == user_id,
                func.lower(func.trim(Account.account_name)) == clean_name,
                Account.is_active == True,
            )
            .first()
        )

    @staticmethod
    def get_by_partial_name(
        db: Session,
        user_id: int,
        name: str
    ) -> Optional[Account]:
        """
        Tìm tài khoản đầu tiên có tên chứa chuỗi tìm kiếm (không phân biệt hoa thường).
        """
        clean_name = name.strip()
        return (
            db.query(Account)
            .filter(
                Account.user_id == user_id,
                Account.account_name.ilike(f"%{clean_name}%"),
                Account.is_active == True,
            )
            .first()
        )

    @staticmethod
    def search_by_name(
        db: Session,
        user_id: int,
        name: str
    ) -> List[Account]:
        """
        Tìm danh sách tất cả các tài khoản có tên chứa chuỗi tìm kiếm.
        """
        clean_name = name.strip()
        return (
            db.query(Account)
            .filter(
                Account.user_id == user_id,
                Account.account_name.ilike(f"%{clean_name}%"),
                Account.is_active == True,
            )
            .order_by(Account.account_id.asc())
            .all()
        )

    @staticmethod
    def get_by_type(
        db: Session,
        user_id: int,
        account_type: str
    ) -> Optional[Account]:
        """
        Lấy tài khoản theo loại tài khoản ('CASH', 'BANK', 'E-WALLET').
        """
        return (
            db.query(Account)
            .filter(
                Account.user_id == user_id,
                Account.account_type == account_type.upper(),
                Account.is_active == True,
            )
            .first()
        )

    @staticmethod
    def get_all_by_user(
        db: Session,
        user_id: int
    ) -> List[Account]:
        """
        Lấy tất cả tài khoản đang hoạt động của người dùng.
        """
        return (
            db.query(Account)
            .filter(
                Account.user_id == user_id,
                Account.is_active == True,
            )
            .order_by(Account.account_id.asc())
            .all()
        )

    @staticmethod
    def create(
        db: Session,
        user_id: int,
        account_name: str,
        account_type: str = "CASH",
        balance: float = 0.0,
        currency: str = "VND",
    ) -> Account:
        """
        Tạo mới tài khoản cho user.
        """
        account = Account(
            user_id=user_id,
            account_name=account_name.strip(),
            account_type=account_type.upper(),
            balance=Decimal(str(balance)),
            currency=currency,
            is_active=True,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        db.add(account)
        db.commit()
        db.refresh(account)
        return account
