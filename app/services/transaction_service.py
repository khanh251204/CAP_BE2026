from math import ceil
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc

# IMPORT CÁC MODELS
from app.models.transaction_model import Transaction
from app.models.transactionDetail_model import TransactionDetail
from app.models.customer_model import Customer
from app.models.supplier_model import Supplier
from app.models.account_model import Account
from app.models.product_model import Product
from app.models.intent_model import Intent
from datetime import datetime, timedelta

# IMPORT REPOSITORIES
from app.repositories.transaction_repository import TransactionRepository
from app.repositories.product_repository import (
    get_product_by_name,
    create_product
)

class TransactionService:

    # # ============================================================
    # # Lấy list giao dịch
    # # ============================================================
    # @staticmethod
    # def get_transactions(db: Session, user_id: int, page: int, limit: int):
    #     transactions, total = TransactionRepository.get_transactions(
    #         db=db, user_id=user_id, page=page, limit=limit
    #     )

    #     total_pages = ceil(total / limit) if total > 0 else 0
    #     data = []

    #     for transaction in transactions:
    #         transaction_detail_data = []
    #         for detail in transaction.transaction_detail:
    #             product_data = None
    #             if detail.product:
    #                 product_data = {
    #                     "name": detail.product.name,
    #                     "image": detail.product.img,
    #                 }

    #             transaction_detail_data.append({
    #                 "detail_id": detail.detail_id,
    #                 "transaction_id": detail.transaction_id,
    #                 "quantity": float(detail.quantity) if detail.quantity is not None else None,
    #                 "unit": detail.unit,
    #                 "unit_price": float(detail.unit_price) if detail.unit_price is not None else None,
    #                 "subtotal": float(detail.subtotal) if detail.subtotal is not None else None,
    #                 "product": product_data
    #             })

    #         customer_data = {"name": transaction.customer.name} if transaction.customer else None
    #         supplier_data = {"name": transaction.supplier.name} if transaction.supplier else None
            
    #         intent_data = None
    #         if transaction.intent: 
    #             intent_data = { 
    #                 "name_intent": transaction.intent.name_intent, 
    #                 "type_intent": transaction.intent.type,
    #             }

    #         account_data = {"type": transaction.account.type} if transaction.account else None

    #         data.append({
    #             "transaction_id": transaction.transaction_id,
    #             "input_text": transaction.input_text,
    #             "intent": intent_data,
    #             "total_amount": float(transaction.total_amount) if transaction.total_amount is not None else None,
    #             "payment_status": transaction.payment_status,
    #             "input_method": transaction.input_method,
    #             "transaction_date": transaction.transaction_date.isoformat() if transaction.transaction_date else None,
    #             "account": account_data,
    #             "customer": customer_data,
    #             "supplier": supplier_data,
    #             "transaction_detail": transaction_detail_data
    #         })

    #     return {
    #         "success": True,
    #         "data": data,
    #         "pagination": {
    #             "page": page,
    #             "limit": limit,
    #             "total": total,
    #             "total_pages": total_pages
    #         }
    #     }
    
    # # ============================================================
    # # Lấy giao dịch theo ID
    # # ============================================================
    # @staticmethod
    # def get_transaction_detail(db: Session, user_id: int, transaction_id: int):
    #     transaction = TransactionRepository.get_transaction_by_id(
    #         db=db, user_id=user_id, transaction_id=transaction_id
    #     )

    #     if not transaction:
    #         return {
    #             "success": False,
    #             "message": "Không tìm thấy giao dịch"
    #         }

    #     transaction_detail_data = []
    #     for detail in transaction.transaction_detail:
    #         product_data = None
    #         if detail.product:
    #             product_data = {
    #                 "name": detail.product.name,
    #                 "image": detail.product.img,
    #             }
        
    #         transaction_detail_data.append({
    #             "quantity": float(detail.quantity) if detail.quantity is not None else None,
    #             "unit": detail.unit,
    #             "unit_price": float(detail.unit_price) if detail.unit_price is not None else None,
    #             "subtotal": float(detail.subtotal) if detail.subtotal is not None else None,
    #             "product": product_data
    #         })

    #     customer_data = {"name": transaction.customer.name} if transaction.customer else None
    #     supplier_data = {"name": transaction.supplier.name} if transaction.supplier else None
        
    #     intent_data = None
    #     if transaction.intent: 
    #         intent_data = { 
    #             "name_intent": transaction.intent.name_intent, 
    #             "type_intent": transaction.intent.type
    #         }
            
    #     account_data = {"type": transaction.account.type} if transaction.account else None

    #     return {
    #         "success": True,
    #         "data": {
    #             "transaction_id": transaction.transaction_id,
    #             "input_text": transaction.input_text,
    #             "intent": intent_data,
    #             "total_amount": float(transaction.total_amount) if transaction.total_amount is not None else None,
    #             "payment_status": transaction.payment_status,
    #             "input_method": transaction.input_method,
    #             "transaction_date": transaction.transaction_date.isoformat() if transaction.transaction_date else None,
    #             "account": account_data,
    #             "customer": customer_data,
    #             "supplier": supplier_data,
    #             "transaction_detail": transaction_detail_data
    #         }
    #     }

    # ============================================================
    # HÀM XỬ LÝ LƯU GIAO DỊCH TỪ GROQ
    # ============================================================
    @staticmethod
    def save_groq_transaction(
        db: Session,
        user_id: int,
        account_id: int | None,
        groq_result: dict
    ):
        INTENT_MAPPING = {
            "bán_hàng": 1,
            "nhập_hàng": 2,
            "thu_tiền": 3,
            "chi_tiền": 4,
            "chuyển_tiền": 5,
            "hoàn_tiền": 6,
            "ghi_nợ_phải_thu": 7,
            "thu_nợ_phải_thu": 8,
            "ghi_nợ_phải_trả": 9,
            "trả_nợ_phải_trả": 10,
        }
         
        analysis = groq_result.get("transaction_analysis", {})
        entities = analysis.get("entities", {})

        product_name = entities.get("product")
        quantity = entities.get("quantity")
        price = entities.get("price")
        unit = entities.get("unit")
    
        payment_method = entities.get("payment", "")
        customer_name = entities.get("customer")
        supplier_name = entities.get("supplier")
        groq_intent = analysis.get("intent", "").lower().strip()
        nlp_date = entities.get("date")
        transaction_date = datetime.now()  # Mặc định (null) là hôm nay/bây giờ

        if nlp_date:
            nlp_date_lower = str(nlp_date).lower().strip()
            
            # Xử lý các từ khóa tương đối tiếng Việt
            if "hôm qua" in nlp_date_lower:
                transaction_date = datetime.now() - timedelta(days=1)
            elif "hôm kia" in nlp_date_lower:
                transaction_date = datetime.now() - timedelta(days=2)
            elif "ngày mai" in nlp_date_lower:
                transaction_date = datetime.now() + timedelta(days=1)
            else:
                # Nếu Groq trả về ngày cụ thể (vd: "2026-08-20" hoặc "20/08/2026")
                try:
                    # Thử parse dạng chuẩn ISO (YYYY-MM-DD) AI hay trả về
                    if len(nlp_date_lower) >= 10:
                        # Cắt lấy 10 ký tự đầu "YYYY-MM-DD"
                        transaction_date = datetime.fromisoformat(nlp_date_lower[:10])
                except Exception:
                    # Nếu AI trả về format lạ không đọc được, cứ lấy mặc định hôm nay
                    pass

        if not product_name:
            raise ValueError("Thiếu product")
        if not quantity:
            raise ValueError("Thiếu quantity")
        if not price:
            raise ValueError("Thiếu price")

        # 1. MAP INTENT
        mapped_intent_id = INTENT_MAPPING.get(groq_intent, None)

        # 2. XỬ LÝ ACCOUNT (Viết hoa Account, dùng db_account)
        if payment_method:
            payment_lower = payment_method.lower()
            if "tiền mặt" in payment_lower:
                acc_type = "CASH"
            elif "chuyển khoản" in payment_lower or "ngân hàng" in payment_lower:
                acc_type = "BANK"
            elif "momo" in payment_lower or "ví" in payment_lower or "zalopay" in payment_lower:
                acc_type = "E-WALLET"
            else:
                acc_type = "CASH"

            db_account = db.query(Account).filter(
                Account.user_id == user_id, 
                Account.type == acc_type
            ).first()

            if not db_account:
                db_account = Account(
                    user_id=user_id, 
                    name=f"Tài khoản {acc_type}", 
                    type=acc_type, 
                    balance=0
                )
                db.add(db_account)
                db.flush()
            
            account_id = db_account.account_id

        # 3. XỬ LÝ CUSTOMER (Viết hoa Customer, dùng db_customer)
        customer_id = None
        if customer_name:
            db_customer = db.query(Customer).filter(
                Customer.user_id == user_id, 
                Customer.name.ilike(customer_name)
            ).first()
        
            if not db_customer:
                db_customer = Customer(user_id=user_id, name=customer_name)
                db.add(db_customer)
                db.flush()
            customer_id = db_customer.customer_id

        # 4. XỬ LÝ SUPPLIER (Viết hoa Supplier, dùng db_supplier)
        supplier_id = None
        if supplier_name:
            db_supplier = db.query(Supplier).filter(
                Supplier.user_id == user_id, 
                Supplier.name.ilike(supplier_name)
            ).first()
        
            if not db_supplier:
                db_supplier = Supplier(user_id=user_id, name=supplier_name)
                db.add(db_supplier)
                db.flush()
            supplier_id = db_supplier.supplier_id

        # 5. TÍNH LẠI TỔNG TIỀN VÀ ĐƠN GIÁ (Thay thế phần 6 cũ)
        total_amount = float(price)
        qty = float(quantity) if quantity else 1.0
        
        # Đơn giá = Tổng tiền / Số lượng (phòng hờ trường hợp chia cho 0)
        unit_price = total_amount / qty if qty > 0 else total_amount

        # 6. XỬ LÝ PRODUCT (Đã sửa lại để lưu unit_price chuẩn)
        product = get_product_by_name(db=db, user_id=user_id, name=product_name)
        if not product:
            product = create_product(
                db=db, user_id=user_id, name=product_name, unit=unit, price=unit_price
            )
        else:
            product.unit_price = str(unit_price)  # Lưu đơn giá vừa tính, không lưu tổng tiền
            if unit:
                product.default_unit = unit

        # 7. TẠO TRANSACTION BẰNG REPOSITORY
        new_transaction = Transaction(
            user_id=user_id,
            account_id=account_id,
            intent_id=mapped_intent_id,
            customer_id=customer_id,
            supplier_id=supplier_id,
            total_amount=total_amount,
            payment_status="Đã thanh toán" if payment_method else "Chưa thanh toán",
            input_method="VOICE",
            input_text=analysis.get("text", ""),
            transaction_date = transaction_date
        )
    
        new_transaction = TransactionRepository.create_transaction(db, new_transaction)

        # 8. TẠO TRANSACTION DETAIL BẰNG REPOSITORY
        detail = TransactionDetail(
            transaction_id=new_transaction.transaction_id,
            product_id=product.product_id,
            quantity=quantity,
            unit=unit,
            unit_price=unit_price,
            subtotal=total_amount
        )
    
        TransactionRepository.create_transaction_detail(db, detail)

        # 9. HOÀN TẤT & LƯU LẠI
        db.commit()
        db.refresh(new_transaction)

        return {
            # "transaction_id": new_transaction.transaction_id,
            "intent_id": mapped_intent_id,
            "account_id": account_id,
            "customer_id": customer_id,
            "supplier_id": supplier_id,
            "product_id": product.product_id,
            "quantity": quantity,
            "unit": unit,
            "unit_price": unit_price,
            "total_amount": total_amount,
            "input_method": new_transaction.input_method,
            "input_text": analysis.get("text", ""),
            "transaction_date": transaction_date,
            "created_at": new_transaction.created_at.isoformat() if new_transaction.created_at else None,
            "updated_at": new_transaction.updated_at.isoformat() if new_transaction.updated_at else None

        }