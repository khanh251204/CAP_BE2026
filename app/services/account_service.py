from app.repositories.account_repositories import AccountRepository


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