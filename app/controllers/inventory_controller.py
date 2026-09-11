from typing import Dict, Any
from sqlalchemy.orm import Session
from app.services.inventory_service import InventoryService
from app.services.websocket_manager import trigger_report_update


class InventoryController:
    @staticmethod
    def import_goods(db: Session, user_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        service = InventoryService(db)
        result = service.import_goods(user_id=user_id, payload=payload)
        if result.get("success"):
            try:
                trigger_report_update(user_id=user_id, affected=["inventory", "purchase"])
            except Exception:
                pass
        return result

    @staticmethod
    def sell_goods(db: Session, user_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        service = InventoryService(db)
        result = service.sell_goods(user_id=user_id, payload=payload)
        if result.get("success"):
            try:
                trigger_report_update(user_id=user_id, affected=["inventory", "sales", "profit"])
            except Exception:
                pass
        return result

    @staticmethod
    def check_stock(db: Session, user_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        service = InventoryService(db)
        return service.check_stock(user_id=user_id, payload=payload)