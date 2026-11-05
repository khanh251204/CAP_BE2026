from app.models.user_model import User
from app.models.store_model import Store
from app.models.role_permission_model import Role, Permission, role_permissions
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
from app.models.closing_period_model import ClosingPeriod
from app.models.closing_transaction_model import ClosingTransaction
from app.models.closing_setting_model import ClosingSetting
from app.models.closing_report_model import ClosingReport
from app.models.system_log_model import SystemLog
from app.models.user_correction_model import UserCorrection
from app.models.user_pending_confirmation_model import UserPendingConfirmation
from app.models.bom_model import BillOfMaterial
from app.models.product_unit_model import ProductUnit
from app.models.audit_log_model import AuditLog
from app.models.app_setting_model import AppSetting

__all__ = [
    "User",
    "Store",
    "Role",
    "Permission",
    "role_permissions",
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
    "ClosingPeriod",
    "ClosingTransaction",
    "ClosingSetting",
    "ClosingReport",
    "SystemLog",
    "UserCorrection",
    "UserPendingConfirmation",
    "BillOfMaterial",
    "ProductUnit",
    "AuditLog",
    "AppSetting",
]
from app.models.user_lock_history_model import UserLockHistory

# Ghi vết (Audit Log) mọi thay đổi giao dịch: gắn sự kiện ORM sau khi mọi model đã nạp
from app.services.audit_service import register_audit_listeners  # noqa: E402

register_audit_listeners()
