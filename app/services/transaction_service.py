from math import ceil
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc
from sqlalchemy.exc import SQLAlchemyError
from decimal import Decimal
from datetime import datetime, timedelta
import unicodedata
from typing import Optional, Dict, Any, List

from app.services.system_log_service import log_event

# IMPORT CÁC MODELS ĐỐI CHIẾU THEO docs/erd.md
from app.services.duplicate_guard import (
    find_duplicate_customer,
    find_duplicate_supplier,
    get_or_create_customer_by_name,
    get_or_create_supplier_by_name,
)
from app.models.transaction_model import Transaction
from app.models.transactionDetail_model import TransactionDetail
from app.models.customer_model import Customer
from app.models.supplier_model import Supplier
from app.models.account_model import Account
from app.models.intent_model import Intent
from app.models.category_model import Category
from app.models.product_model import Product
from app.models.inventory_model import InventoryTransaction
from app.models.debt_model import Debt

# IMPORT REPOSITORIES
from app.repositories.transaction_repository import TransactionRepository
from app.repositories.product_repository import (
    get_product_by_name,
    create_product
)
from app.schemas.transaction_schema import TransactionCreateRequest


# ==========================================================
# 10 INTENTS MAPPING THEO docs/erd.md:
# 1. mua_hang            -> EXPENSE
# 2. ban_hang            -> INCOME
# 3. ghi_no_nha_cung_cap -> DEBT
# 4. tra_no_cung_cap     -> DEBT
# 5. ghi_no_khach_hang   -> DEBT
# 6. thu_no_khach_hang   -> DEBT
# 7. chi_tien            -> EXPENSE
# 8. hang_hong           -> EXPENSE
# 9. kiem_kho            -> NONE
# 10. bao_cao            -> NONE
# ==========================================================
INTENT_TYPE_MAPPING = {
    "ban_hang": "INCOME",
    "mua_hang": "EXPENSE",
    "nhap_hang": "EXPENSE",
    "chi_tien": "EXPENSE",
    "hang_hong": "EXPENSE",
    "hoan_tien": "REFUND",
    "ghi_no_khach_hang": "DEBT",
    "ghi_no_phai_thu": "DEBT",
    "khach_ghi_no": "DEBT",
    "thu_no_khach_hang": "DEBT",
    "thu_no_phai_thu": "DEBT",
    "thu_no_khach": "DEBT",
    "ghi_no_nha_cung_cap": "DEBT",
    "ghi_no_cung_cap": "DEBT",
    "ghi_no_phai_tra": "DEBT",
    "ncc_ghi_no": "DEBT",
    "tra_no_cung_cap": "DEBT",
    "tra_no_nha_cung_cap": "DEBT",
    "tra_no_phai_tra": "DEBT",
    "tra_no_ncc": "DEBT",
    "thu_no_nha_cung_cap": "DEBT",
    "kiem_kho": "NONE",
    "bao_cao": "NONE",
    "chuyen_tien": "TRANFER",
}


def resolve_intent_type(intent_obj: Optional[Intent], intent_name: Optional[str] = None) -> Optional[str]:
    """
    Lấy intent_type từ Intent model theo ERD (INCOME, EXPENSE, DEBT, TRANFER, REFUND, NONE),
    hoặc suy diễn từ danh mục 10 intent theo docs/erd.md nếu intent_type trong DB bị null/chưa gán.
    """
    if intent_obj and intent_obj.intent_type:
        return str(intent_obj.intent_type)
    name = (intent_obj.intent_name if intent_obj else intent_name) or ""
    return INTENT_TYPE_MAPPING.get(name.lower().strip())


