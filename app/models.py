"""
Alias module for app.models to ensure backwards compatibility
for any imports referencing `app.models` as a module file.
"""
from app.models import (
    User,
    Product,
    Intent,
    Category,
    Account,
    Customer,
    Supplier,
    Transaction,
    TransactionDetail,
    InventoryTransaction,
    Debt,
    DebtPayment,
    VoiceRecord,
    RefreshToken,
    OTPCode,
    ClosingPeriod,
    ClosingTransaction,
    ClosingSetting,
    ClosingReport,
    SystemLog,
    UserCorrection,
    __all__,
)
