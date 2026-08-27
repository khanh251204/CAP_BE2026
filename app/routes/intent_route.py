from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.configs.database import get_db
from app.controllers.intent_controller import IntentController


router = APIRouter()


@router.get("/intents")
def get_intents(
    db: Session = Depends(get_db)
):
    return IntentController.get_intents(db)

@router.get("/intent/{intent_id}")
def get_intent(
    intent_id: int,
    db: Session = Depends(get_db)
):
    intent = IntentController.get_intent(
        db=db,
        intent_id=intent_id
    )

    if not intent:
        raise HTTPException(
            status_code=404,
            detail="Intent không tồn tại"
        )

    return {
        "success": True,
        "data": intent
    }