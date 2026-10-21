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

        # Xác định input_method: API tạo giao dịch mặc định là MANUAL
        # Chỉ thành VOICE khi request có voice_id hoặc truyền rõ ràng input_method="VOICE"
        voice_id = getattr(request, "voice_id", None)
        raw_method = getattr(request, "input_method", None)
        if voice_id:
            input_method = "VOICE"
        elif raw_method and str(raw_method).upper().strip() in {"VOICE", "MANUAL"}:
            input_method = str(raw_method).upper().strip()
        else:
            input_method = "MANUAL"

        if is_direct:
            request.input_method = input_method
            result = TransactionService.create_direct_transaction(
                db=db,
                user_id=user_id,
                request=request
            )
        else:
            # Chế độ tương thích ngược Flat NLP / Quick Form
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
                groq_result=groq_result_dict,
                input_method=input_method
            )

        # Chỉ liên kết Voice_Record khi request THỰC SỰ có truyền voice_id (luồng voice -> api)
        tx_id = result.get("transaction_id") if isinstance(result, dict) else getattr(result, "transaction_id", None)
        if tx_id and voice_id:
            try:
                from app.services.voice_record_service import link_voice_record_to_transaction
                link_voice_record_to_transaction(
                    db=db,
                    voice_id=voice_id,
                    transaction_id=tx_id,
                    user_id=user_id
                )
            except Exception:
                pass

        # Kích hoạt sự kiện WebSocket realtime thông báo Dashboard & Report
        try:
            from app.services.websocket_manager import trigger_report_update
            tx_id = result.get("transaction_id") if isinstance(result, dict) else getattr(result, "transaction_id", None)
            trigger_report_update(user_id=user_id, transaction_id=tx_id)
        except Exception:
            pass

        # Gửi thông báo & FCM khi giao dịch ở trạng thái chờ (PENDING / ghi nợ chưa thanh toán)
        try:
            p_status = result.get("payment_status") if isinstance(result, dict) else getattr(result, "payment_status", None)
            total_amt = result.get("total_amount") if isinstance(result, dict) else getattr(result, "total_amount", 0)
            intent_n = result.get("intent_name") or result.get("intent") or "giao dịch"
            if p_status == "PENDING":
                from app.services.notification_service import NotificationService
                amt_str = f"{int(float(total_amt)):,}đ" if total_amt else "0đ"
                NotificationService.create_notification({
                    "userId": str(user_id),
                    "title": "Giao dịch chờ thanh toán ⏳",
                    "description": f"Giao dịch '{intent_n}' trị giá {amt_str} đang ở trạng thái chờ xử lý/chưa thanh toán.",
                    "notificationType": "TRANSACTION_PENDING",
                    "icon": "clock-outline",
                    "iconColor": "#FFFFFF",
                    "borderColor": "#F59E0B",
                    "isRead": False
                })
        except Exception:
            pass

        return result

    @staticmethod
    def save_groq_transaction(
        db: Session,
        user_id: int,
        account_id: int | None,
        groq_result: dict,
        input_method: str | None = None
    ):
        result = TransactionService.save_groq_transaction(
            db=db,
            user_id=user_id,
            account_id=account_id,
            groq_result=groq_result,
            input_method=input_method
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

    @staticmethod
    def delete_transaction(
        db: Session,
        user_id: int,
        transaction_id: int
    ):
        return TransactionService.delete_transaction(
            db=db,
            user_id=user_id,
            transaction_id=transaction_id
        )