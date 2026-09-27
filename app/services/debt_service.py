from app.services.debt.debt_helper import (
    DebtHelperMixin,
    _get_intent_id,
    INTENT_ALIASES,
)
from app.services.debt.customer_debt_service import CustomerDebtMixin
from app.services.debt.customer_fifo_service import CustomerFifoMixin
from app.services.debt.supplier_debt_service import SupplierDebtMixin
from app.services.debt.supplier_fifo_service import SupplierFifoMixin
from app.services.debt.debt_query_service import DebtQueryMixin
from app.services.debt.debt_payment_exact_service import DebtPaymentExactMixin
from app.services.debt.debt_transaction_service import DebtTransactionMixin


class DebtService(
    DebtHelperMixin,
    CustomerDebtMixin,
    CustomerFifoMixin,
    SupplierDebtMixin,
    SupplierFifoMixin,
    DebtQueryMixin,
    DebtPaymentExactMixin,
    DebtTransactionMixin,
):
    """
    Debt Service Facade — Quản lý công nợ khách hàng & nhà cung cấp theo ERD.
    Kế thừa đầy đủ toàn bộ nghiệp vụ từ các module con.
    """
    pass


__all__ = [
    "DebtService",
    "_get_intent_id",
    "INTENT_ALIASES",
]