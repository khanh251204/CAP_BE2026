from sqlalchemy.orm import Session

from app.models.intent_model import Intent


class IntentRepository:

    @staticmethod
    def get_intents(db: Session):
        return (
            db.query(Intent)
            .order_by(Intent.intent_id.asc())
            .all()
        )

    @staticmethod
    def get_intent_by_id(db: Session, intent_id: int):
        return (
            db.query(Intent)
            .filter(Intent.intent_id == intent_id)
            .first()
        )