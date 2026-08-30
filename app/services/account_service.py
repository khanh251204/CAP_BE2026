from app.repositories.account_repositories import AccountRepository
from decimal import Decimal
from sqlalchemy.orm import Session


class AccountService:

    @staticmethod
    def get_accounts(
        db,
        user_id: int
    ):
        return AccountRepository.get_accounts_by_user_id(
            db=db,
            user_id=user_id
        )

    @staticmethod
    def get_account_by_payment(
        db: Session,
        user_id: int,
        payment_method: str | None,
    ):
        """
        Mapping payment -> account type

        tiền mặt       -> CASH
        chuyển khoản   -> BANK
        ngân hàng      -> BANK
        momo           -> E-WALLET
        ví điện tử     -> E-WALLET
        zalopay        -> E-WALLET
        """

        if not payment_method:
            raise ValueError(
                "Phải có phương thức thanh toán"
            )

        payment = (
            str(payment_method)
            .lower()
            .strip()
        )

        if "tiền mặt" in payment:
            account_type = "CASH"

        elif (
            "chuyển khoản" in payment
            or "ngân hàng" in payment
        ):
            account_type = "BANK"

        elif (
            "momo" in payment
            or "ví" in payment
            or "zalopay" in payment
        ):
            account_type = "E-WALLET"

        else:
            raise ValueError(
                f"Không xác định được loại tài khoản từ payment: "
                f"{payment_method}"
            )

        account = AccountRepository.get_account_by_type(
            db=db,
            user_id=user_id,
            account_type=account_type
        )

        if not account:
            raise ValueError(
                f"Không tìm thấy tài khoản loại '{account_type}'"
            )

        return account

    @staticmethod
    def increase_balance(
        account,
        amount: Decimal,
    ):
        """
        Bán hàng -> tiền vào account
        """

        if amount is None:
            return account

        amount = Decimal(str(amount))

        account.balance += amount

        return account