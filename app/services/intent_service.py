from sqlalchemy.orm import Session

from app.repositories.intent_repositories import IntentRepository


class IntentService:

    @staticmethod
    def get_intents(db: Session):
        return IntentRepository.get_intents(db)

    @staticmethod
    def get_intent(db: Session, intent_id: int):
        intent = IntentRepository.get_intent_by_id(
            db=db,
            intent_id=intent_id
        )

        if not intent:
            return None

        return intent