class TransactionService:

    @staticmethod
    def create_direct_transaction(
        db: Session,
        user_id: int,
        request: TransactionCreateRequest
    ) -> Dict[str, Any]:
        """
        Tạo Transaction trực tiếp theo đúng chuẩn Model và docs/erd.md:
        - Transaction: intent_id, category_id, account_id, customer_id, supplier_id,
                       total_amount, payment_status, input_method, input_text, note, transaction_date
        - Transaction_Detail (1-N): product_id, quantity, unit, unit_price, subtotal
        - Tự động cập nhật số dư Account nếu thanh toán thành công (PAID).
        """
        intent_id = request.intent_id
        category_id = request.category_id
        account_id = request.account_id

        intent = None
        if intent_id is not None:
            intent = db.query(Intent).filter(Intent.intent_id == intent_id).first()
            if not intent:
                raise ValueError(f"Không tìm thấy Intent với id {intent_id}")

        # TC_TX03_052: Giao dịch chi tiền (chi_tien) bắt buộc phải có category_id
        if intent and intent.intent_name == "chi_tien" and category_id is None:
            raise ValueError("Giao dịch chi tiền bắt buộc phải có danh mục (category_id)")

        # TC_TX03_053: Giao dịch chi tiền bắt buộc phải có account_id
        if intent and intent.intent_name == "chi_tien" and account_id is None:
            raise ValueError("Giao dịch chi tiền bắt buộc phải có tài khoản thanh toán (account_id)")

        # TC_TX03_054 & TC_TX03_058: Giao dịch chi tiền bắt buộc phải có total_amount > 0
        if intent and intent.intent_name == "chi_tien":
            if request.total_amount is None:
                raise ValueError("Giao dịch chi tiền bắt buộc phải có số tiền (total_amount)")
            try:
                chk_amt = Decimal(str(request.total_amount))
                if chk_amt <= 0:
                    raise ValueError("Số tiền giao dịch (total_amount) phải lớn hơn 0")
            except Exception as e:
                if "phải lớn hơn 0" in str(e):
                    raise
                raise ValueError("Số tiền giao dịch (total_amount) không hợp lệ")

        # 2. Kiểm tra category_id nếu được truyền
        category = None
        if category_id is not None:
            category = db.query(Category).filter(
                Category.category_id == category_id,
                (Category.user_id == user_id) | (Category.user_id.is_(None))
            ).first()
            if not category:
                raise ValueError(f"Không tìm thấy Category với id {category_id}")

        # 3. Kiểm tra account_id nếu được truyền
        account = None
        if account_id is not None:
            account = db.query(Account).filter(
                Account.account_id == account_id,
                Account.user_id == user_id
            ).first()
            if not account:
                raise ValueError(f"Không tìm thấy Account với id {account_id}")

        # 4. Kiểm tra customer_id nếu được truyền
        customer_id = request.customer_id
        if customer_id is not None:
            customer = db.query(Customer).filter(
                Customer.customer_id == customer_id,
                Customer.user_id == user_id
            ).first()
            if not customer:
                raise ValueError(f"Không tìm thấy Customer với id {customer_id}")

        # 5. Kiểm tra supplier_id nếu được truyền
        supplier_id = request.supplier_id
        if supplier_id is not None:
            supplier = db.query(Supplier).filter(
                Supplier.supplier_id == supplier_id,
                Supplier.user_id == user_id
            ).first()
            if not supplier:
                raise ValueError(f"Không tìm thấy Supplier với id {supplier_id}")

        # 6. Tính toán total_amount
        total_amount = Decimal(str(request.total_amount or 0))
        calculated_detail_total = Decimal("0.00")

        # Chuẩn hóa payment_status theo ERD: 'PAID', 'PARTIAL', 'PENDING'
        payment_status_valid = {"PAID", "PARTIAL", "PENDING"}
        raw_payment_status = (request.payment_status or "").upper().strip()
        if raw_payment_status in payment_status_valid:
            payment_status = raw_payment_status
        else:
            payment_status = "PAID" if account_id is not None else "PENDING"

        # Chuẩn hóa input_method theo ERD: 'VOICE', 'MANUAL'
        if getattr(request, "voice_id", None):
            input_method = "VOICE"
        else:
            raw_input_method = (request.input_method or "MANUAL").upper().strip()
            input_method = raw_input_method if raw_input_method in {"VOICE", "MANUAL"} else "MANUAL"

        transaction_date = request.transaction_date or datetime.now()

        # 7. Khởi tạo Transaction
        new_transaction = Transaction(
            user_id=user_id,
            intent_id=intent_id,
            category_id=category_id,
            account_id=account_id,
            customer_id=customer_id,
            supplier_id=supplier_id,
            total_amount=total_amount,
            payment_status=payment_status,
            input_method=input_method,
            input_text=request.input_text or request.text or "",
            note=request.note,
            transaction_date=transaction_date,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

        db.add(new_transaction)
        db.flush()

        # 8. Xử lý danh sách chi tiết (Transaction_Detail) nếu có
        saved_details = []
        if request.details:
            for item in request.details:
                prod = db.query(Product).filter(
                    Product.product_id == item.product_id,
                    Product.user_id == user_id
                ).first()
                if not prod:
                    raise ValueError(f"Không tìm thấy sản phẩm với id {item.product_id}")

                qty = Decimal(str(item.quantity))
                u_price = Decimal(str(item.unit_price))
                subtotal = Decimal(str(item.subtotal)) if item.subtotal is not None else (qty * u_price)
                calculated_detail_total += subtotal

                detail = TransactionDetail(
                    transaction_id=new_transaction.transaction_id,
                    product_id=prod.product_id,
                    product_name=item.product_name or prod.product_name,
                    quantity=qty,
                    unit=item.unit or prod.default_unit or "cái",
                    unit_price=u_price,
                    subtotal=subtotal
                )
                db.add(detail)
                saved_details.append(detail)

            db.flush()

            # Nếu total_amount ban đầu bằng 0 thì cập nhật theo tổng details
            if total_amount == 0 and calculated_detail_total > 0:
                total_amount = calculated_detail_total
                new_transaction.total_amount = total_amount

        # 9. Cập nhật số dư tài khoản nếu đã thanh toán (PAID) và có account
        if account and payment_status == "PAID":
            if category:
                if category.category_type == "INCOME":
                    account.balance += total_amount
                elif category.category_type == "EXPENSE":
                    account.balance -= total_amount
        try:
            db.commit()
            db.refresh(new_transaction)
        except SQLAlchemyError as exc:
            db.rollback()
            log_event(
                level="ERROR",
                step="DB",
                message=f"Database commit error in create_direct_transaction: {str(exc)}",
                detail={"error": str(exc), "error_type": type(exc).__name__, "user_id": user_id},
                user_id=user_id,
            )
            raise

        intent_name = intent.intent_name if intent else None
        resolved_type = resolve_intent_type(intent, intent_name)

        return {
            "transaction_id": new_transaction.transaction_id,
            "user_id": new_transaction.user_id,
            "intent_id": new_transaction.intent_id,
            "intent": intent_name,
            "intent_name": intent_name,
            "intent_type": resolved_type,
            "type": resolved_type,
            "category_id": new_transaction.category_id,
            "account_id": new_transaction.account_id,
            "customer_id": new_transaction.customer_id,
            "supplier_id": new_transaction.supplier_id,
            "total_amount": float(new_transaction.total_amount),
            "payment_status": new_transaction.payment_status,
            "input_method": new_transaction.input_method,
            "input_text": new_transaction.input_text,
            "note": new_transaction.note,
            "transaction_date": new_transaction.transaction_date.isoformat() if new_transaction.transaction_date else None,
            "created_at": new_transaction.created_at.isoformat() if new_transaction.created_at else None,
            "updated_at": new_transaction.updated_at.isoformat() if new_transaction.updated_at else None,
            "details_count": len(saved_details)
        }

    @staticmethod
    def save_groq_transaction(
        db: Session,
        user_id: int,
        account_id: int | None,
        groq_result: dict,
        input_method: Optional[str] = None
    ):
        # ==========================================================
        # 1. LẤY KẾT QUẢ GROQ
        # ==========================================================
        def remove_accents(text: str) -> str:
            text = unicodedata.normalize("NFD", text)
            return "".join(
                c for c in text
                if unicodedata.category(c) != "Mn"
            )

        analysis = groq_result.get("transaction_analysis", {})
        entities = analysis.get("entities", {})

        groq_intent = (
            analysis.get("intent", "")
            .lower()
            .strip()
        )

        if not groq_intent:
            raise ValueError("Không xác định được intent")

        groq_intent = remove_accents(groq_intent)
        groq_intent = groq_intent.replace(" ", "_")

        db_intent = (
            db.query(Intent)
            .filter(
                Intent.intent_name == groq_intent
            )
            .first()
        )

        if not db_intent:
            raise ValueError(f"Intent '{groq_intent}' không tồn tại trong hệ thống")

        intent_id = db_intent.intent_id

        # ==========================================================
        # 2. LẤY ENTITIES
        # ==========================================================
        product_name = entities.get("product")
        quantity = entities.get("quantity")
        price = entities.get("price")
        unit = entities.get("unit")

        payment_method = entities.get("payment")
        customer_name = entities.get("customer")
        supplier_name = entities.get("supplier")

        nlp_date = entities.get("date")

        # ==========================================================
        # 3. XỬ LÝ NGÀY
        # ==========================================================
        transaction_date = datetime.now()

        if nlp_date:
            date_text = str(nlp_date).lower().strip()
            if "hôm qua" in date_text:
                transaction_date = datetime.now() - timedelta(days=1)
            elif "hôm kia" in date_text:
                transaction_date = datetime.now() - timedelta(days=2)
            elif "ngày mai" in date_text:
                transaction_date = datetime.now() + timedelta(days=1)
            else:
                try:
                    transaction_date = datetime.fromisoformat(date_text[:10])
                except Exception:
                    pass

        # ==========================================================
        # 4. XÁC ĐỊNH LOẠI INTENT
        # ==========================================================
        SALES_INTENTS = {"ban_hang"}
        PURCHASE_INTENTS = {"nhap_hang", "mua_hang"}
        MONEY_IN_INTENTS = {"thu_tien", "thu_no_phai_thu", "thu_no_khach_hang"}
        MONEY_OUT_INTENTS = {"chi_tien", "hang_hong", "hoan_tien"}
        MONEY_OUT_DEBT_INTENTS = {"tra_no_phai_tra", "tra_no_nha_cung_cap"}
        RECEIVABLE_DEBT_INTENTS = {"ghi_no_phai_thu", "ghi_no_khach_hang"}
        PAYABLE_DEBT_INTENTS = {"ghi_no_phai_tra", "ghi_no_nha_cung_cap"}
        TRANSFER_INTENTS = {"chuyen_tien"}

        # ==========================================================
        # 5. VALIDATE THEO INTENT
        # ==========================================================
        if groq_intent in SALES_INTENTS:
            if not product_name:
                raise ValueError("Bán hàng phải có product")
            if not unit or not str(unit).strip():
                raise ValueError("Thiếu đơn vị tính (unit)")
            if quantity is None:
                raise ValueError("Bán hàng phải có quantity")
            if price is None:
                raise ValueError("Bán hàng phải có price")

        elif groq_intent in PURCHASE_INTENTS:
            if not product_name:
                raise ValueError("Nhập hàng phải có product")
            if not unit or not str(unit).strip():
                raise ValueError("Thiếu đơn vị tính (unit)")
            if quantity is None:
                raise ValueError("Nhập hàng phải có quantity")
            if price is None:
                raise ValueError("Nhập hàng phải có price")

        elif groq_intent in {"thu_no_phai_thu", "thu_no_khach_hang"}:
            if not customer_name:
                raise ValueError("Thu nợ khách hàng bắt buộc phải có khách hàng (customer)")
            if price is None:
                raise ValueError("Thu nợ khách hàng phải có số tiền (price/amount)")

        elif groq_intent in {"thu_tien"}:
            if price is None:
                raise ValueError("Thu tiền phải có amount")

        elif groq_intent in MONEY_OUT_INTENTS:
            if price is None:
                raise ValueError("Chi tiền phải có amount")

        elif groq_intent in MONEY_OUT_DEBT_INTENTS:
            if not supplier_name:
                raise ValueError("Phải có nhà cung cấp")
            if price is None:
                raise ValueError("Phải có giá tiền")

        elif groq_intent in RECEIVABLE_DEBT_INTENTS:
            if price is None:
                raise ValueError("Ghi nợ phải thu phải có amount")
            if not customer_name:
                raise ValueError("Ghi nợ phải thu phải có customer")
            # TC_TX03_013 & TC_TX03_014 & TC_TX03_015: Ghi nợ nếu có nhắc số lượng/unit thì bắt buộc phải có product, và ngược lại; có product bắt buộc có unit
            if (quantity is not None or unit is not None) and not product_name:
                raise ValueError("Giao dịch ghi nợ có số lượng hoặc đơn vị tính bắt buộc phải có sản phẩm (product)")
            if product_name and quantity is None:
                raise ValueError("Giao dịch ghi nợ có sản phẩm bắt buộc phải có số lượng (quantity)")
            if product_name and (not unit or not str(unit).strip()):
                raise ValueError("Thiếu đơn vị tính (unit)")

        elif groq_intent in PAYABLE_DEBT_INTENTS:
            if price is None:
                raise ValueError("Ghi nợ phải trả phải có amount")
            if not supplier_name:
                raise ValueError("Ghi nợ phải trả phải có supplier")
            # TC_TX03_038 & TC_TX03_039: Mua hàng nợ có nhắc sản phẩm thì bắt buộc có product, quantity, unit
            if (quantity is not None or unit is not None) and not product_name:
                raise ValueError("Giao dịch ghi nợ có số lượng hoặc đơn vị tính bắt buộc phải có sản phẩm (product)")
            if product_name and quantity is None:
                raise ValueError("Giao dịch ghi nợ có sản phẩm bắt buộc phải có số lượng (quantity)")
            if product_name and (not unit or not str(unit).strip()):
                raise ValueError("Thiếu đơn vị tính (unit)")

        # ==========================================================
        # 6. TÍNH TIỀN & VALIDATE SỐ LIỆU (TC_TX03_006, 007, 009, 025, 026)
        # ==========================================================
        try:
            total_amount = Decimal(str(price or 0))
        except Exception:
            raise ValueError("Giá tiền không hợp lệ")

        if total_amount <= 0:
            raise ValueError("Giá (price/amount) phải lớn hơn 0")

        try:
            qty = Decimal(str(quantity)) if quantity is not None else Decimal("1")
        except Exception:
            raise ValueError("Số lượng không hợp lệ")

        if quantity is not None and qty <= 0:
            raise ValueError("Số lượng (quantity) phải lớn hơn 0")

        unit_price = total_amount / qty if product_name and qty > 0 else Decimal("0.00")

        # ==========================================================
        # 7. XỬ LÝ ACCOUNT (đúng model Account & docs/erd.md: account_type, account_name)
        # ==========================================================
        db_account = None
        account_id = None

        is_pure_debt = groq_intent in [
            "ghi_no_phai_thu",
            "ghi_no_khach_hang",
            "ghi_no_phai_tra",
            "ghi_no_nha_cung_cap"
        ]

        if not is_pure_debt:
            acc_type = "CASH"
            if payment_method:
                payment_lower = str(payment_method).lower().strip()
                if "tiền mặt" in payment_lower:
                    acc_type = "CASH"
                elif "chuyển khoản" in payment_lower or "ngân hàng" in payment_lower:
                    acc_type = "BANK"
                elif "momo" in payment_lower or "ví" in payment_lower or "zalopay" in payment_lower:
                    acc_type = "E-WALLET"

            db_account = (
                db.query(Account)
                .filter(
                    Account.user_id == user_id,
                    Account.account_type == acc_type
                )
                .first()
            )

            if not db_account:
                db_account = Account(
                    user_id=user_id,
                    account_name=f"Tài khoản {acc_type}",
                    account_type=acc_type,
                    balance=Decimal("0.00"),
                    currency="VND",
                    is_active=True,
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                db.add(db_account)
                db.flush()

            account_id = db_account.account_id

        # ==========================================================
        # 8. CUSTOMER (đúng model Customer: customer_name, created_at, updated_at)
        # ==========================================================
        customer_id = None
        if customer_name:
            # So khớp đã chuẩn hóa (hoa/thường, khoảng trắng) để không tạo khách hàng trùng
            db_customer, _ = find_duplicate_customer(db, user_id, name=str(customer_name))

            # TC_TX03_062 & TC_TX03_065: Thu nợ khách hàng yêu cầu khách hàng phải tồn tại và có nợ cần thu
            if groq_intent in ("thu_no_khach_hang", "thu_no_phai_thu"):
                if not db_customer:
                    raise ValueError(f"Khách hàng '{customer_name}' không tồn tại")

                unpaid_debts = (
                    db.query(Debt)
                    .filter(
                        Debt.user_id == user_id,
                        Debt.customer_id == db_customer.customer_id,
                        Debt.direction == "RECEIVABLE",
                        Debt.status != "PAID"
                    )
                    .order_by(Debt.debt_id.asc())
                    .all()
                )
                if not unpaid_debts:
                    raise ValueError(f"Khách hàng '{customer_name}' không tồn tại khoản nợ nào cần thu")

                # Kiểm tra số tiền thu nợ không vượt quá số nợ còn lại của khoản nợ đầu tiên
                current_debt = unpaid_debts[0]
                if total_amount > current_debt.remaining_debt:
                    raise ValueError(f"Số tiền thu nợ ({total_amount}) vượt quá số nợ ({current_debt.remaining_debt})")

            elif not db_customer:
                db_customer = get_or_create_customer_by_name(db, user_id, str(customer_name))

            customer_id = db_customer.customer_id

        # ==========================================================
        # 9. SUPPLIER (đúng model Supplier: supplier_name, created_at, updated_at)
        # ==========================================================
        supplier_id = None
        if supplier_name:
            # So khớp đã chuẩn hóa (hoa/thường, khoảng trắng) để không tạo nhà cung cấp trùng
            db_supplier, _ = find_duplicate_supplier(db, user_id, name=str(supplier_name))

            # TC_TX03_069 & TC_TX03_072: Trả nợ nhà cung cấp yêu cầu nhà cung cấp phải tồn tại và có nợ cần trả
            if groq_intent in ("tra_no_nha_cung_cap", "tra_no_phai_tra"):
                if not db_supplier:
                    raise ValueError(f"Nhà cung cấp '{supplier_name}' không tồn tại")

                unpaid_debts = (
                    db.query(Debt)
                    .filter(
                        Debt.user_id == user_id,
                        Debt.supplier_id == db_supplier.supplier_id,
                        Debt.direction == "PAYABLE",
                        Debt.status != "PAID"
                    )
                    .order_by(Debt.debt_id.asc())
                    .all()
                )
                if not unpaid_debts:
                    raise ValueError(f"Nhà cung cấp '{supplier_name}' không tồn tại khoản nợ nào cần trả")

                # Kiểm tra số tiền trả nợ không vượt quá số nợ còn lại của khoản nợ đầu tiên
                current_debt = unpaid_debts[0]
                if total_amount > current_debt.remaining_debt:
                    raise ValueError(f"Số tiền trả nợ ({total_amount}) vượt quá số nợ ({current_debt.remaining_debt})")

            elif not db_supplier:
                db_supplier = get_or_create_supplier_by_name(db, user_id, str(supplier_name))

            supplier_id = db_supplier.supplier_id

        # ==========================================================
        # 10. PAYMENT STATUS (Chuẩn Enum ERD: 'PAID', 'PARTIAL', 'PENDING')
        # ==========================================================
        payment_status = "PENDING" if is_pure_debt else "PAID"

        # Xác định input_method chuẩn theo ERD: API thêm giao dịch là 'MANUAL', voice là 'VOICE'
        if input_method and str(input_method).upper().strip() in {"VOICE", "MANUAL"}:
            final_input_method = str(input_method).upper().strip()
        elif groq_result.get("input_method") and str(groq_result["input_method"]).upper().strip() in {"VOICE", "MANUAL"}:
            final_input_method = str(groq_result["input_method"]).upper().strip()
        elif analysis.get("input_method") and str(analysis["input_method"]).upper().strip() in {"VOICE", "MANUAL"}:
            final_input_method = str(analysis["input_method"]).upper().strip()
        else:
            final_input_method = "MANUAL"

        new_transaction = Transaction(
            user_id=user_id,
            intent_id=intent_id,
            account_id=account_id,
            customer_id=customer_id,
            supplier_id=supplier_id,
            total_amount=total_amount,
            payment_status=payment_status,
            input_method=final_input_method,
            input_text=analysis.get("text", ""),
            transaction_date=transaction_date,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

        db.add(new_transaction)
        db.flush()

        # ==========================================================
        # 12. PRODUCT + TRANSACTION DETAIL (đúng model Product: product_name, default_unit)
        # ==========================================================
        product = None
        if product_name:
            product = get_product_by_name(
                db=db,
                user_id=user_id,
                product_name=product_name
            )

            if not product:
                # TC_TX03_016: Luồng bán hàng (ban_hang, ghi_no_khach_hang) yêu cầu sản phẩm phải tồn tại trong kho, không tự tạo mới
                if groq_intent in ("ban_hang", "ghi_no_khach_hang", "ghi_no_phai_thu"):
                    raise ValueError(f"Sản phẩm '{product_name}' không tồn tại")

                product = create_product(
                    db=db,
                    user_id=user_id,
                    product_name=product_name,
                    unit=unit,
                    price=float(unit_price)
                )
                product.updated_at = datetime.now()
            else:
                # TC_TX03_010 & TC_TX03_035: Đơn vị tính gửi lên phải khớp với đơn vị tính đã lưu của sản phẩm
                ALL_ITEM_INTENTS = (
                    "ban_hang", "ghi_no_khach_hang", "ghi_no_phai_thu",
                    "mua_hang", "nhap_hang", "ghi_no_nha_cung_cap", "ghi_no_phai_tra"
                )
                if groq_intent in ALL_ITEM_INTENTS and unit and product.default_unit:
                    norm_req_unit = str(unit).strip().lower()
                    norm_prod_unit = str(product.default_unit).strip().lower()
                    if norm_req_unit != norm_prod_unit:
                        raise ValueError(f"Đơn vị tính '{unit}' không khớp với đơn vị tính của sản phẩm ('{product.default_unit}')")

                product.unit_price = str(unit_price)
                if unit:
                    product.default_unit = unit
                product.updated_at = datetime.now()
                db.flush()

            detail = TransactionDetail(
                transaction_id=new_transaction.transaction_id,
                product_id=product.product_id,
                product_name=product.product_name,
                quantity=qty,
                unit=unit or product.default_unit or "cái",
                unit_price=unit_price,
                subtotal=total_amount
            )
            db.add(detail)
            db.flush()

        # ==========================================================
        # 13. ACCOUNT BALANCE (cập nhật số dư đúng nghiệp vụ)
        # ==========================================================
        if db_account:
            if groq_intent in ("ban_hang", "thu_tien", "thu_no_phai_thu", "thu_no_khach_hang"):
                db_account.balance += total_amount
            elif groq_intent in ("nhap_hang", "mua_hang", "chi_tien", "tra_no_phai_tra", "tra_no_nha_cung_cap", "hoan_tien", "hang_hong"):
                db_account.balance -= total_amount
            db_account.updated_at = datetime.now()

        # ==========================================================
        # 14. INVENTORY TRANSACTION (đúng model InventoryTransaction: inventory_type)
        # ==========================================================
        inventory = None
        if product:
            last_inventory = (
                db.query(InventoryTransaction)
                .filter(
                    InventoryTransaction.user_id == user_id,
                    InventoryTransaction.product_id == product.product_id
                )
                .order_by(
                    InventoryTransaction.inventory_transaction_id.desc()
                )
                .first()
            )

            quantity_before = (
                last_inventory.quantity_after
                if last_inventory
                else Decimal("0.00")
            )

            if groq_intent in ["ban_hang", "ghi_no_phai_thu", "ghi_no_khach_hang"]:
                quantity_after = quantity_before - qty
                if quantity_after < 0:
                    raise ValueError(f"Sản phẩm '{product.product_name}' không đủ tồn kho")

                inventory = InventoryTransaction(
                    user_id=user_id,
                    product_id=product.product_id,
                    transaction_id=new_transaction.transaction_id,
                    inventory_type="OUT",
                    quantity=qty,
                    unit=unit or product.default_unit,
                    quantity_before=quantity_before,
                    quantity_after=quantity_after,
                    note="Xuất kho do bán hàng",
                    created_at=datetime.now()
                )
                db.add(inventory)

            elif groq_intent in ["nhap_hang", "mua_hang", "ghi_no_phai_tra", "ghi_no_nha_cung_cap"]:
                quantity_after = quantity_before + qty
                inventory = InventoryTransaction(
                    user_id=user_id,
                    product_id=product.product_id,
                    transaction_id=new_transaction.transaction_id,
                    inventory_type="IN",
                    quantity=qty,
                    unit=unit or product.default_unit,
                    quantity_before=quantity_before,
                    quantity_after=quantity_after,
                    note="Nhập kho từ giao dịch nhập hàng",
                    created_at=datetime.now()
                )
                db.add(inventory)

            db.flush()

        # ==========================================================
        # 15. TẠO DEBT (đúng model Debt: remaining_debt, status theo ERD)
        # ==========================================================
        debt = None
        if groq_intent in ("ghi_no_khach_hang", "ghi_no_phai_thu"):
            if not customer_id:
                raise ValueError("Phải có thông tin khách hàng để ghi nợ")
            debt = Debt(
                transaction_id=new_transaction.transaction_id,
                user_id=user_id,
                customer_id=customer_id,
                supplier_id=None,
                direction="RECEIVABLE",
                original_amount=total_amount,
                remaining_debt=total_amount,
                status="UNPAID",
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            db.add(debt)

        elif groq_intent in ("ghi_no_nha_cung_cap", "ghi_no_phai_tra"):
            if not supplier_id:
                raise ValueError("Phải có thông tin nhà cung cấp để ghi nợ")
            debt = Debt(
                transaction_id=new_transaction.transaction_id,
                user_id=user_id,
                customer_id=None,
                supplier_id=supplier_id,
                direction="PAYABLE",
                original_amount=total_amount,
                remaining_debt=total_amount,
                status="UNPAID",
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            db.add(debt)

        elif groq_intent in ("thu_no_khach_hang", "thu_no_phai_thu"):
            # Cập nhật trừ nợ cho khoản nợ cần thu
            target_debt = (
                db.query(Debt)
                .filter(
                    Debt.user_id == user_id,
                    Debt.customer_id == customer_id,
                    Debt.direction == "RECEIVABLE",
                    Debt.status != "PAID"
                )
                .order_by(Debt.debt_id.asc())
                .first()
            )
            if target_debt:
                applied = min(total_amount, target_debt.remaining_debt)
                orig = Decimal(str(target_debt.original_amount or 0))
                pct = ((applied / orig * 100).quantize(Decimal("0.01")) if orig > 0 else Decimal("0.00"))
                try:
                    from app.models.debt_payment_model import DebtPayment
                    dp = DebtPayment(
                        debt_id=target_debt.debt_id,
                        transaction_id=new_transaction.transaction_id,
                        account_id=account_id or (db_account.account_id if db_account else None),
                        amount=applied,
                        payment_percentage=pct,
                        payment_date=transaction_date or datetime.now(),
                        note=f"Thu nợ từ khách hàng {customer_name}",
                        created_at=datetime.now()
                    )
                    db.add(dp)
                except Exception:
                    pass
                target_debt.remaining_debt -= applied
                target_debt.status = "PAID" if target_debt.remaining_debt == 0 else "PARTIAL"
                target_debt.updated_at = datetime.now()

        elif groq_intent in ("tra_no_nha_cung_cap", "tra_no_phai_tra"):
            # Cập nhật trừ nợ cho khoản nợ cần trả
            target_debt = (
                db.query(Debt)
                .filter(
                    Debt.user_id == user_id,
                    Debt.supplier_id == supplier_id,
                    Debt.direction == "PAYABLE",
                    Debt.status != "PAID"
                )
                .order_by(Debt.debt_id.asc())
                .first()
            )
            if target_debt:
                applied = min(total_amount, target_debt.remaining_debt)
                orig = Decimal(str(target_debt.original_amount or 0))
                pct = ((applied / orig * 100).quantize(Decimal("0.01")) if orig > 0 else Decimal("0.00"))
                try:
                    from app.models.debt_payment_model import DebtPayment
                    dp = DebtPayment(
                        debt_id=target_debt.debt_id,
                        transaction_id=new_transaction.transaction_id,
                        account_id=account_id or (db_account.account_id if db_account else None),
                        amount=applied,
                        payment_percentage=pct,
                        payment_date=transaction_date or datetime.now(),
                        note=f"Trả nợ cho nhà cung cấp {supplier_name}",
                        created_at=datetime.now()
                    )
                    db.add(dp)
                except Exception:
                    pass
                target_debt.remaining_debt -= applied
                target_debt.status = "PAID" if target_debt.remaining_debt == 0 else "PARTIAL"
                target_debt.updated_at = datetime.now()

        try:
            db.flush()
            db.commit()
            db.refresh(new_transaction)
        except SQLAlchemyError as exc:
            db.rollback()
            log_event(
                level="ERROR",
                step="DB",
                message=f"Database commit error in save_groq_transaction: {str(exc)}",
                detail={"error": str(exc), "error_type": type(exc).__name__, "intent": groq_intent, "user_id": user_id},
                user_id=user_id,
            )
            raise

        # Kích hoạt cảnh báo tồn kho nếu xuất kho bán hàng làm tồn kho hết hoặc dưới min_quantity
        if product and inventory and getattr(inventory, "inventory_type", None) == "OUT":
            try:
                from app.services.stock_alert_service import StockAlertService
                StockAlertService.check_and_notify_stock(
                    db=db,
                    user_id=user_id,
                    product_id=product.product_id,
                    current_stock=inventory.quantity_after
                )
            except Exception as alert_err:
                logger.warning(f"[StockAlert] Không thể gửi cảnh báo tồn kho: {alert_err}")

        # ==========================================================
        # 16. RETURN
        # ==========================================================
        intent_name = db_intent.intent_name if db_intent else groq_intent
        resolved_type = resolve_intent_type(db_intent, intent_name)

        return {
            "transaction_id": new_transaction.transaction_id,
            "user_id": user_id,
            "intent_id": intent_id,
            "intent": intent_name,
            "intent_name": intent_name,
            "intent_type": resolved_type,
            "type": resolved_type,
            "account_id": account_id,
            "customer_id": customer_id,
            "supplier_id": supplier_id,
            "product_id": product.product_id if product else None,
            "inventory_transaction_id": inventory.inventory_transaction_id if inventory else None,
            "debt_id": debt.debt_id if debt else None,
            "quantity": float(qty) if product else None,
            "unit": unit or (product.default_unit if product else None),
            "unit_price": float(unit_price) if product else None,
            "total_amount": float(total_amount),
            "payment_status": new_transaction.payment_status,
            "input_method": new_transaction.input_method,
            "input_text": analysis.get("text", ""),
            "transaction_date": transaction_date.isoformat() if transaction_date else None,
            "created_at": new_transaction.created_at.isoformat() if new_transaction.created_at else None,
            "updated_at": new_transaction.updated_at.isoformat() if new_transaction.updated_at else None
        }

    # ==========================================================
    # GET LIST TRANSACTIONS (đúng tên trường theo docs/erd.md)
    # ==========================================================
    @staticmethod
    def get_transactions(
        db: Session,
        user_id: int,
        page: int = 1,
        limit: int = 20,
        intent_type: Optional[str] = None,
        intent_name: Optional[str] = None,
    ):
        transactions, total = TransactionRepository.get_transactions(
            db=db,
            user_id=user_id,
            page=page,
            limit=limit,
            intent_type=intent_type,
            intent_name=intent_name,
        )

        total_pages = ceil(total / limit) if limit > 0 else 0
        data = []

        for transaction in transactions:
            details = []
            # Duyệt qua transaction_detail
            raw_details = transaction.transaction_detail if transaction.transaction_detail else []
            for detail in raw_details:
                prod = detail.product
                resolved_prod_name = detail.product_name or (prod.product_name if prod else "Sản phẩm không xác định")
                details.append({
                    "detail_id": detail.detail_id,
                    "quantity": float(detail.quantity) if detail.quantity is not None else 0.0,
                    "unit": detail.unit,
                    "unit_price": float(detail.unit_price) if detail.unit_price is not None else 0.0,
                    "subtotal": float(detail.subtotal) if detail.subtotal is not None else 0.0,
                    "product_id": detail.product_id,
                    "product_name": resolved_prod_name,
                    "image": prod.img if prod else None,
                    "product": (
                        {
                            "product_id": prod.product_id,
                            "product_name": resolved_prod_name,
                            "name": resolved_prod_name,
                            "image": prod.img
                        }
                        if prod
                        else None
                    )
                })

            item_intent_name = transaction.intent.intent_name if transaction.intent else None
            resolved_type = resolve_intent_type(transaction.intent, item_intent_name)

            data.append({
                "transaction_id": transaction.transaction_id,
                "user_id": transaction.user_id,
                "intent_id": transaction.intent_id,
                "category_id": transaction.category_id,
                "account_id": transaction.account_id,
                "customer_id": transaction.customer_id,
                "supplier_id": transaction.supplier_id,
                "intent": item_intent_name,
                "intent_name": item_intent_name,
                "intent_type": resolved_type,
                "type": resolved_type,
                "account": (
                    {
                        "account_id": transaction.account.account_id,
                        "account_name": transaction.account.account_name,
                        "name": transaction.account.account_name,
                        "account_type": transaction.account.account_type
                    }
                    if transaction.account
                    else None
                ),
                "customer": (
                    {
                        "customer_id": transaction.customer.customer_id,
                        "customer_name": transaction.customer.customer_name,
                        "name": transaction.customer.customer_name
                    }
                    if transaction.customer
                    else None
                ),
                "supplier": (
                    {
                        "supplier_id": transaction.supplier.supplier_id,
                        "supplier_name": transaction.supplier.supplier_name,
                        "name": transaction.supplier.supplier_name
                    }
                    if transaction.supplier
                    else None
                ),
                "total_amount": float(transaction.total_amount) if transaction.total_amount is not None else 0.0,
                "payment_status": transaction.payment_status,
                "input_method": transaction.input_method,
                "input_text": transaction.input_text,
                "note": transaction.note,
                "transaction_date": (
                    transaction.transaction_date.isoformat()
                    if transaction.transaction_date
                    else None
                ),
                "created_at": (
                    transaction.created_at.isoformat()
                    if transaction.created_at
                    else None
                ),
                "updated_at": (
                    transaction.updated_at.isoformat()
                    if transaction.updated_at
                    else None
                ),
                "details": details
            })

        return {
            "items": data,
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": total_pages
        }

    # ==========================================================
    # GET TRANSACTION BY ID (đúng tên trường theo docs/erd.md)
    # ==========================================================
    @staticmethod
    def get_transaction_by_id(
        db: Session,
        user_id: int,
        transaction_id: int
    ):
        transaction = TransactionRepository.get_transaction_by_id(
            db=db,
            user_id=user_id,
            transaction_id=transaction_id
        )

        if not transaction:
            return None

        details = []
        raw_details = transaction.transaction_detail if transaction.transaction_detail else []
        for detail in raw_details:
            prod = detail.product
            resolved_prod_name = detail.product_name or (prod.product_name if prod else "Sản phẩm không xác định")
            details.append({
                "detail_id": detail.detail_id,
                "product_id": detail.product_id,
                "product_name": resolved_prod_name,
                "image": prod.img if prod else None,
                "quantity": float(detail.quantity) if detail.quantity is not None else 0.0,
                "unit": detail.unit,
                "unit_price": float(detail.unit_price) if detail.unit_price is not None else 0.0,
                "subtotal": float(detail.subtotal) if detail.subtotal is not None else 0.0,
                "product": (
                    {
                        "product_id": prod.product_id,
                        "product_name": resolved_prod_name,
                        "name": resolved_prod_name,
                        "image": prod.img
                    }
                    if prod
                    else None
                )
            })

        item_intent_name = transaction.intent.intent_name if transaction.intent else None
        resolved_type = resolve_intent_type(transaction.intent, item_intent_name)

        return {
            "transaction_id": transaction.transaction_id,
            "user_id": transaction.user_id,
            "intent_id": transaction.intent_id,
            "category_id": transaction.category_id,
            "account_id": transaction.account_id,
            "customer_id": transaction.customer_id,
            "supplier_id": transaction.supplier_id,
            "intent": item_intent_name,
            "intent_name": item_intent_name,
            "intent_type": resolved_type,
            "type": resolved_type,
            "account": (
                {
                    "account_id": transaction.account.account_id,
                    "account_name": transaction.account.account_name,
                    "name": transaction.account.account_name,
                    "account_type": transaction.account.account_type
                }
                if transaction.account
                else None
            ),
            "customer": (
                {
                    "customer_id": transaction.customer.customer_id,
                    "customer_name": transaction.customer.customer_name,
                    "name": transaction.customer.customer_name
                }
                if transaction.customer
                else None
            ),
            "supplier": (
                {
                    "supplier_id": transaction.supplier.supplier_id,
                    "supplier_name": transaction.supplier.supplier_name,
                    "name": transaction.supplier.supplier_name
                }
                if transaction.supplier
                else None
            ),
            "total_amount": float(transaction.total_amount) if transaction.total_amount is not None else 0.0,
            "payment_status": transaction.payment_status,
            "input_method": transaction.input_method,
            "input_text": transaction.input_text,
            "note": transaction.note,
            "transaction_date": (
                transaction.transaction_date.isoformat()
                if transaction.transaction_date
                else None
            ),
            "created_at": (
                transaction.created_at.isoformat()
                if transaction.created_at
                else None
            ),
            "updated_at": (
                transaction.updated_at.isoformat()
                if transaction.updated_at
                else None
            ),
            "details": details
        }

    @staticmethod
    def delete_transaction(
        db: Session,
        user_id: int,
        transaction_id: int
    ) -> Dict[str, Any]:
        """
        Xóa giao dịch theo transaction_id và user_id.
        Yêu cầu:
        1. Chỉ chủ giao dịch (user_id) mới được xóa. Không tìm thấy hoặc không phải chủ -> 404.
        2. Không cho phép xóa nếu giao dịch thuộc kỳ chốt sổ đã đóng (CLOSED) -> 409 Conflict.
        3. Trong CÙNG 1 database transaction (atomic commit/rollback):
           - Hoàn lại tồn kho (Inventory_Transaction) cho các sản phẩm liên quan.
           - Hoàn lại công nợ (Debt, Debt_Payment).
           - Hoàn lại số dư tài khoản (Account.balance) nếu giao dịch đã phát sinh thu/chi tiền.
           - Hủy liên kết VoiceRecord (nếu có).
           - Xóa TransactionDetail và Transaction.
        4. Ghi log qua log_event (step="TRANSACTION").
        """
        from fastapi import HTTPException, status
        from app.models.closing_period_model import ClosingPeriod
        from app.models.closing_transaction_model import ClosingTransaction
        from app.models.debt_payment_model import DebtPayment
        from app.models.voice_record_model import VoiceRecord

        # 1. Tìm giao dịch
        tx = (
            db.query(Transaction)
            .filter(
                Transaction.transaction_id == transaction_id,
                Transaction.user_id == user_id
            )
            .first()
        )
        if not tx:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Không tìm thấy giao dịch #{transaction_id} hoặc bạn không có quyền xóa"
            )

        # 2. Kiểm tra kỳ chốt sổ
        # A: Kiểm tra qua ClosingTransaction
        closed_link = (
            db.query(ClosingPeriod)
            .join(ClosingTransaction, ClosingTransaction.closing_id == ClosingPeriod.closing_id)
            .filter(
                ClosingTransaction.transaction_id == tx.transaction_id,
                ClosingPeriod.status == "CLOSED"
            )
            .first()
        )
        # B: Kiểm tra theo ngày giao dịch trong kỳ CLOSED của user
        if not closed_link and tx.transaction_date:
            tx_d = tx.transaction_date.date() if isinstance(tx.transaction_date, datetime) else tx.transaction_date
            closed_link = (
                db.query(ClosingPeriod)
                .filter(
                    ClosingPeriod.user_id == user_id,
                    ClosingPeriod.status == "CLOSED",
                    ClosingPeriod.period_start <= tx_d,
                    ClosingPeriod.period_end >= tx_d
                )
                .first()
            )

        if closed_link:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Giao dịch thuộc kỳ chốt sổ đã đóng (Kỳ ID: {closed_link.closing_id}). Không thể xóa giao dịch trong kỳ đã chốt."
            )

        try:
            # 3. Hoàn lại tác động phụ (Side effects rollback)

            # A. Hoàn lại TỒN KHO (Inventory_Transaction)
            inv_txs = (
                db.query(InventoryTransaction)
                .filter(
                    InventoryTransaction.transaction_id == tx.transaction_id,
                    InventoryTransaction.user_id == user_id
                )
                .all()
            )
            for inv in inv_txs:
                # Tìm các biến động kho sau giao dịch này của cùng sản phẩm để cập nhật lại chuỗi số dư kho
                subsequent_invs = (
                    db.query(InventoryTransaction)
                    .filter(
                        InventoryTransaction.user_id == user_id,
                        InventoryTransaction.product_id == inv.product_id,
                        InventoryTransaction.inventory_transaction_id > inv.inventory_transaction_id
                    )
                    .all()
                )
                # Nếu giao dịch bị xóa là xuất kho (OUT), tồn kho cần được cộng trả lại
                if inv.inventory_type == "OUT":
                    for sub in subsequent_invs:
                        sub.quantity_before = Decimal(str(sub.quantity_before)) + Decimal(str(inv.quantity))
                        sub.quantity_after = Decimal(str(sub.quantity_after)) + Decimal(str(inv.quantity))
                # Nếu giao dịch bị xóa là nhập kho (IN), tồn kho cần được trừ đi
                elif inv.inventory_type == "IN":
                    for sub in subsequent_invs:
                        sub.quantity_before = Decimal(str(sub.quantity_before)) - Decimal(str(inv.quantity))
                        sub.quantity_after = Decimal(str(sub.quantity_after)) - Decimal(str(inv.quantity))

                db.delete(inv)

            # B. Hoàn lại SỐ DƯ TÀI KHOẢN (Account)
            if tx.account_id and tx.payment_status in ("PAID", "PARTIAL") and tx.total_amount:
                account = (
                    db.query(Account)
                    .filter(
                        Account.account_id == tx.account_id,
                        Account.user_id == user_id
                    )
                    .first()
                )
                if account:
                    amount_to_revert = Decimal(str(tx.total_amount))
                    is_income = False
                    if tx.category and tx.category.category_type == "INCOME":
                        is_income = True
                    elif tx.intent and tx.intent.intent_name in ("ban_hang", "thu_no_khach_hang", "thu_no_khach"):
                        is_income = True

                    is_expense = False
                    if tx.category and tx.category.category_type == "EXPENSE":
                        is_expense = True
                    elif tx.intent and tx.intent.intent_name in ("mua_hang", "nhap_hang", "chi_tien", "chi_phi", "tra_no_nha_cung_cap"):
                        is_expense = True

                    if is_income:
                        account.balance = Decimal(str(account.balance)) - amount_to_revert
                    elif is_expense:
                        account.balance = Decimal(str(account.balance)) + amount_to_revert

            # C. Hoàn lại CÔNG NỢ (Debt & DebtPayment)
            # TH1: Giao dịch này tạo ra một khoản nợ (Debt)
            created_debts = (
                db.query(Debt)
                .filter(
                    Debt.transaction_id == tx.transaction_id,
                    Debt.user_id == user_id
                )
                .all()
            )
            for d in created_debts:
                # Xóa các khoản thanh toán gắn với khoản nợ này
                payments_on_debt = db.query(DebtPayment).filter(DebtPayment.debt_id == d.debt_id).all()
                for p in payments_on_debt:
                    db.delete(p)
                db.delete(d)

            # TH2: Giao dịch này là thanh toán cho một khoản nợ đã có (DebtPayment)
            debt_payments = (
                db.query(DebtPayment)
                .filter(DebtPayment.transaction_id == tx.transaction_id)
                .all()
            )
            for dp in debt_payments:
                parent_debt = db.query(Debt).filter(Debt.debt_id == dp.debt_id).first()
                if parent_debt:
                    parent_debt.remaining_debt = Decimal(str(parent_debt.remaining_debt)) + Decimal(str(dp.amount))
                    if parent_debt.remaining_debt >= parent_debt.original_amount:
                        parent_debt.status = "UNPAID"
                    else:
                        parent_debt.status = "PARTIAL"
                db.delete(dp)

            # D. Gỡ liên kết VoiceRecord
            voice_records = (
                db.query(VoiceRecord)
                .filter(VoiceRecord.transaction_id == tx.transaction_id)
                .all()
            )
            for vr in voice_records:
                vr.transaction_id = None

            # E. Gỡ liên kết ClosingTransaction (nếu kỳ OPEN / REOPENED)
            open_closing_links = (
                db.query(ClosingTransaction)
                .filter(ClosingTransaction.transaction_id == tx.transaction_id)
                .all()
            )
            for cl in open_closing_links:
                db.delete(cl)

            # F. Xóa TransactionDetail
            details = (
                db.query(TransactionDetail)
                .filter(TransactionDetail.transaction_id == tx.transaction_id)
                .all()
            )
            for det in details:
                db.delete(det)

            # G. Xóa Transaction
            db.delete(tx)

            # COMMIT trong cùng transaction
            db.commit()

            # Ghi log sự kiện
            log_event(
                level="INFO",
                step="TRANSACTION",
                message=f"Đã xóa thành công giao dịch #{transaction_id}",
                detail={"transaction_id": transaction_id, "user_id": user_id},
                user_id=user_id,
                status_code=200,
                api_path=f"/api/v1/transactions/{transaction_id}"
            )

            return {
                "success": True,
                "message": f"Đã xóa giao dịch #{transaction_id} và hoàn lại toàn bộ tồn kho, công nợ liên quan thành công"
            }

        except HTTPException:
            db.rollback()
            raise
        except Exception as exc:
            db.rollback()
            log_event(
                level="ERROR",
                step="TRANSACTION",
                message=f"Lỗi khi xóa giao dịch #{transaction_id}: {str(exc)}",
                detail={"transaction_id": transaction_id, "error": str(exc)},
                user_id=user_id,
                status_code=500,
                api_path=f"/api/v1/transactions/{transaction_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Lỗi hệ thống khi xóa giao dịch: {str(exc)}"
            )

    # ==========================================================
    # UPDATE TRANSACTION (đối chiếu docs/erd_new.md)
    # ==========================================================
    _UPDATE_SALE_INVENTORY_INTENTS = {
        "ban_hang", "ghi_no_khach_hang", "ghi_no_phai_thu", "khach_ghi_no"
    }
    _UPDATE_PURCHASE_INVENTORY_INTENTS = {
        "mua_hang", "nhap_hang", "ghi_no_nha_cung_cap", "ghi_no_phai_tra",
        "ghi_no_cung_cap", "ncc_ghi_no"
    }
    _UPDATE_RECEIVABLE_ORIGIN_INTENTS = {"ghi_no_khach_hang", "ghi_no_phai_thu", "khach_ghi_no"}
    _UPDATE_PAYABLE_ORIGIN_INTENTS = {"ghi_no_nha_cung_cap", "ghi_no_phai_tra", "ghi_no_cung_cap", "ncc_ghi_no"}
    _UPDATE_DEBT_PAYMENT_INTENTS = {
        "thu_no_khach_hang", "thu_no_phai_thu", "thu_no_khach",
        "tra_no_nha_cung_cap", "tra_no_phai_tra", "tra_no_cung_cap", "tra_no_ncc"
    }
    _UPDATE_CASH_IN_INTENTS = {
        "ban_hang", "thu_tien", "thu_no_khach_hang", "thu_no_phai_thu", "thu_no_khach"
    }
    _UPDATE_CASH_OUT_INTENTS = {
        "mua_hang", "nhap_hang", "chi_tien", "chi_phi", "hang_hong", "hoan_tien",
        "tra_no_nha_cung_cap", "tra_no_phai_tra", "tra_no_cung_cap", "tra_no_ncc"
    }

    @staticmethod
    def _find_closed_period(
        db: Session,
        user_id: int,
        transaction_id: Optional[int],
        tx_date: Optional[datetime]
    ):
        """Trả về ClosingPeriod (status=CLOSED) chứa giao dịch / ngày giao dịch, nếu có."""
        from app.models.closing_period_model import ClosingPeriod
        from app.models.closing_transaction_model import ClosingTransaction

        closed = None
        if transaction_id is not None:
            closed = (
                db.query(ClosingPeriod)
                .join(ClosingTransaction, ClosingTransaction.closing_id == ClosingPeriod.closing_id)
                .filter(
                    ClosingTransaction.transaction_id == transaction_id,
                    ClosingPeriod.user_id == user_id,
                    ClosingPeriod.status == "CLOSED"
                )
                .first()
            )
        if not closed and tx_date:
            tx_d = tx_date.date() if isinstance(tx_date, datetime) else tx_date
            closed = (
                db.query(ClosingPeriod)
                .filter(
                    ClosingPeriod.user_id == user_id,
                    ClosingPeriod.status == "CLOSED",
                    ClosingPeriod.period_start <= tx_d,
                    ClosingPeriod.period_end >= tx_d
                )
                .first()
            )
        return closed

    @staticmethod
    def _resolve_cash_direction(category: Optional[Category], intent_name: str) -> int:
        """+1: thu tiền vào tài khoản, -1: chi tiền ra, 0: không ảnh hưởng số dư."""
        if category is not None:
            if category.category_type == "INCOME":
                return 1
            if category.category_type == "EXPENSE":
                return -1
        if intent_name in TransactionService._UPDATE_CASH_IN_INTENTS:
            return 1
        if intent_name in TransactionService._UPDATE_CASH_OUT_INTENTS:
            return -1
        return 0

    @staticmethod
    def _account_effect(
        account_id: Optional[int],
        payment_status: Optional[str],
        amount: Decimal,
        direction: int
    ) -> Decimal:
        """Tác động lên Account.balance của giao dịch (đồng bộ logic hoàn tác trong delete_transaction)."""
        if account_id is None or direction == 0 or payment_status not in ("PAID", "PARTIAL"):
            return Decimal("0")
        return amount * direction

    @staticmethod
    def _get_latest_stock(db: Session, user_id: int, product_id: int) -> Decimal:
        last = (
            db.query(InventoryTransaction)
            .filter(
                InventoryTransaction.user_id == user_id,
                InventoryTransaction.product_id == product_id
            )
            .order_by(InventoryTransaction.inventory_transaction_id.desc())
            .first()
        )
        return Decimal(str(last.quantity_after)) if last and last.quantity_after is not None else Decimal("0")

    @staticmethod
    def _shift_subsequent_inventory(
        db: Session,
        user_id: int,
        product_id: int,
        after_inventory_id: int,
        delta: Decimal
    ) -> None:
        """Dịch chuỗi quantity_before/quantity_after của các biến động kho phát sinh sau một bản ghi."""
        if delta == 0:
            return
        subsequent = (
            db.query(InventoryTransaction)
            .filter(
                InventoryTransaction.user_id == user_id,
                InventoryTransaction.product_id == product_id,
                InventoryTransaction.inventory_transaction_id > after_inventory_id
            )
            .all()
        )
        for sub in subsequent:
            sub.quantity_before = Decimal(str(sub.quantity_before or 0)) + delta
            sub.quantity_after = Decimal(str(sub.quantity_after or 0)) + delta

    @staticmethod
    def update_transaction(
        db: Session,
        user_id: int,
        transaction_id: int,
        request
    ) -> Dict[str, Any]:
        """
        Cập nhật giao dịch theo docs/erd_new.md (partial update):
        1. Chỉ chủ giao dịch (user_id) được sửa -> 404 nếu không tìm thấy.
        2. Chặn sửa nếu giao dịch (hoặc ngày giao dịch mới) thuộc kỳ chốt sổ CLOSED -> 409.
        3. Không cho đổi intent.
        4. Trong CÙNG 1 database transaction (atomic commit/rollback):
           - Thay thế Transaction_Detail (nếu gửi details), subtotal = quantity * unit_price do backend tính.
           - Đồng bộ Inventory_Transaction (OUT/IN) theo business_type & product_type.
           - Hoàn tác & áp dụng lại Account.balance.
           - Đồng bộ Debt (giao dịch gốc sinh nợ) hoặc Debt_Payment (giao dịch trả/thu nợ).
        Lỗi nghiệp vụ -> ValueError (route map thành 422).
        """
        from fastapi import HTTPException, status
        from app.models.debt_payment_model import DebtPayment
        from app.models.user_model import User

        fields = request.model_fields_set
        now = datetime.now()

        # ------------------------------------------------------
        # 1. Lấy giao dịch (row lock) & kiểm tra quyền sở hữu
        # ------------------------------------------------------
        tx = TransactionRepository.get_transaction_for_update(
            db=db,
            user_id=user_id,
            transaction_id=transaction_id
        )
        if not tx:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Không tìm thấy giao dịch #{transaction_id} hoặc bạn không có quyền sửa"
            )

        # ------------------------------------------------------
        # 2. Kiểm tra kỳ chốt sổ (cũ & mới)
        # ------------------------------------------------------
        closed = TransactionService._find_closed_period(db, user_id, tx.transaction_id, tx.transaction_date)
        if closed:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Giao dịch thuộc kỳ chốt sổ đã đóng (Kỳ ID: {closed.closing_id}). Không thể sửa giao dịch trong kỳ đã chốt."
            )
        if "transaction_date" in fields and request.transaction_date is not None:
            closed_new = TransactionService._find_closed_period(db, user_id, None, request.transaction_date)
            if closed_new:
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Ngày giao dịch mới thuộc kỳ chốt sổ đã đóng (Kỳ ID: {closed_new.closing_id}). Không thể chuyển giao dịch vào kỳ đã chốt."
                )

        try:
            intent_name = ((tx.intent.intent_name if tx.intent else "") or "").lower().strip()

            # 3. Không cho đổi intent
            if "intent_id" in fields and request.intent_id is not None and request.intent_id != tx.intent_id:
                raise ValueError("Không được thay đổi intent của giao dịch. Vui lòng xóa và tạo giao dịch mới")

            # ------------------------------------------------------
            # 4. Snapshot trạng thái cũ
            # ------------------------------------------------------
            old_account_id = tx.account_id
            old_payment_status = tx.payment_status
            old_total = Decimal(str(tx.total_amount or 0))
            old_category = tx.category
            old_direction = TransactionService._resolve_cash_direction(old_category, intent_name)

            # ------------------------------------------------------
            # 5. Resolve & validate khóa ngoại mới (multi-tenant)
            # ------------------------------------------------------
            new_category = old_category
            if "category_id" in fields:
                if request.category_id is None:
                    new_category = None
                else:
                    new_category = db.query(Category).filter(
                        Category.category_id == request.category_id,
                        (Category.user_id == user_id) | (Category.user_id.is_(None))
                    ).first()
                    if not new_category:
                        raise ValueError(f"Category với id {request.category_id} không tồn tại")

            new_account_id = old_account_id
            if "account_id" in fields:
                if request.account_id is not None:
                    acc_exists = db.query(Account).filter(
                        Account.account_id == request.account_id,
                        Account.user_id == user_id
                    ).first()
                    if not acc_exists:
                        raise ValueError(f"Account với id {request.account_id} không tồn tại")
                new_account_id = request.account_id

            new_customer_id = tx.customer_id
            if "customer_id" in fields:
                if request.customer_id is not None:
                    cus_exists = db.query(Customer).filter(
                        Customer.customer_id == request.customer_id,
                        Customer.user_id == user_id
                    ).first()
                    if not cus_exists:
                        raise ValueError(f"Customer với id {request.customer_id} không tồn tại")
                new_customer_id = request.customer_id

            new_supplier_id = tx.supplier_id
            if "supplier_id" in fields:
                if request.supplier_id is not None:
                    sup_exists = db.query(Supplier).filter(
                        Supplier.supplier_id == request.supplier_id,
                        Supplier.user_id == user_id
                    ).first()
                    if not sup_exists:
                        raise ValueError(f"Supplier với id {request.supplier_id} không tồn tại")
                new_supplier_id = request.supplier_id

            new_payment_status = request.payment_status if "payment_status" in fields else old_payment_status

            # ------------------------------------------------------
            # 6. Chi tiết dòng hàng & tổng tiền (backend tự tính)
            # ------------------------------------------------------
            details_changed = "details" in fields and request.details is not None
            new_detail_rows: List[Dict[str, Any]] = []
            details_total = Decimal("0.00")
            product_map: Dict[int, Product] = {}

            if details_changed:
                old_detail_product_ids = {d.product_id for d in (tx.transaction_detail or [])}
                req_product_ids = sorted({item.product_id for item in request.details})
                locked_products = (
                    db.query(Product)
                    .filter(
                        Product.user_id == user_id,
                        Product.product_id.in_(req_product_ids)
                    )
                    .with_for_update()
                    .all()
                )
                product_map = {p.product_id: p for p in locked_products}

                for item in request.details:
                    prod = product_map.get(item.product_id)
                    if not prod:
                        raise ValueError(f"Sản phẩm với id {item.product_id} không tồn tại")
                    if not prod.is_active and prod.product_id not in old_detail_product_ids:
                        raise ValueError(f"Sản phẩm '{prod.product_name}' đã ngừng kinh doanh")

                    qty = Decimal(str(item.quantity))
                    u_price = Decimal(str(item.unit_price))
                    subtotal = qty * u_price
                    details_total += subtotal
                    new_detail_rows.append({
                        "product": prod,
                        "product_name": item.product_name or prod.product_name,
                        "quantity": qty,
                        "unit": item.unit or prod.default_unit or "cái",
                        "unit_price": u_price,
                        "subtotal": subtotal,
                    })

            if details_changed:
                new_total = details_total
                if "total_amount" in fields and Decimal(str(request.total_amount)) != details_total:
                    raise ValueError(
                        f"Tổng tiền (total_amount = {request.total_amount}) không khớp với tổng chi tiết ({details_total})"
                    )
            elif "total_amount" in fields:
                new_total = Decimal(str(request.total_amount))
            else:
                new_total = old_total

            # ------------------------------------------------------
            # 7. Validate nghiệp vụ theo intent
            # ------------------------------------------------------
            is_debt_origin = (
                intent_name in TransactionService._UPDATE_RECEIVABLE_ORIGIN_INTENTS
                or intent_name in TransactionService._UPDATE_PAYABLE_ORIGIN_INTENTS
            )
            is_debt_payment = intent_name in TransactionService._UPDATE_DEBT_PAYMENT_INTENTS

            if (is_debt_origin or is_debt_payment or intent_name == "chi_tien") and new_total <= 0:
                raise ValueError("Số tiền giao dịch (total_amount) phải lớn hơn 0")
            if intent_name == "chi_tien":
                if new_category is None:
                    raise ValueError("Giao dịch chi tiền bắt buộc phải có danh mục (category_id)")
                if new_account_id is None:
                    raise ValueError("Giao dịch chi tiền bắt buộc phải có tài khoản thanh toán (account_id)")
            if intent_name in TransactionService._UPDATE_RECEIVABLE_ORIGIN_INTENTS and new_customer_id is None:
                raise ValueError("Giao dịch ghi nợ khách hàng bắt buộc phải có khách hàng (customer_id)")
            if intent_name in TransactionService._UPDATE_PAYABLE_ORIGIN_INTENTS and new_supplier_id is None:
                raise ValueError("Giao dịch ghi nợ nhà cung cấp bắt buộc phải có nhà cung cấp (supplier_id)")
            if is_debt_payment and (new_customer_id != tx.customer_id or new_supplier_id != tx.supplier_id):
                raise ValueError("Không được thay đổi khách hàng/nhà cung cấp của giao dịch thanh toán công nợ")

            # ------------------------------------------------------
            # 8. Đồng bộ Debt (giao dịch gốc sinh ra nợ)
            # ------------------------------------------------------
            origin_debts = (
                db.query(Debt)
                .filter(
                    Debt.transaction_id == tx.transaction_id,
                    Debt.user_id == user_id
                )
                .with_for_update()
                .all()
            )
            for debt in origin_debts:
                payments = db.query(DebtPayment).filter(DebtPayment.debt_id == debt.debt_id).all()
                paid = sum((Decimal(str(p.amount or 0)) for p in payments), Decimal("0"))

                if debt.direction == "RECEIVABLE" and new_customer_id != debt.customer_id:
                    if payments:
                        raise ValueError("Khoản nợ đã có thanh toán, không thể đổi khách hàng")
                    debt.customer_id = new_customer_id
                elif debt.direction == "PAYABLE" and new_supplier_id != debt.supplier_id:
                    if payments:
                        raise ValueError("Khoản nợ đã có thanh toán, không thể đổi nhà cung cấp")
                    debt.supplier_id = new_supplier_id

                if new_total != Decimal(str(debt.original_amount or 0)):
                    if new_total < paid:
                        raise ValueError(
                            f"Tổng tiền mới ({new_total}) nhỏ hơn số tiền đã thanh toán ({paid}), vượt giới hạn cho phép"
                        )
                    debt.original_amount = new_total
                    debt.remaining_debt = new_total - paid
                    if debt.remaining_debt == 0:
                        debt.status = "PAID"
                    elif paid > 0:
                        debt.status = "PARTIAL"
                    else:
                        debt.status = "UNPAID"
                    for p in payments:
                        p.payment_percentage = (
                            (Decimal(str(p.amount or 0)) / new_total * 100).quantize(Decimal("0.01"))
                            if new_total > 0 else Decimal("0.00")
                        )
                debt.updated_at = now

            # ------------------------------------------------------
            # 9. Đồng bộ Debt_Payment (giao dịch thu/trả nợ)
            # ------------------------------------------------------
            debt_payments = (
                db.query(DebtPayment)
                .filter(DebtPayment.transaction_id == tx.transaction_id)
                .all()
            )
            if debt_payments:
                if len(debt_payments) == 1 and new_total != Decimal(str(debt_payments[0].amount or 0)):
                    dp = debt_payments[0]
                    parent = (
                        db.query(Debt)
                        .filter(Debt.debt_id == dp.debt_id, Debt.user_id == user_id)
                        .with_for_update()
                        .first()
                    )
                    if parent:
                        available = Decimal(str(parent.remaining_debt or 0)) + Decimal(str(dp.amount or 0))
                        if new_total > available:
                            raise ValueError(f"Số tiền thanh toán ({new_total}) vượt quá số nợ còn lại ({available})")
                        orig = Decimal(str(parent.original_amount or 0))
                        parent.remaining_debt = available - new_total
                        if parent.remaining_debt == 0:
                            parent.status = "PAID"
                        elif parent.remaining_debt >= orig:
                            parent.status = "UNPAID"
                        else:
                            parent.status = "PARTIAL"
                        parent.updated_at = now
                        dp.payment_percentage = (
                            (new_total / orig * 100).quantize(Decimal("0.01")) if orig > 0 else Decimal("0.00")
                        )
                    dp.amount = new_total
                elif len(debt_payments) > 1 and new_total != old_total:
                    raise ValueError("Giao dịch thanh toán nhiều khoản nợ, không hỗ trợ sửa số tiền")

                if "account_id" in fields:
                    if new_account_id is None:
                        raise ValueError("Giao dịch thanh toán công nợ bắt buộc phải có tài khoản (account_id)")
                    for dp in debt_payments:
                        dp.account_id = new_account_id
                if "transaction_date" in fields:
                    for dp in debt_payments:
                        dp.payment_date = request.transaction_date

            # ------------------------------------------------------
            # 10. Đồng bộ Inventory_Transaction theo business_type & product_type
            # ------------------------------------------------------
            is_sale = intent_name in TransactionService._UPDATE_SALE_INVENTORY_INTENTS
            is_purchase = intent_name in TransactionService._UPDATE_PURCHASE_INVENTORY_INTENTS

            if details_changed and (is_sale or is_purchase):
                user = db.query(User).filter(User.user_id == user_id).first()
                business_type = ((user.business_type if user else "") or "").upper().strip()

                desired: Dict[int, Dict[str, Any]] = {}
                for row in new_detail_rows:
                    pid = row["product"].product_id
                    if pid not in desired:
                        desired[pid] = {"quantity": Decimal("0"), "unit": row["unit"]}
                    desired[pid]["quantity"] += row["quantity"]

                old_invs = (
                    db.query(InventoryTransaction)
                    .filter(
                        InventoryTransaction.transaction_id == tx.transaction_id,
                        InventoryTransaction.user_id == user_id
                    )
                    .order_by(InventoryTransaction.inventory_transaction_id.asc())
                    .all()
                )
                old_by_product: Dict[int, List[InventoryTransaction]] = {}
                for inv in old_invs:
                    old_by_product.setdefault(inv.product_id, []).append(inv)

                extra_ids = sorted(set(old_by_product.keys()) - set(product_map.keys()))
                if extra_ids:
                    for p in (
                        db.query(Product)
                        .filter(Product.user_id == user_id, Product.product_id.in_(extra_ids))
                        .with_for_update()
                        .all()
                    ):
                        product_map[p.product_id] = p

                for pid in sorted(set(desired.keys()) | set(old_by_product.keys())):
                    recs = old_by_product.get(pid, [])
                    old_change = sum(
                        (Decimal(str(r.quantity_after or 0)) - Decimal(str(r.quantity_before or 0)) for r in recs),
                        Decimal("0")
                    )
                    latest = TransactionService._get_latest_stock(db, user_id, pid)
                    stock_excluding_tx = latest - old_change

                    new_change = Decimal("0")
                    inv_type = None
                    unit = None
                    prod = product_map.get(pid)
                    prod_name = prod.product_name if prod else f"#{pid}"

                    if pid in desired:
                        qty = desired[pid]["quantity"]
                        unit = desired[pid]["unit"]
                        product_type = ((prod.product_type if prod else None) or "RESALE").upper()

                        if is_sale:
                            inv_type = "OUT"
                            if product_type == "RAW_MATERIAL":
                                raise ValueError(
                                    f"cannot_sell_raw_material: Sản phẩm '{prod_name}' là nguyên liệu, không được bán trực tiếp"
                                )
                            if business_type == "SERVICE":
                                # SERVICE: bỏ qua kiểm tra kho, không tạo OUT
                                new_change = Decimal("0")
                            elif product_type == "FINISHED_GOOD":
                                # PRODUCER + FINISHED_GOOD: được bán khi tồn = 0, không tạo xuất kho âm
                                new_change = -qty if stock_excluding_tx >= qty else Decimal("0")
                            else:
                                # RESELLER + RESALE: bắt buộc đủ tồn kho
                                if stock_excluding_tx < qty:
                                    raise ValueError(
                                        f"INSUFFICIENT_STOCK: Sản phẩm '{prod_name}' không đủ tồn kho "
                                        f"(tồn {stock_excluding_tx}, cần {qty})"
                                    )
                                new_change = -qty
                        else:
                            inv_type = "IN"
                            new_change = qty

                    if stock_excluding_tx + new_change < 0:
                        raise ValueError(
                            f"INSUFFICIENT_STOCK: Không thể cập nhật vì tồn kho sản phẩm '{prod_name}' sẽ bị âm"
                        )

                    keep = None
                    for rec in recs:
                        if keep is None and new_change != 0:
                            keep = rec
                            continue
                        rec_change = Decimal(str(rec.quantity_after or 0)) - Decimal(str(rec.quantity_before or 0))
                        TransactionService._shift_subsequent_inventory(
                            db, user_id, pid, rec.inventory_transaction_id, -rec_change
                        )
                        db.delete(rec)

                    if keep is not None:
                        keep_before = Decimal(str(keep.quantity_before or 0))
                        keep_change = Decimal(str(keep.quantity_after or 0)) - keep_before
                        keep.inventory_type = inv_type
                        keep.quantity = abs(new_change)
                        keep.unit = unit or keep.unit
                        keep.quantity_after = keep_before + new_change
                        TransactionService._shift_subsequent_inventory(
                            db, user_id, pid, keep.inventory_transaction_id, new_change - keep_change
                        )
                    elif new_change != 0:
                        current_stock = TransactionService._get_latest_stock(db, user_id, pid)
                        db.add(InventoryTransaction(
                            user_id=user_id,
                            product_id=pid,
                            transaction_id=tx.transaction_id,
                            inventory_type=inv_type,
                            quantity=abs(new_change),
                            unit=unit,
                            quantity_before=current_stock,
                            quantity_after=current_stock + new_change,
                            note=(
                                "Xuất kho do cập nhật giao dịch bán hàng"
                                if inv_type == "OUT"
                                else "Nhập kho do cập nhật giao dịch nhập hàng"
                            ),
                            created_at=now
                        ))
                    db.flush()

            # ------------------------------------------------------
            # 11. Thay thế Transaction_Detail
            # ------------------------------------------------------
            if details_changed:
                old_details = (
                    db.query(TransactionDetail)
                    .filter(TransactionDetail.transaction_id == tx.transaction_id)
                    .all()
                )
                for det in old_details:
                    db.delete(det)
                db.flush()

                for row in new_detail_rows:
                    db.add(TransactionDetail(
                        transaction_id=tx.transaction_id,
                        product_id=row["product"].product_id,
                        product_name=row["product_name"],
                        quantity=row["quantity"],
                        unit=row["unit"],
                        unit_price=row["unit_price"],
                        subtotal=row["subtotal"]
                    ))

            # ------------------------------------------------------
            # 12. Hoàn tác & áp dụng lại Account.balance
            # ------------------------------------------------------
            new_direction = TransactionService._resolve_cash_direction(new_category, intent_name)
            old_effect = TransactionService._account_effect(old_account_id, old_payment_status, old_total, old_direction)
            new_effect = TransactionService._account_effect(new_account_id, new_payment_status, new_total, new_direction)

            def _lock_account(acc_id: int) -> Optional[Account]:
                return (
                    db.query(Account)
                    .filter(Account.account_id == acc_id, Account.user_id == user_id)
                    .with_for_update()
                    .first()
                )

            if old_account_id == new_account_id:
                diff = new_effect - old_effect
                if new_account_id is not None and diff != 0:
                    acc = _lock_account(new_account_id)
                    if acc:
                        acc.balance = Decimal(str(acc.balance or 0)) + diff
                        acc.updated_at = now
            else:
                if old_account_id is not None and old_effect != 0:
                    old_acc = _lock_account(old_account_id)
                    if old_acc:
                        old_acc.balance = Decimal(str(old_acc.balance or 0)) - old_effect
                        old_acc.updated_at = now
                if new_account_id is not None and new_effect != 0:
                    new_acc = _lock_account(new_account_id)
                    if new_acc:
                        new_acc.balance = Decimal(str(new_acc.balance or 0)) + new_effect
                        new_acc.updated_at = now

            # ------------------------------------------------------
            # 13. Cập nhật Transaction
            # ------------------------------------------------------
            if "category_id" in fields:
                tx.category_id = new_category.category_id if new_category else None
            if "account_id" in fields:
                tx.account_id = new_account_id
            if "customer_id" in fields:
                tx.customer_id = new_customer_id
            if "supplier_id" in fields:
                tx.supplier_id = new_supplier_id
            if "payment_status" in fields:
                tx.payment_status = new_payment_status
            if "input_text" in fields:
                tx.input_text = request.input_text
            if "note" in fields:
                tx.note = request.note
            if "transaction_date" in fields:
                tx.transaction_date = request.transaction_date
            tx.total_amount = new_total
            tx.updated_at = now

            db.commit()

            # Kích hoạt cảnh báo tồn kho nếu có sản phẩm xuất kho bị giảm số lượng tồn
            for pid in new_by_product.keys():
                try:
                    from app.services.stock_alert_service import StockAlertService
                    StockAlertService.check_and_notify_stock(
                        db=db,
                        user_id=user_id,
                        product_id=pid
                    )
                except Exception:
                    pass

        except (ValueError, HTTPException):
            db.rollback()
            raise
        except SQLAlchemyError as exc:
            db.rollback()
            log_event(
                level="ERROR",
                step="DB",
                message=f"Database commit error in update_transaction: {str(exc)}",
                detail={"error": str(exc), "error_type": type(exc).__name__, "transaction_id": transaction_id, "user_id": user_id},
                user_id=user_id,
            )
            raise

        log_event(
            level="INFO",
            step="TRANSACTION",
            message=f"Đã cập nhật thành công giao dịch #{transaction_id}",
            detail={"transaction_id": transaction_id, "user_id": user_id, "fields": sorted(list(fields))},
            user_id=user_id,
            status_code=200,
            api_path=f"/api/v1/transactions/{transaction_id}"
        )

        return TransactionService.get_transaction_by_id(
            db=db,
            user_id=user_id,
            transaction_id=transaction_id
        )
