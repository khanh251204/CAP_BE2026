from math import ceil

from app.repositories.transaction_repository import (
    TransactionRepository
)


class TransactionService:

    @staticmethod
    def get_transactions(
        db,
        page: int,
        limit: int
    ):

        transactions, total = (
            TransactionRepository.get_transactions(
                db=db,
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

            data.append({
                "transaction_id": transaction.transaction_id,
                "user_id": transaction.user_id,
                "account_id": transaction.account_id,
                "customer_id": transaction.customer_id,
                "supplier_id": transaction.supplier_id,
                "category_id": transaction.category_id,
                "type": transaction.type,
                "intent": transaction.intent,
                "total_amount": transaction.total_amount,
                "payment_status": transaction.payment_status,
                "input_method": transaction.input_method,
                "note": transaction.note,
                "transaction_date": (
                    transaction.transaction_date.isoformat()
                    if transaction.transaction_date
                    else None
                ),
                "created_at": transaction.created_at,
                "update": transaction.updated_at
            })

        return {
            "success": True,
            "data": data,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "total_pages": total_pages
            }
        }

    @staticmethod
    def get_transaction_detail(
        db,
        transaction_id: int
    ):

        transaction = (
            TransactionRepository
            .get_transaction_by_id(
                db=db,
                transaction_id=transaction_id
            )
        )

        if not transaction:
            return {
                "success": False,
                "message": "Không tìm thấy giao dịch"
            }

        details = []

        for detail in transaction.details:

            product_data = None

            if detail.product:
                product_data = {
                    "product_id": detail.product.product_id,
                    "name": detail.product.name,
                    "image": detail.product.img,
                    "default_unit": detail.product.default_unit,
                    "min_quantity": (
                        float(detail.product.min_quantity)
                        if detail.product.min_quantity is not None
                        else None
                    )
                }

            details.append({
                "detail_id": detail.detail_id,
                "transaction_id": detail.transaction_id,
                "product_id": detail.product_id,

        

                "quantity": (
                    float(detail.quantity)
                    if detail.quantity is not None
                    else None
                ),

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

                "product": product_data
            })

        return {
            "success": True,

            "data": {
                "transaction_id": transaction.transaction_id,
                "user_id": transaction.user_id,
                "account_id": transaction.account_id,
                "customer_id": transaction.customer_id,
                "supplier_id": transaction.supplier_id,
                "category_id": transaction.category_id,

                "type": transaction.type,
                "intent": transaction.intent,

                "total_amount": (
                    float(transaction.total_amount)
                    if transaction.total_amount is not None
                    else None
                ),

                "payment_status": transaction.payment_status,
                "input_method": transaction.input_method,
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

                # ⭐ CHI TIẾT GIAO DỊCH
                "details": details
            }
        }