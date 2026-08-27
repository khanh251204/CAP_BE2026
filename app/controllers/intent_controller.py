from sqlalchemy.orm import Session

from app.services.intent_service import IntentService


class IntentController:

    @staticmethod
    def get_intents(db: Session):
        return IntentService.get_intents(db)

    @staticmethod
    def get_intent(db: Session, intent_id: int):
        return IntentService.get_intent(
            db=db,
            intent_id=intent_id
        )