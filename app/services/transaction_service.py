from math import ceil
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc

# IMPORT CÁC MODELS
from app.models.transaction_model import Transaction
from app.models.transactionDetail_model import TransactionDetail
from app.models.customer_model import Customer
from app.models.supplier_model import Supplier
from app.models.account_model import Account
from app.models.intent_model import Intent
from app.models.inventory_model import InventoryTransaction
from app.models.debt_model import Debt

from app.services.intent_service import IntentService
from app.services.customer_service import CustomerService
from app.services.product_service import ProductService
from app.services.account_service import AccountService
from app.services.inventory_service import InventoryService

from app.repositories.inventory_respositories import InventoryRepository


from datetime import datetime, timedelta
import unicodedata

# IMPORT REPOSITORIES
from app.repositories.transaction_repository import TransactionRepository
from app.repositories.product_repository import (
    get_product_by_name,
    create_product
)
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy.orm import Session


class TransactionService:

    @staticmethod
    def parse_transaction_date(
        transaction_date: str | None
    ) -> datetime:
        now = datetime.now()

        # Không có ngày giờ
        if not transaction_date:
            return now

        transaction_date = str(
            transaction_date
        ).strip()

        # ======================================================
        # YYYY-MM-DD HH:MM:SS
        # ======================================================

        try:
            return datetime.strptime(
                transaction_date,
                "%Y-%m-%d %H:%M:%S"
            )
        except ValueError:
            pass

        # ======================================================
        # YYYY-MM-DD HH:MM
        # ======================================================

        try:
            return datetime.strptime(
                transaction_date,
                "%Y-%m-%d %H:%M"
            )
        except ValueError:
            pass

        # ======================================================
        # YYYY-MM-DD
        # ======================================================

        try:
            parsed_date = datetime.strptime(
                transaction_date,
                "%Y-%m-%d"
            )

            return parsed_date.replace(
                hour=now.hour,
                minute=now.minute,
                second=now.second,
                microsecond=now.microsecond
            )

        except ValueError:
            pass

        # ======================================================
        # INVALID
        # ======================================================
        raise ValueError(
            f"Ngày/giờ không hợp lệ: {transaction_date}. "
            "Định dạng cho phép: "
            "YYYY-MM-DD, "
            "YYYY-MM-DD HH:MM, "
            "YYYY-MM-DD HH:MM:SS"
        )

    @staticmethod
    def save_groq_transaction(
        db: Session,
        user_id: int,
        account_id: int | None,
        groq_result: dict
    ):
        # ==========================================================
        # 1. LẤY TRANSACTION ANALYSIS
        # ==========================================================

        transaction_analysis = groq_result.get(
            "transaction_analysis"
        )

        if not transaction_analysis:
            raise ValueError(
                 "Không có transaction_analysis trong kết quả AI"
            )
        
        groq_intent = transaction_analysis.get("intent")

        intent_name = IntentService.normalize_intent(        
            groq_intent
        )

        intent = IntentService.get_intent_by_name(        
            db=db,
            intent_name=intent_name
        )

        if not intent:
            raise ValueError(
                f"Intent '{intent_name}' không tồn tại trong database"
            )
        

        # ==========================================================
        # 3. LẤY ENTITIES
        # ==========================================================

        entities = transaction_analysis.get("entities") or {}

        customer_name = entities.get("customer")
        supplier_name = entities.get("supplier")
        product_name = entities.get("product")
        payment_method = entities.get("payment")

        input_text = transaction_analysis.get("text")

        quantity = entities.get("quantity")
        price = entities.get("price")
        unit = entities.get("unit")
        transaction_date = entities.get("date")
        transaction_date = TransactionService.parse_transaction_date(
            transaction_date
        )
        # ==========================================================
        # 4. DEFAULT VALUE
        # ==========================================================
        if price is None:
            raise ValueError("Phải có giá")

        if quantity is None:
            raise ValueError("Phải có số lượng")

        try:
            quantity = Decimal(str(quantity))
        except Exception:
            raise ValueError("Số lượng không hợp lệ")

        try:
            price = Decimal(str(price))
        except Exception:
            raise ValueError("Giá tiền không hợp lệ")

        if quantity <= 0:
            raise ValueError(
                "Số lượng phải lớn hơn 0"
            )

        if price < 0:
            raise ValueError(
                "Giá tiền không được âm"
            )

        total_amount = Decimal("0")
        customer = None
        supplier = None
        product = None
        account = None
        inventory = None
        debt = None

        payment_status = "Đã thanh toán"


        # ==========================================================
        # BÁN HÀNG
        # ==========================================================

        if IntentService.is_sales_intent(intent_name):

            # 1. Customer
            customer = CustomerService.get_customer_for_sale(
                db=db,
                user_id=user_id,
                customer_name=customer_name,
            )

            # 2. Product
            product = ProductService.get_product_for_sale(
                db=db,
                user_id=user_id,
                product_name=product_name
            )

            # 3. Account
            account = AccountService.get_account_by_payment(
                db=db,
                user_id=user_id,
                payment_method=payment_method,
            )

            # 4. Tồn kho
            quantity_before = InventoryService.get_quantity_before(
                db=db,
                user_id=user_id,
                product_id=product.product_id,
            )

            # 5. Kiểm tra số lượng bán
            quantity_after = InventoryService.validate_sale_quantity(
                quantity_before=quantity_before,
                quantity=quantity,
                product_name=product.name,
            )

            # 6. Tính tiền
          
            total_amount = price
        
            unit_price = total_amount / quantity 
                 
            # 7. Tăng tiền tài khoản
            AccountService.increase_balance(
                account=account,
                amount=total_amount,
            )

            # 8. Tạo transaction
            transaction = Transaction(
                user_id=user_id,
                intent_id=intent.intent_id,
                customer_id=customer.customer_id if customer else None,
                supplier_id=None,
                account_id=account.account_id,
                total_amount=total_amount,
                payment_status="Đã thanh toán",
                input_text=input_text,
                transaction_date=transaction_date,
            )
            transaction = TransactionRepository.create_transaction(
                db=db,
                transaction=transaction
            )

            # 9. Tạo chi tiết giao dịch
            detail = TransactionDetail(
                transaction_id=transaction.transaction_id,
                product_id=product.product_id,

                quantity=quantity,
                unit=unit,
                unit_price=unit_price,
                subtotal=total_amount,
            )

            TransactionRepository.create_transaction_detail(
                db=db,
                detail=detail,            
            )
            

            # 10. Xuất kho
            inventory = InventoryRepository.create_inventory(
                db=db,
                user_id=user_id,
                product_id=product.product_id,
                transaction_id=transaction.transaction_id,
                quantity=quantity,
                unit=unit,
                quantity_before=quantity_before,
                quantity_after=quantity_after,
                inventory_type="OUT",
                note="Xuất kho do bán hàng",
            )
        

        # ==========================================================
        # 16. COMMIT TOÀN BỘ
        # ==========================================================
        db.commit()
        db.refresh(transaction)

        # ==========================================================
        # 17. RETURN
        # ==========================================================
        return {
            "transaction_id": transaction.transaction_id,
            "user_id": user_id,
            "intent_id": intent.intent_id,
            "account_id": account.account_id if account else None,
            "customer_id": (
                customer.customer_id
                if customer 
                else None 
            ),
            "supplier_id":( 
                supplier.supplier_id 
                if supplier 
                else None 
            ),
            "product_id": product.product_id if product else None,
            "inventory_transaction_id": inventory.inventory_transaction_id if inventory else None,
            "debt_id": debt.debt_id if debt else None,
            "quantity": ( 
                float(quantity) 
                if product 
                else None 
            ),
            "unit": ( 
                unit or product.default_unit 
                if product 
                else None 
            ),
            "unit_price": unit_price if product else None,
            "total_amount": total_amount,
            "payment_status": payment_status,
            "input_method": transaction.input_method,
            "input_text": input_text,
            "transaction_date": transaction_date,
            "created_at": transaction.created_at.isoformat() if transaction.created_at else None,
            "updated_at": transaction.updated_at.isoformat() if transaction.updated_at else None
        }

    # ==============================================================
    # GET LIST TRANSACTIONS
    # ==============================================================
    @staticmethod
    def get_transactions(
        db: Session,
        user_id: int,
        page: int = 1,
        limit: int = 20
    ):
        transactions, total = (
            TransactionRepository.get_transactions(
                db=db,
                user_id=user_id,
                page=page,
                limit=limit
            )
        )

        total_pages = ceil(total / limit)
        data = []

        for transaction in transactions:
            details = []
            for detail in transaction.transaction_detail:
                details.append({
                    "detail_id": detail.detail_id,
                    "quantity": float(detail.quantity),
                    "unit": detail.unit,
                    "unit_price": float(detail.unit_price),
                    "subtotal": float(detail.subtotal),
                    "product_id": detail.product_id,
                    "product": (
                        {
                            "name": detail.product.name,
                            "image": detail.product.img
                        }
                        if detail.product
                        else None
                    )
                })

            data.append({
                "transaction_id": transaction.transaction_id,
                "intent": (
                    transaction.intent.name_intent
                    if transaction.intent
                    else None
                ),
                "account": (
                    {
                        "name": transaction.account.name,
                        "type": transaction.account.type,
                    }
                    if transaction.account
                    else None
                ),
                "customer": (
                    {
                        "name": transaction.customer.name,
                    }
                    if transaction.customer
                    else None
                ),
                "supplier": (
                    {
                        "name": transaction.supplier.name,
                    }
                    if transaction.supplier
                    else None
                ),
                "total_amount": float(transaction.total_amount),
                "payment_status": transaction.payment_status,
                "input_method": transaction.input_method,
                "input_text": transaction.input_text,
                "transaction_date": (
                    transaction.transaction_date.isoformat()
                    if transaction.transaction_date
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

    # ==============================================================
    # GET TRANSACTION BY ID
    # ==============================================================
    @staticmethod
    def get_transaction_by_id(
        db: Session,
        user_id: int,
        transaction_id: int
    ):
        transaction = (
            TransactionRepository.get_transaction_by_id(
                db=db,
                user_id=user_id,
                transaction_id=transaction_id
            )
        )

        if not transaction:
            raise ValueError("Không tìm thấy giao dịch")

        details = []
        for detail in transaction.transaction_detail:
            details.append({
                "detail_id": detail.detail_id,
                "product_id": detail.product_id,
                "quantity": float(detail.quantity),
                "unit": detail.unit,
                "unit_price": float(detail.unit_price),
                "subtotal": float(detail.subtotal),
                "product": (
                    {
                        "name": detail.product.name,
                        "image": detail.product.img
                    }
                    if detail.product
                    else None
                )
            })

        return {
            "transaction_id": transaction.transaction_id,
            "intent": (
                transaction.intent.name_intent
                if transaction.intent
                else None
            ),
            "account": (
                {
                    "account_id": transaction.account.account_id,
                    "name": transaction.account.name,
                    "type": transaction.account.type
                }
                if transaction.account
                else None
            ),
            "customer": (
                {
                    "name": transaction.customer.name
                }
                if transaction.customer
                else None
            ),
            "supplier": (
                {
                    "name": transaction.supplier.name
                }
                if transaction.supplier
                else None
            ),
            "total_amount": float(transaction.total_amount),
            "payment_status": transaction.payment_status,
            "input_method": transaction.input_method,
            "input_text": transaction.input_text,
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

    # ==============================================================
    # UPDATE TRANSACTION
    # ==============================================================
    @staticmethod
    def update_transaction(
        db: Session,
        user_id: int,
        transaction_id: int,
        data: dict
    ):
        try:
            transaction = (
                db.query(Transaction)
                .filter(
                    Transaction.transaction_id == transaction_id,
                    Transaction.user_id == user_id
                )
                .first()
            )

            if not transaction:
                raise HTTPException(
                    status_code=404,
                    detail="Không tìm thấy giao dịch"
                )

            old_intent = (
                transaction.intent.name_intent
                if transaction.intent
                else None
            )

            old_amount = Decimal(
                str(transaction.total_amount or 0)
            )

            old_account_id = transaction.account_id
            old_payment_status = transaction.payment_status

            old_inventory = (
                db.query(InventoryTransaction)
                .filter(
                    InventoryTransaction.transaction_id == transaction_id,
                    InventoryTransaction.user_id == user_id
                )
                .all()
            )

            old_product_ids = set()
            for inventory in old_inventory:
                if inventory.product_id:
                    old_product_ids.add(inventory.product_id)

            old_details = (
                db.query(TransactionDetail)
                .filter(
                    TransactionDetail.transaction_id == transaction_id
                )
                .all()
            )

            for detail in old_details:
                if detail.product_id:
                    old_product_ids.add(detail.product_id)

            MONEY_IN_INTENTS = {
                "ban_hang",
                "thu_tien",
                "thu_no_phai_thu",
                "thu_no_khach_hang"
            }

            MONEY_OUT_INTENTS = {
                "nhap_hang",
                "chi_tien",
                "tra_no_phai_tra",
                "tra_no_nha_cung_cap",
                "tra_no_cung_cap",
                "hoan_tien",
                "hang_hong"
            }

            INVENTORY_OUT_INTENTS = {
                "ban_hang",
                "ghi_no_khach_hang",
                "ghi_no_phai_thu"
            }

            INVENTORY_IN_INTENTS = {
                "nhap_hang",
                "ghi_no_nha_cung_cap"
            }

            DEBT_INTENTS = {
                "ghi_no_khach_hang",
                "ghi_no_phai_thu",
                "ghi_no_nha_cung_cap",
                "ghi_no_phai_tra"
            }

            RECEIVABLE_DEBT_INTENTS = {
                "ghi_no_khach_hang",
                "ghi_no_phai_thu"
            }

            PAYABLE_DEBT_INTENTS = {
                "ghi_no_nha_cung_cap",
                "ghi_no_phai_tra"
            }

            intent_name = data.get("intent")
            if intent_name is None:
                intent_name = old_intent

            if not intent_name:
                raise HTTPException(
                    status_code=400,
                    detail="Giao dịch phải có intent"
                )

            intent_name = str(intent_name).lower().strip()
            intent_name = unicodedata.normalize("NFD", intent_name)
            intent_name = "".join(
                c for c in intent_name
                if unicodedata.category(c) != "Mn"
            )
            intent_name = intent_name.replace(" ", "_")

            new_intent = (
                db.query(Intent)
                .filter(Intent.name_intent == intent_name)
                .first()
            )

            if not new_intent:
                raise HTTPException(
                    status_code=400,
                    detail=f"Intent '{intent_name}' không tồn tại"
                )

            transaction.intent_id = new_intent.intent_id

            # Hoàn tác account cũ
            if (
                old_payment_status == "Đã thanh toán"
                and old_account_id
                and old_intent
            ):
                old_account = (
                    db.query(Account)
                    .filter(
                        Account.account_id == old_account_id,
                        Account.user_id == user_id
                    )
                    .first()
                )
                if old_account:
                    if old_intent in MONEY_IN_INTENTS:
                        old_account.balance -= old_amount
                    elif old_intent in MONEY_OUT_INTENTS:
                        old_account.balance += old_amount

            # Xóa inventory & details cũ
            for inventory in old_inventory:
                db.delete(inventory)
            db.flush()

            for detail in old_details:
                db.delete(detail)
            db.flush()

            old_debt = (
                db.query(Debt)
                .filter(
                    Debt.transaction_id == transaction_id,
                    Debt.user_id == user_id
                )
                .first()
            )

            if old_debt:
                db.delete(old_debt)
            db.flush()

            details_data = data.get("details", [])
            new_product_ids = set()
            total_amount = Decimal("0")

            for item in details_data:
                product_name = item.get("product")
                if not product_name:
                    raise HTTPException(status_code=400, detail="Không có tên sản phẩm")

                quantity = Decimal(str(item.get("quantity", 0)))
                if quantity <= 0:
                    raise HTTPException(status_code=400, detail="Quantity phải lớn hơn 0")

                unit = item.get("unit", "")
                unit_price = Decimal(str(item.get("unit_price", 0)))

                product_obj = get_product_by_name(db=db, user_id=user_id, name=product_name)
                if not product_obj:
                    raise HTTPException(status_code=400, detail=f"Sản phẩm '{product_name}' không tồn tại")

                new_product_ids.add(product_obj.product_id)
                subtotal = quantity * unit_price
                total_amount += subtotal

                new_detail = TransactionDetail(
                    transaction_id=transaction_id,
                    product_id=product_obj.product_id,
                    quantity=quantity,
                    unit=unit,
                    unit_price=unit_price,
                    subtotal=subtotal
                )
                db.add(new_detail)

            db.flush()
            transaction.total_amount = total_amount
            new_amount = total_amount

            # Rebuild Inventory mới
            inventory_type = None
            if intent_name in INVENTORY_OUT_INTENTS:
                inventory_type = "OUT"
            elif intent_name in INVENTORY_IN_INTENTS:
                inventory_type = "IN"

            if inventory_type:
                for item in details_data:
                    product_obj = get_product_by_name(db=db, user_id=user_id, name=item.get("product"))
                    if product_obj:
                        inventory = InventoryTransaction(
                            user_id=user_id,
                            product_id=product_obj.product_id,
                            transaction_id=transaction_id,
                            type=inventory_type,
                            quantity=Decimal(str(item.get("quantity", 0))),
                            unit=item.get("unit", ""),
                            quantity_before=Decimal("0"),
                            quantity_after=Decimal("0"),
                            note="Cập nhật tồn kho từ giao dịch"
                        )
                        db.add(inventory)
            db.flush()

            # Tạo Debt mới nếu thuộc nhóm debt (sử dụng cột total_debt chuẩn ERD)
            new_debt = None
            if intent_name in DEBT_INTENTS:
                if intent_name in RECEIVABLE_DEBT_INTENTS:
                    new_debt = Debt(
                        transaction_id=transaction_id,
                        user_id=user_id,
                        customer_id=transaction.customer_id,
                        supplier_id=None,
                        direction="RECEIVABLE",
                        total_debt=new_amount,
                        status="UNPAID"
                    )
                elif intent_name in PAYABLE_DEBT_INTENTS:
                    new_debt = Debt(
                        transaction_id=transaction_id,
                        user_id=user_id,
                        customer_id=None,
                        supplier_id=transaction.supplier_id,
                        direction="PAYABLE",
                        total_debt=new_amount,
                        status="UNPAID"
                    )
                if new_debt:
                    db.add(new_debt)
                    db.flush()

            db.commit()
            db.refresh(transaction)

            return {
                "success": True,
                "message": "Cập nhật giao dịch thành công",
                "transaction_id": transaction.transaction_id,
                "intent": intent_name,
                "total_amount": float(transaction.total_amount),
                "debt_id": new_debt.debt_id if new_debt else None
            }

        except HTTPException:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Cập nhật giao dịch thất bại: {str(e)}")

    # ==============================================================
    # DELETE TRANSACTION
    # ==============================================================
    @staticmethod
    def delete_transaction(
        db: Session,
        user_id: int,
        transaction_id: int
    ):
        try:
            transaction = (
                db.query(Transaction)
                .filter(
                    Transaction.transaction_id == transaction_id,
                    Transaction.user_id == user_id
                )
                .first()
            )

            if not transaction:
                raise HTTPException(
                    status_code=404,
                    detail="Không tìm thấy giao dịch"
                )

            if getattr(transaction, "is_deleted", False):
                raise HTTPException(
                    status_code=400,
                    detail="Giao dịch đã được xóa"
                )

            intent_name = (
                transaction.intent.name_intent
                if transaction.intent
                else None
            )

            amount = Decimal(
                str(transaction.total_amount or 0)
            )

            old_account_id = transaction.account_id
            payment_status = transaction.payment_status

            MONEY_IN_INTENTS = {
                "ban_hang",
                "thu_tien",
                "thu_no_phai_thu",
                "thu_no_khach_hang"
            }

            MONEY_OUT_INTENTS = {
                "nhap_hang",
                "chi_tien",
                "tra_no_phai_tra",
                "tra_no_nha_cung_cap",
                "tra_no_cung_cap",
                "hoan_tien",
                "hang_hong"
            }

            # Hoàn tác Account
            if (
                payment_status == "Đã thanh toán"
                and old_account_id
            ):
                account = (
                    db.query(Account)
                    .filter(
                        Account.account_id == old_account_id,
                        Account.user_id == user_id
                    )
                    .first()
                )

                if account:
                    if intent_name in MONEY_IN_INTENTS:
                        account.balance -= amount
                    elif intent_name in MONEY_OUT_INTENTS:
                        account.balance += amount

            # Xóa Inventory & Details & Debt liên quan
            inventories = (
                db.query(InventoryTransaction)
                .filter(
                    InventoryTransaction.transaction_id == transaction_id,
                    InventoryTransaction.user_id == user_id
                )
                .all()
            )

            affected_product_ids = set()
            for inventory in inventories:
                if inventory.product_id:
                    affected_product_ids.add(inventory.product_id)
                db.delete(inventory)

            details = (
                db.query(TransactionDetail)
                .filter(TransactionDetail.transaction_id == transaction_id)
                .all()
            )
            for detail in details:
                if detail.product_id:
                    affected_product_ids.add(detail.product_id)

            debt = (
                db.query(Debt)
                .filter(
                    Debt.transaction_id == transaction_id,
                    Debt.user_id == user_id
                )
                .first()
            )

            if debt:
                db.delete(debt)

            db.flush()

            # Xóa mềm Transaction
            transaction.is_deleted = True
            transaction.deleted_at = datetime.now()
            db.flush()

            db.commit()

            return {
                "success": True,
                "message": "Xóa giao dịch thành công",
                "transaction_id": transaction_id,
                "intent": intent_name,
                "deleted": True,
                "inventory_product_ids": list(affected_product_ids)
            }

        except HTTPException:
            db.rollback()
            raise

        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Xóa giao dịch thất bại: {str(e)}"
            )