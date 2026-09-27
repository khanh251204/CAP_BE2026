"""
Account Service — Quản lý tài khoản thanh toán / ví tiền theo ERD.
Hỗ trợ tìm kiếm account_id theo tên chính xác, tên một phần, và từ khóa thông dụng.
"""

from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from app.models.account_model import Account
from app.repositories.account_repository import AccountRepository


# Bản đồ ánh xạ từ khóa phổ biến sang loại tài khoản (Account.account_type)
PAYMENT_TYPE_ALIASES = {
    # Tiền mặt
    "tiền mặt": "CASH",
    "tien mat": "CASH",
    "cash": "CASH",
    "tiền": "CASH",
    "tien": "CASH",

    # Ngân hàng / Chuyển khoản
    "chuyển khoản": "BANK",
    "chuyen khoan": "BANK",
    "ngân hàng": "BANK",
    "ngan hang": "BANK",
    "bank": "BANK",
    "ck": "BANK",
    "stk": "BANK",
    "vietcombank": "BANK",
    "vcb": "BANK",
    "mbbank": "BANK",
    "mb": "BANK",
    "techcombank": "BANK",
    "tcb": "BANK",
    "vietinbank": "BANK",
    "bidv": "BANK",
    "agribank": "BANK",
    "tpbank": "BANK",
    "acb": "BANK",
    "vpbank": "BANK",

    # Ví điện tử
    "momo": "E-WALLET",
    "ví momo": "E-WALLET",
    "vi momo": "E-WALLET",
    "zalopay": "E-WALLET",
    "zalo pay": "E-WALLET",
    "ví zalopay": "E-WALLET",
    "vi zalopay": "E-WALLET",
    "viettel money": "E-WALLET",
    "shopeepay": "E-WALLET",
    "ví điện tử": "E-WALLET",
    "vi dien tu": "E-WALLET",
    "ví": "E-WALLET",
    "vi": "E-WALLET",
}


