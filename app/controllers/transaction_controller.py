from sqlalchemy.orm import Session
from app.services.transaction_service import TransactionService
from app.schemas.transaction_schema import TransactionCreateRequest


class TransactionController:

    @staticmethod
    def create_transaction(
        db: Session,
        user_id: int,
        request: TransactionCreateRequest
    ):
        """
        Tạo giao dịch. Tự động nhận diện:
        - Nếu request có `details` hoặc các trường FK ID chuẩn (intent_id, category_id, account_id...)
          thì gọi create_direct_transaction theo đúng docs/erd.md.
        - Nếu request chứa các trường phẳng NLP (product, price, quantity, text...)
          thì gom thành payload và gọi save_groq_transaction.
        """
        is_direct = bool(
            request.details
            or request.category_id is not None
            or request.account_id is not None
            or (request.intent_id is not None and not request.product)
        )

        if is_direct:
            result = TransactionService.create_direct_transaction(
                db=db,
                user_id=user_id,
                request=request
            )
        else:
            # Chế độ tương thích ngược Flat NLP / Groq Voice
            groq_result_dict = {
                "transaction_analysis": {
                    "text": request.text or request.input_text or "",
                    "intent": request.intent or "",
                    "type": request.type or "",
                    "entities": {
                        "product": request.product,
                        "price": request.price or request.total_amount,
                        "quantity": request.quantity,
                        "unit": request.unit,
                        "customer": request.customer,
                        "supplier": request.supplier,
                        "date": request.date or (request.transaction_date.isoformat() if request.transaction_date else None),
                        "payment": request.payment
                    }
                }
            }

            result = TransactionService.save_groq_transaction(
                db=db,
                user_id=user_id,
                account_id=request.account_id,
                groq_result=groq_result_dict
            )

        # Tự động liên kết Voice_Record nếu request có voice_id hoặc tự khớp bản ghi voice gần nhất
        tx_id = result.get("transaction_id") if isinstance(result, dict) else getattr(result, "transaction_id", None)
        voice_id = getattr(request, "voice_id", None)
        if tx_id:
            try:
                from app.services.voice_record_service import link_voice_record_to_transaction
                from app.models.voice_record_model import VoiceRecord
                from app.models.transaction_model import Transaction
                from datetime import datetime, timedelta

                if not voice_id and user_id:
                    cutoff = datetime.now() - timedelta(minutes=15)
                    recent_voice = db.query(VoiceRecord).filter(
                        VoiceRecord.user_id == user_id,
                        VoiceRecord.transaction_id.is_(None),
                        VoiceRecord.created_at >= cutoff
                    ).order_by(VoiceRecord.created_at.desc()).first()
                    if recent_voice:
                        voice_id = recent_voice.voice_id

                if voice_id:
                    link_voice_record_to_transaction(
                        db=db,
                        voice_id=voice_id,
                        transaction_id=tx_id,
                        user_id=user_id
                    )
                    tx_obj = db.query(Transaction).filter(Transaction.transaction_id == tx_id).first()
                    if tx_obj and tx_obj.input_method != "VOICE":
                        tx_obj.input_method = "VOICE"
                        db.commit()
            except Exception:
                pass

        # Kích hoạt sự kiện WebSocket realtime thông báo Dashboard & Report
        try:
            from app.services.websocket_manager import trigger_report_update
            tx_id = result.get("transaction_id") if isinstance(result, dict) else getattr(result, "transaction_id", None)
            trigger_report_update(user_id=user_id, transaction_id=tx_id)
        except Exception:
            pass

        return result

    @staticmethod
    def save_groq_transaction(
        db: Session,
        user_id: int,
        account_id: int | None,
        groq_result: dict
    ):
        result = TransactionService.save_groq_transaction(
            db=db,
            user_id=user_id,
            account_id=account_id,
            groq_result=groq_result
        )
        try:
            from app.services.websocket_manager import trigger_report_update
            tx_id = result.get("transaction_id") if isinstance(result, dict) else getattr(result, "transaction_id", None)
            trigger_report_update(user_id=user_id, transaction_id=tx_id)
        except Exception:
            pass
        return result

    @staticmethod
    def get_transactions(
        db: Session,
        user_id: int,
        page: int = 1,
        limit: int = 10,
        intent_type: str | None = None,
        intent: str | None = None,
    ):
        return TransactionService.get_transactions(
            db=db,
            user_id=user_id,
            page=page,
            limit=limit,
            intent_type=intent_type,
            intent_name=intent,
        )

    @staticmethod
    def get_transaction_by_id(
        db: Session,
        user_id: int,
        transaction_id: int
    ):
        return TransactionService.get_transaction_by_id(
            db=db,
            user_id=user_id,
            transaction_id=transaction_id
        )