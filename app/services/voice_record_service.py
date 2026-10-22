from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models.voice_record_model import VoiceRecord


def create_voice_record(
    db: Session,
    user_id: Optional[int] = None,
    audio_url: Optional[str] = None,
    transcript: Optional[str] = None,
    llm_output: Optional[Dict[str, Any]] = None,
    confidence: Optional[float] = None,
    processing_time: Optional[float] = None,
    intent: Optional[str] = None,
    status: str = "PROCESSING",
    error_message: Optional[str] = None,
    transaction_id: Optional[int] = None
) -> VoiceRecord:
    valid_user_id = None
    if user_id is not None:
        from app.models.user_model import User
        if db.query(User.user_id).filter(User.user_id == user_id).first():
            valid_user_id = user_id

    valid_tx_id = None
    if transaction_id is not None:
        from app.models.transaction_model import Transaction
        if db.query(Transaction.transaction_id).filter(Transaction.transaction_id == transaction_id).first():
            valid_tx_id = transaction_id

    # Trạng thái thành công chỉ khi đã có transaction_id xác nhận; ngược lại là PROCESSING
    record_status = status
    if valid_tx_id is not None and record_status == "PROCESSING":
        record_status = "SUCCESS"

    record = VoiceRecord(
        user_id=valid_user_id,
        transaction_id=valid_tx_id,
        audio_path=audio_url,
        transcript=transcript,
        intent=intent,
        status=record_status,
        confidence=confidence,
        processing_time=processing_time,
        error_message=error_message,
        llm_output=llm_output
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    # Ingest Data Lake Foundation (Decoupled, lỗi Data Lake không làm hỏng transaction nghiệp vụ)
    try:
        from app.services.data_lake_service import DataLakeService
        DataLakeService.ingest_record(record, db=db)
    except Exception:
        pass

    return record


def link_voice_record_to_transaction(
    db: Session,
    voice_id: int,
    transaction_id: int,
    user_id: Optional[int] = None,
    status: str = "SUCCESS"
) -> bool:
    """
    Liên kết VoiceRecord với Transaction sau khi người dùng bấm xác nhận đồng ý giao dịch.
    Trạng thái được cập nhật thành SUCCESS (Thành công) và đồng bộ sang Data Lake.
    """
    query = db.query(VoiceRecord).filter(VoiceRecord.voice_id == voice_id)
    if user_id is not None:
        query = query.filter((VoiceRecord.user_id == user_id) | (VoiceRecord.user_id.is_(None)))
    
    record = query.first()
    if not record:
        return False

    record.transaction_id = transaction_id
    record.status = status
    if user_id is not None and not record.user_id:
        record.user_id = user_id

    # Đảm bảo Transaction có input_method = 'VOICE' vì giao dịch phát sinh từ voice record
    from app.models.transaction_model import Transaction
    tx = db.query(Transaction).filter(Transaction.transaction_id == transaction_id).first()
    if tx and tx.input_method != "VOICE":
        tx.input_method = "VOICE"

    db.commit()

    # Cập nhật Data Lake snapshot sau khi giao dịch được xác nhận thành công
    try:
        from app.services.data_lake_service import DataLakeService
        DataLakeService.ingest_record(record, transaction=tx, db=db)
    except Exception:
        pass

    return True


def mark_voice_record_rejected(
    db: Session,
    voice_id: int,
    user_id: Optional[int] = None,
    reason: Optional[str] = "Người dùng không đồng ý xác nhận giao dịch"
) -> bool:
    """
    Đánh dấu bản ghi khi người dùng không đồng ý / từ chối / hủy bỏ giao dịch.
    Trạng thái cập nhật thành FAILED và đồng bộ sang Data Lake.
    """
    query = db.query(VoiceRecord).filter(VoiceRecord.voice_id == voice_id)
    if user_id is not None:
        query = query.filter((VoiceRecord.user_id == user_id) | (VoiceRecord.user_id.is_(None)))

    record = query.first()
    if not record:
        return False

    record.status = "FAILED"
    record.error_message = reason
    db.commit()

    try:
        from app.services.data_lake_service import DataLakeService
        DataLakeService.ingest_record(record, db=db)
    except Exception:
        pass

    return True