class AccountService:

    # =========================================================
    # 1. TÌM ACCOUNT_ID THEO TÊN (HÀM CHÍNH)
    # =========================================================
    @staticmethod
    def get_account_id_by_name(
        db: Session,
        user_id: int,
        account_name: Optional[str],
        fallback_to_default: bool = False,
    ) -> Optional[int]:
        """
        Tìm account_id của người dùng theo tên tài khoản hoặc từ khóa thanh toán.

        Thứ tự ưu tiên tìm kiếm:
          1. Khớp chính xác tên tài khoản (không phân biệt hoa/thường).
          2. Khớp chuỗi con trong tên tài khoản (ilike).
          3. Khớp theo từ khóa / loại thanh toán ('tiền mặt', 'chuyển khoản', 'ngân hàng', 'momo', v.v.).
          4. Fallback (nếu fallback_to_default=True): lấy tài khoản CASH hoặc tài khoản đầu tiên của user.

        Trả về:
          int (account_id) nếu tìm thấy, hoặc None nếu không tìm thấy.
        """
        account = AccountService.get_account_by_name(
            db=db,
            user_id=user_id,
            account_name=account_name,
            fallback_to_default=fallback_to_default,
        )

        return account.account_id if account else None

    # =========================================================
    # 2. TÌM ĐỐI TƯỢNG ACCOUNT THEO TÊN
    # =========================================================
    @staticmethod
    def get_account_by_name(
        db: Session,
        user_id: int,
        account_name: Optional[str],
        fallback_to_default: bool = False,
    ) -> Optional[Account]:
        """
        Tìm bản ghi Account đầy đủ theo tên hoặc từ khóa.
        """
        if not account_name or not str(account_name).strip():
            if fallback_to_default:
                return AccountService.get_default_account(db=db, user_id=user_id)
            return None

        clean_name = str(account_name).strip().lower()

        # -----------------------------------------------------
        # Ưu tiên 1: Khớp chính xác tên tài khoản
        # -----------------------------------------------------
        account = AccountRepository.get_by_exact_name(
            db=db,
            user_id=user_id,
            name=clean_name,
        )
        if account:
            return account

        # -----------------------------------------------------
        # Ưu tiên 2: Khớp tên một phần (chứa trong tên)
        # -----------------------------------------------------
        account = AccountRepository.get_by_partial_name(
            db=db,
            user_id=user_id,
            name=clean_name,
        )
        if account:
            return account

        # -----------------------------------------------------
        # Ưu tiên 3: Khớp theo từ khóa / hình thức thanh toán
        # -----------------------------------------------------
        detected_type = None
        for keyword, acc_type in PAYMENT_TYPE_ALIASES.items():
            if keyword in clean_name or clean_name in keyword:
                detected_type = acc_type
                # Thử tìm tài khoản có tên chứa keyword trước
                acc_by_kw = AccountRepository.get_by_partial_name(
                    db=db,
                    user_id=user_id,
                    name=keyword,
                )
                if acc_by_kw:
                    return acc_by_kw
                break

        if detected_type:
            account = AccountRepository.get_by_type(
                db=db,
                user_id=user_id,
                account_type=detected_type,
            )
            if account:
                return account

        # -----------------------------------------------------
        # Ưu tiên 4: Fallback về tài khoản mặc định nếu cho phép
        # -----------------------------------------------------
        if fallback_to_default:
            return AccountService.get_default_account(db=db, user_id=user_id)

        return None

    # =========================================================
    # 3. LẤY TÀI KHOẢN MẶC ĐỊNH CỦA USER
    # =========================================================
    @staticmethod
    def get_default_account(
        db: Session,
        user_id: int
    ) -> Optional[Account]:
        """
        Lấy tài khoản mặc định của user (ưu tiên CASH, nếu không có thì lấy tài khoản đầu tiên).
        """
        # 1. Tìm tài khoản CASH
        cash_account = AccountRepository.get_by_type(
            db=db,
            user_id=user_id,
            account_type="CASH",
        )
        if cash_account:
            return cash_account

        # 2. Lấy tài khoản đầu tiên bất kỳ đang active
        all_accounts = AccountRepository.get_all_by_user(db=db, user_id=user_id)
        if all_accounts:
            return all_accounts[0]

        return None

    # =========================================================
    # 4. LẤY TÀI KHOẢN THEO ID
    # =========================================================
    @staticmethod
    def get_account_by_id(
        db: Session,
        user_id: int,
        account_id: int
    ) -> Optional[Account]:
        """
        Lấy tài khoản theo ID và kiểm tra quyền sở hữu của user.
        """
        return AccountRepository.get_by_id_and_user(
            db=db,
            account_id=account_id,
            user_id=user_id,
        )

    # =========================================================
    # 5. TÌM KIẾM DANH SÁCH TÀI KHOẢN
    # =========================================================
    @staticmethod
    def search_accounts(
        db: Session,
        user_id: int,
        name: str
    ) -> List[Dict[str, Any]]:
        """
        Tìm kiếm danh sách tài khoản theo từ khóa, trả về dạng dictionary.
        """
        accounts = AccountRepository.search_by_name(
            db=db,
            user_id=user_id,
            name=name,
        )

        return [
            {
                "account_id": acc.account_id,
                "account_name": acc.account_name,
                "account_type": acc.account_type,
                "balance": float(acc.balance) if acc.balance is not None else 0.0,
                "currency": acc.currency,
                "is_active": acc.is_active,
            }
            for acc in accounts
        ]

    # =========================================================
    # 6. TÌM HOẶC TỰ TẠO TÀI KHOẢN NẾU CHƯA CÓ
    # =========================================================
    @staticmethod
    def get_or_create_account_by_name(
        db: Session,
        user_id: int,
        account_name: str,
        account_type: Optional[str] = None,
        initial_balance: float = 0.0,
    ) -> Account:
        """
        Tìm tài khoản theo tên; nếu chưa có thì tự động tạo tài khoản mới.
        """
        account = AccountService.get_account_by_name(
            db=db,
            user_id=user_id,
            account_name=account_name,
            fallback_to_default=False,
        )

        if account:
            return account

        # Tự suy luận account_type nếu chưa truyền
        final_type = account_type
        if not final_type:
            clean = account_name.strip().lower()
            final_type = PAYMENT_TYPE_ALIASES.get(clean, "CASH")

        return AccountRepository.create(
            db=db,
            user_id=user_id,
            account_name=account_name.strip(),
            account_type=final_type,
            balance=initial_balance,
            currency="VND",
        )
