from sqlalchemy.orm import Session
import unicodedata

from app.repositories.intent_repositories import IntentRepository


class IntentService:

    # ==========================================================
    # INTENT GROUPS
    # ==========================================================

    SALES_INTENTS = {
        "ban_hang",
    }

    PURCHASE_INTENTS = {
        "nhap_hang",
    }

    MONEY_IN_INTENTS = {
        "thu_tien",
        "thu_no_phai_thu",
        "thu_no_khach_hang",
    }

    MONEY_OUT_INTENTS = {
        "chi_tien",
        "hang_hong",
        "hoan_tien",
        "tra_no_cung_cap",
        "tra_no_phai_tra",
        "tra_no_nha_cung_cap",
    }

    RECEIVABLE_DEBT_INTENTS = {
        "ghi_no_phai_thu",
        "ghi_no_khach_hang",
    }

    PAYABLE_DEBT_INTENTS = {
        "ghi_no_phai_tra",
        "ghi_no_nha_cung_cap",
    }

    DEBT_INTENTS = (
        RECEIVABLE_DEBT_INTENTS
        | PAYABLE_DEBT_INTENTS
    )

    # ==========================================================
    # NORMALIZE INTENT
    # ==========================================================

    @staticmethod
    def remove_accents(text: str) -> str:
        text = unicodedata.normalize("NFD", text)

        return "".join(
            c
            for c in text
            if unicodedata.category(c) != "Mn"
        )

    @staticmethod
    def normalize_intent(intent: str) -> str:

        if intent is None:
            raise ValueError(
                "Không xác định được intent"
            )

        intent = str(intent).strip().lower()

        if not intent:
            raise ValueError(
                "Không xác định được intent"
            )

        intent = IntentService.remove_accents(
            intent
        )

        # Chuẩn hóa khoảng trắng
        intent = "_".join(
            intent.split()
        )

        return intent

    # ==========================================================
    # GET ALL INTENTS
    # ==========================================================

    @staticmethod
    def get_intents(
        db: Session,
    ):
        return IntentRepository.get_intents(
            db=db
        )

    # ==========================================================
    # GET INTENT BY ID
    # ==========================================================

    @staticmethod
    def get_intent(
        db: Session,
        intent_id: int,
    ):

        return IntentRepository.get_intent_by_id(
            db=db,
            intent_id=intent_id
        )

    # ==========================================================
    # GET INTENT BY NAME
    # ==========================================================

    @staticmethod
    def get_intent_by_name(
        db: Session,
        intent_name: str,
    ):

        intent_name = (
            IntentService.normalize_intent(
                intent_name
            )
        )

        return IntentRepository.get_intent_by_name(
            db=db,
            name_intent=intent_name
        )

    # ==========================================================
    # GET INTENT GROUP
    # ==========================================================

    @staticmethod
    def get_intent_group(
        intent_name: str,
    ) -> str:
        """
        Xác định nhóm nghiệp vụ của intent.

        SALES
        PURCHASE
        MONEY_IN
        MONEY_OUT
        RECEIVABLE_DEBT
        PAYABLE_DEBT
        DEBT
        UNKNOWN
        """

        intent_name = (
            IntentService.normalize_intent(
                intent_name
            )
        )

        if intent_name in IntentService.SALES_INTENTS:
            return "SALES"

        if intent_name in IntentService.PURCHASE_INTENTS:
            return "PURCHASE"

        if intent_name in IntentService.MONEY_IN_INTENTS:
            return "MONEY_IN"

        if intent_name in IntentService.MONEY_OUT_INTENTS:
            return "MONEY_OUT"

        if intent_name in IntentService.RECEIVABLE_DEBT_INTENTS:
            return "RECEIVABLE_DEBT"

        if intent_name in IntentService.PAYABLE_DEBT_INTENTS:
            return "PAYABLE_DEBT"

        return "UNKNOWN"

    # ==========================================================
    # CHECK INTENT
    # ==========================================================

    @staticmethod
    def is_sales_intent(
        intent_name: str,
    ) -> bool:

        return (
            IntentService.get_intent_group(
                intent_name
            )
            == "SALES"
        )

    @staticmethod
    def is_purchase_intent(
        intent_name: str,
    ) -> bool:

        return (
            IntentService.get_intent_group(
                intent_name
            )
            == "PURCHASE"
        )

    @staticmethod
    def is_money_in_intent(
        intent_name: str,
    ) -> bool:

        return (
            IntentService.get_intent_group(
                intent_name
            )
            == "MONEY_IN"
        )

    @staticmethod
    def is_money_out_intent(
        intent_name: str,
    ) -> bool:

        return (
            IntentService.get_intent_group(
                intent_name
            )
            == "MONEY_OUT"
        )

    @staticmethod
    def is_receivable_debt_intent(
        intent_name: str,
    ) -> bool:

        return (
            IntentService.get_intent_group(
                intent_name
            )
            == "RECEIVABLE_DEBT"
        )

    @staticmethod
    def is_payable_debt_intent(
        intent_name: str,
    ) -> bool:

        return (
            IntentService.get_intent_group(
                intent_name
            )
            == "PAYABLE_DEBT"
        )

    @staticmethod
    def is_debt_intent(
        intent_name: str,
    ) -> bool:

        return (
            IntentService.get_intent_group(
                intent_name
            )
            in {
                "RECEIVABLE_DEBT",
                "PAYABLE_DEBT",
            }
        )