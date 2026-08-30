from sqlalchemy.orm import Session

from app.models.inventory_model import InventoryTransaction


class InventoryRepository:

    @staticmethod
    def get_quantity_before(
        db: Session,
        user_id: int,
        product_id: int,
    ):
        """
        Lấy tồn kho hiện tại của product.
        """

        last_inventory = (
            db.query(InventoryTransaction)
            .filter(
                InventoryTransaction.user_id == user_id,
                InventoryTransaction.product_id == product_id,
            )
            .order_by(
                InventoryTransaction.inventory_transaction_id.desc()
            )
            .first()
        )

        return last_inventory

    @staticmethod
    def create_inventory(
        db: Session,
        user_id: int,
        product_id: int,
        transaction_id: int,
        quantity,
        unit: str,
        quantity_before,
        quantity_after,
        inventory_type: str,
        note: str,
    ):
        inventory = InventoryTransaction(
            user_id=user_id,
            product_id=product_id,
            transaction_id=transaction_id,
            type=inventory_type,
            quantity=quantity,
            unit=unit,
            quantity_before=quantity_before,
            quantity_after=quantity_after,
            note=note,
        )

        db.add(inventory)
        db.flush()

        return inventory