from decimal import Decimal
from sqlalchemy.orm import Session

from app.repositories.inventory_respositories import InventoryRepository

class InventoryService:

    @staticmethod
    def get_quantity_before(
        db: Session,
        user_id: int,
        product_id: int,
    ) -> Decimal:
        """
        Lấy tồn kho hiện tại của product.
        """

        last_inventory = InventoryRepository.get_quantity_before(
            db=db,
            user_id=user_id,
            product_id=product_id,
        )

        if not last_inventory:
            return Decimal("0")

        return Decimal(
            str(last_inventory.quantity_after)
        )

    @staticmethod
    def validate_sale_quantity(
        quantity_before: Decimal,
        quantity: Decimal,
        product_name: str,
    ) -> Decimal:
        """
        Kiểm tra đủ tồn kho để bán.
        """

        quantity_before = Decimal(str(quantity_before))
        quantity = Decimal(str(quantity))

        if quantity_before <= 0:
            raise ValueError(
                f"Sản phẩm '{product_name}' không đủ tồn kho"
            )

        if quantity_before < quantity:
            raise ValueError(
                f"Sản phẩm '{product_name}' không đủ tồn kho. "
                f"Tồn kho hiện tại: {quantity_before}, "
                f"số lượng cần bán: {quantity}"
            )

        quantity_after = quantity_before - quantity

        if quantity_after < 0:
            raise ValueError(
                f"Sản phẩm '{product_name}' không đủ tồn kho"
            )

        return quantity_after

    @staticmethod
    def create_sale_inventory(
        db: Session,
        user_id: int,
        product_id: int,
        transaction_id: int,
        quantity: Decimal,
        unit: str,
        quantity_before: Decimal,
        quantity_after: Decimal,
    ):

        return InventoryRepository.create_inventory(
            db=db,
            user_id=user_id,
            product_id=product_id,
            transaction_id=transaction_id,
            quantity=quantity,
            unit=unit,
            quantity_before=quantity_before,
            quantity_after=quantity_after,
            inventory_type="OUT",
            note="Xuất kho do bán hàng",
        )