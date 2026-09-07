import json
from typing import Any, Dict

from app.configs.database import SessionLocal
from app.services.inventory_service import InventoryService


class InventoryTools:

    # =========================================================
    # NHẬP HÀNG
    # =========================================================

    @staticmethod
    def import_inventory(
        user_id: int,
        payload: Dict[str, Any]
    ) -> str:
        """
        Nhập hàng vào kho.
        Type: IN
        """

        db = SessionLocal()

        try:

            service = InventoryService(db)

            result = service.process_import(
                user_id=user_id,
                payload=payload
            )

            return json.dumps(
                result,
                ensure_ascii=False
            )

        except Exception as e:

            db.rollback()

            return json.dumps(
                {
                    "success": False,
                    "message": "Có lỗi xảy ra khi nhập hàng vào kho",
                    "error": str(e)
                },
                ensure_ascii=False
            )

        finally:

            db.close()

    # =========================================================
    # BÁN HÀNG / XUẤT KHO
    # =========================================================

    @staticmethod
    def export_inventory(
        user_id: int,
        payload: Dict[str, Any]
    ) -> str:
        """
        Bán hàng / xuất kho.
        Type: OUT
        """

        db = SessionLocal()

        try:

            service = InventoryService(db)

            result = service.sell_goods(
                user_id=user_id,
                payload=payload
            )

            return json.dumps(
                result,
                ensure_ascii=False
            )

        except Exception as e:

            db.rollback()

            return json.dumps(
                {
                    "success": False,
                    "message": "Có lỗi xảy ra khi xuất kho / bán hàng",
                    "error": str(e)
                },
                ensure_ascii=False
            )

        finally:

            db.close()

    # =========================================================
    # KIỂM KHO
    # =========================================================


    @staticmethod
    
    @staticmethod
    def check_stock(
        user_id: int,
        payload: dict
    ) -> str:
        """
        MCP tool:
        Kiểm tra tồn kho sản phẩm.
        """

        db = SessionLocal()

        try:

            service = InventoryService(db)

            result = service.check_stock(
                user_id=user_id,
                payload=payload
            )

            return json.dumps(
                result,
                ensure_ascii=False
            )

        except Exception as e:

            db.rollback()

            return json.dumps(
                {
                    "status": "error",
                    "success": False,
                    "message": "Có lỗi xảy ra khi kiểm tra tồn kho.",
                    "error": str(e)
                },
                ensure_ascii=False
            )

        finally:

            db.close()
