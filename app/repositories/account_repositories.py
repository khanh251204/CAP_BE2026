from sqlalchemy.orm import Session

from app.models.account_model import Account


class AccountRepository:

    @staticmethod
    def get_accounts_by_user_id(
        db: Session,
        user_id: int
    ):
        return (
            db.query(Account)
            .filter(
                Account.user_id == user_id
            )
            .order_by(Account.account_id.asc())
            .all()
        )