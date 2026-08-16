from math import ceil

from app.repositories.transaction_repository import (
    TransactionRepository
)


class TransactionService:

    # lấy list giao dịch
    @staticmethod
    def get_transactions(
        db,
        user_id: int,
        page: int,
        limit: int
    ):

        transactions, total = (
            TransactionRepository.get_transactions(
                db=db,
                user_id=user_id,
                page=page,
                limit=limit
            )
        )

        total_pages = (
            ceil(total / limit)
            if total > 0
            else 0
        )

        data = []

        for transaction in transactions:

            transaction_detail_data = []

            for detail in transaction.transaction_detail:

                product_data = None

                if detail.product:
                    product_data = {
                        "product_id": detail.product.product_id,
                        "name": detail.product.name,
                        "image": detail.product.img,
                        "default_unit": detail.product.default_unit,
                        "unit_price": (
                            float(detail.product.unit_price)
                            if detail.product.unit_price is not None
                            else None
                        ),
                        "min_quantity": (
                            float(detail.product.min_quantity)
                            if detail.product.min_quantity is not None
                            else None
                        )
                    }

                transaction_detail_data.append({
                    "detail_id": detail.detail_id,
                    "transaction_id": detail.transaction_id,
                    "quantity": (
                        float(detail.quantity)
                        if detail.quantity is not None
                        else None
                    ),
                    "unit": detail.unit,
                    "unit_price": (
                        float(detail.unit_price)
                        if detail.unit_price is not None
                        else None
                    ),
                    "subtotal": (
                        float(detail.subtotal)
                        if detail.subtotal is not None
                        else None
                    ),
                    "product_id": detail.product_id,
                    "product": product_data
                })

                category_data = None
                if transaction.category: 
                    category_data = { 
                        "category_id": transaction.category.category_id, 
                        "name": transaction.category.name, 
                        "type_category": transaction.category.type_category 
                    }

                customer_data = None
                if transaction.customer: 
                    customer_data = { 
                        "customer_id": transaction.customer.customer_id, 
                        "name": transaction.customer.name, 
                        "phone_number": transaction.customer.phone_number, 
                        "note": transaction.customer.note 
                    }

                supplier_data = None
                if transaction.supplier: 
                    supplier_data = { 
                        "supplier_id": transaction.supplier.supplier_id, 
                        "name": transaction.supplier.name, 
                        "phone_number": transaction.supplier.phone_number, 
                        "note": transaction.supplier.note 
                    }
                intent_data = None
                if transaction.intent: 
                    intent_data = { 
                        "intent_id": transaction.intent.intent_id, 
                        "name_intent": transaction.intent.name_intent, 
                    }

                account_data = None
                if transaction.account:
                    account_data={
                        "account_id": transaction.account.account_id,
                        "name": transaction.account.name,
                        "type": transaction.account.type,
                        "balance": transaction.account.balance,
                        "currency": transaction.account.currency
            
                    }
                data.append({
                                "transaction_id": transaction.transaction_id,
                                "account_id": transaction.account_id,
                                "intent_id": transaction.intent_id,
                                "category_id": transaction.category_id,
                                "customer_id": transaction.customer_id,
                                "supplier_id": transaction.supplier_id,
                                "total_amount": (
                                    float(transaction.total_amount)
                                    if transaction.total_amount is not None
                                    else None
                                ),
                                "payment_status": transaction.payment_status,
                                "input_method": transaction.input_method,
                                "input_text": transaction.input_text,
                                "note": transaction.note,
                                "transaction_date": (
                                    transaction.transaction_date.isoformat()
                                    if transaction.transaction_date
                                    else None
                                ),
                                "account": account_data,
                                "category": category_data,
                                "customer": customer_data,
                                "supplier": supplier_data,
                                "intent": intent_data,
                                "transaction_detail": transaction_detail_data
                
                            }),
        return {
            "success": True,
            "data": data ,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "total_pages": total_pages
            }
        }
    
    # lấy giao dịch theo id
    @staticmethod
    def get_transaction_detail(
        db,
        user_id: int,
        transaction_id: int
    ):

        transaction = (
            TransactionRepository
            .get_transaction_by_id(
                db=db,
                user_id=user_id,
                transaction_id=transaction_id
            )
        )

        if not transaction:
            return {
                "success": False,
                "message": "Không tìm thấy giao dịch"
            }

        transaction_detail_data = []
        
        for detail in transaction.transaction_detail:
        
            product_data = None
        
            if detail.product:
                product_data = {
                    "product_id": detail.product.product_id,
                    "name": detail.product.name,
                    "image": detail.product.img,
                    "default_unit": detail.product.default_unit,
                    "unit_price": (
                        float(detail.product.unit_price)
                        if detail.product.unit_price is not None
                        else None
                    ),
                    "min_quantity": (
                        float(detail.product.min_quantity)
                        if detail.product.min_quantity is not None
                        else None
                    )
                }
        
            transaction_detail_data.append({
                "detail_id": detail.detail_id,
                "transaction_id": detail.transaction_id,
                "quantity": (
                    float(detail.quantity)
                    if detail.quantity is not None
                    else None
                ),
                "unit": detail.unit,
                "unit_price": (
                    float(detail.unit_price)
                    if detail.unit_price is not None
                    else None
                ),
                "subtotal": (
                    float(detail.subtotal)
                    if detail.subtotal is not None
                    else None
                ),
                "product_id": detail.product_id,
                "product": product_data
            })


        category_data = None
        if transaction.category: 
            category_data = { 
                "category_id": transaction.category.category_id, 
                "name": transaction.category.name, 
                "type_category": transaction.category.type_category 
            }
        
        customer_data = None
        if transaction.customer: 
            customer_data = { 
                "customer_id": transaction.customer.customer_id, 
                "name": transaction.customer.name, 
                "phone_number": transaction.customer.phone_number, 
                "note": transaction.customer.note 
            }
        
        supplier_data = None
        if transaction.supplier: 
            supplier_data = { 
                "supplier_id": transaction.supplier.supplier_id, 
                "name": transaction.supplier.name, 
                "phone_number": transaction.supplier.phone_number, 
                "note": transaction.supplier.note 
            }
        intent_data = None
        if transaction.intent: 
            intent_data = { 
                "intent_id": transaction.intent.intent_id, 
                "name_intent": transaction.intent.name_intent, 
            }
        account_data = None
        if transaction.account:
            account_data={
                "account_id": transaction.account.account_id,
                "name": transaction.account.name,
                "type": transaction.account.type,
                "balance": transaction.account.balance,
                "currency": transaction.account.currency
                    
            }
        return {
            "success": True,
            "data": {
                "transaction_id": transaction.transaction_id,
                "account_id": transaction.account_id,
                "intent_id": transaction.intent_id,
                "category_id": transaction.category_id,
                "customer_id": transaction.customer_id,
                "supplier_id": transaction.supplier_id,
                "total_amount": (
                    float(transaction.total_amount)
                    if transaction.total_amount is not None
                    else None
                ),
                "payment_status": transaction.payment_status,
                "input_method": transaction.input_method,
                "input_text": transaction.input_text,
                "note": transaction.note,
                "transaction_date": (
                    transaction.transaction_date.isoformat()
                    if transaction.transaction_date
                    else None
                ),
                "account": account_data,
                "category": category_data,
                "customer": customer_data,
                "supplier": supplier_data,
                "intent": intent_data,
                "transaction_detail": transaction_detail_data
            
            }
        }


    # 