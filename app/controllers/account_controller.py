from app.services.account_service import AccountService


class AccountController:

    @staticmethod
    def get_accounts(
        db,
        user_id: int
    ):
        return AccountService.get_accounts(
            db=db,
            user_id=user_id
        )