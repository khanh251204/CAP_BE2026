from sqlalchemy.orm import Session

from app.services.debt_service import DebtService


class DebtController:

    # ==========================================
    # GET ALL
    # ==========================================

    @staticmethod
    def get_all_debts(
        user_id: int,
        db: Session
    ):
        return DebtService.get_all_debts(
            user_id,
            db
        )


    # ==========================================
    # GET BY ID
    # ==========================================

    @staticmethod
    def get_debt_by_id(
        debt_id: int,
        db: Session
    ):
        return DebtService.get_debt_by_id(
            debt_id,
            db
        )


    # ==========================================
    # GET BY USER
    # ==========================================

    @staticmethod
    def get_debts_by_user_id(
        user_id: int,
        db: Session
    ):
        return DebtService.get_debts_by_user_id(
            user_id,
            db
        )


    # ==========================================
    # SEARCH
    # ==========================================

    @staticmethod
    def search_debts(
        name: str,
        db: Session
    ):
        return DebtService.search_by_name(
            name,
            db
        )


    # ==========================================
    # CREATE
    # ==========================================

    @staticmethod
    def create_debt(
        data: dict,
        db: Session
    ):
        return DebtService.create_debt(
            data,
            db
        )


    # ==========================================
    # UPDATE
    # ==========================================

    @staticmethod
    def update_debt(
        debt_id: int,
        data: dict,
        db: Session
    ):
        return DebtService.update_debt(
            debt_id,
            data,
            db
        )


    # ==========================================
    # DELETE
    # ==========================================

    @staticmethod
    def delete_debt(
        debt_id: int,
        db: Session
    ):
        return DebtService.delete_debt(
            debt_id,
            db
        )