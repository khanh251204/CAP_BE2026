"""
Tập hợp toàn bộ 15 models/entities của hệ thống theo đặc tả erd.md.
Cho phép import trực tiếp từ `app.models` hoặc `app.models.py`.
"""

from app.models.user_model import User
from app.models.product_model import Product
from app.models.intent_model import Intent
from app.models.category_model import Category
from app.models.account_model import Account
from app.models.customer_model import Customer
from app.models.supplier_model import Supplier
from app.models.transaction_model import Transaction
from app.models.transactionDetail_model import TransactionDetail
from app.models.inventory_model import InventoryTransaction
from app.models.debt_model import Debt
from app.models.debt_payment_model import DebtPayment
from app.models.voice_record_model import VoiceRecord
from app.models.refresh_token_model import RefreshToken
from app.models.otp_model import OTPCode

__all__ = [
    "User",
    "Product",
    "Intent",
    "Category",
    "Account",
    "Customer",
    "Supplier",
    "Transaction",
    "TransactionDetail",
    "InventoryTransaction",
    "Debt",
    "DebtPayment",
    "VoiceRecord",
    "RefreshToken",
    "OTPCode",
]
