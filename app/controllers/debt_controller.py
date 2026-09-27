# app/controllers/debt_controller.py
# Facade controller aggregating customer debt, supplier debt, and debt query controllers.

from app.controllers.debt.customer_debt_controller import CustomerDebtController
from app.controllers.debt.supplier_debt_controller import SupplierDebtController
from app.controllers.debt.debt_query_controller import DebtQueryController


class DebtController(
    CustomerDebtController,
    SupplierDebtController,
    DebtQueryController
):
    """
    Facade controller for Debt operations.
    Delegates customer debt, supplier debt, and query operations.
    100% backward compatible with existing calls.
    """
    pass


__all__ = ["DebtController"]
