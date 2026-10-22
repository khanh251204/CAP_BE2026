from typing import Dict, Any, Union
from sqlalchemy.orm import Session
from app.services.inventory_service import InventoryService
from app.services.websocket_manager import trigger_report_update
from app.schemas.inventory_schema import (
    InventoryImportRequest,
    InventorySellRequest,
    InventoryCheckStockRequest,
)


class InventoryController:
    @staticmethod
    def import_goods(db: Session, user_id: int, payload: Union[InventoryImportRequest, Dict[str, Any]]) -> Dict[str, Any]:
        payload_dict = payload.model_dump(exclude_unset=True) if hasattr(payload, "model_dump") else (payload.dict(exclude_unset=True) if hasattr(payload, "dict") else dict(payload))
        service = InventoryService(db)
        result = service.import_goods(user_id=user_id, payload=payload_dict)
        if result.get("success"):
            try:
                trigger_report_update(user_id=user_id, affected=["inventory", "purchase"])
            except Exception:
                pass
        return result

    @staticmethod
    def sell_goods(db: Session, user_id: int, payload: Union[InventorySellRequest, Dict[str, Any]]) -> Dict[str, Any]:
        payload_dict = payload.model_dump(exclude_unset=True) if hasattr(payload, "model_dump") else (payload.dict(exclude_unset=True) if hasattr(payload, "dict") else dict(payload))
        service = InventoryService(db)
        result = service.sell_goods(user_id=user_id, payload=payload_dict)
        if result.get("success"):
            try:
                trigger_report_update(user_id=user_id, affected=["inventory", "sales", "profit"])
            except Exception:
                pass
        return result

    @staticmethod
    def check_stock(db: Session, user_id: int, payload: Union[InventoryCheckStockRequest, Dict[str, Any]]) -> Dict[str, Any]:
        payload_dict = payload.model_dump(exclude_unset=True) if hasattr(payload, "model_dump") else (payload.dict(exclude_unset=True) if hasattr(payload, "dict") else dict(payload))
        service = InventoryService(db)
        return service.check_stock(user_id=user_id, payload=payload_dict)