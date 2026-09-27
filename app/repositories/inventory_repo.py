# app/repositories/inventory_repo.py
# Facade repository combining stock, mutation, and lookup operations for inventory domain.

from sqlalchemy.orm import Session
from app.repositories.inventory.inventory_stock_repo import InventoryStockRepository
from app.repositories.inventory.inventory_mutation_repo import InventoryMutationRepository
from app.repositories.inventory.inventory_lookup_repo import InventoryLookupRepository


class InventoryRepository(
    InventoryStockRepository,
    InventoryMutationRepository,
    InventoryLookupRepository
):
    """
    Facade repository for Inventory operations.
    Inherits stock history, mutation, and party/product lookup methods.
    100% backward compatible with existing calls.
    """
    def __init__(self, db: Session):
        self.db = db


__all__ = ["InventoryRepository"]