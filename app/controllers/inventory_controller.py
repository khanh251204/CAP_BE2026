from typing import Dict, Any
from sqlalchemy.orm import Session
from app.services.inventory_service import InventoryService


class InventoryController:
    @staticmethod
    def import_goods(db: Session, user_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        service = InventoryService(db)
        return service.import_goods(user_id=user_id, payload=payload)

    @staticmethod
    def sell_goods(db: Session, user_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        service = InventoryService(db)
        return service.sell_goods(user_id=user_id, payload=payload)

    @staticmethod
    def check_stock(db: Session, user_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        service = InventoryService(db)
        return service.check_stock(user_id=user_id, payload=payload)