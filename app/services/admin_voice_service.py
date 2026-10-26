import math
import os
import mimetypes
from datetime import datetime
from typing import Optional, Dict, Any, List

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.admin_voice_repository import AdminVoiceRepository
from app.schemas.admin_voice_schema import (
    AdminVoiceListResponse,
    AdminVoiceListItem,
    AdminVoicePagination,
    AdminVoiceDetailResponse,
    AdminVoiceDetailUser,
    AdminVoiceDetailAudio,
    AdminVoiceDetailAiResult,
    AdminVoiceDetailValidation,
    AdminVoiceDetailTransaction,
    AdminVoiceDetailProcessing,
    AdminVoiceAiResultResponse,
)


class AdminVoiceService:

    @staticmethod
    def _normalize_processing_time_ms(processing_time: Optional[float]) -> Optional[int]:
        if processing_time is None:
            return None
        # Nếu đã lưu theo ms (> 100) thì làm tròn nguyên, nếu là giây (< 100) thì nhân 1000
        if processing_time > 100.0:
            return int(round(processing_time))
        return int(round(processing_time * 1000))

    @staticmethod
    def _extract_llm_data(llm_output: Any) -> Dict[str, Any]:
        if isinstance(llm_output, dict):
            return llm_output
        if isinstance(llm_output, str):
            try:
                import json
                return json.loads(llm_output)
            except Exception:
                return {}
        return {}

    @classmethod
    def list_voice_records(
        cls,
        db: Session,
        page: int = 1,
        limit: int = 20,
        search: Optional[str] = None,
        user_id: Optional[int] = None,
        intent: Optional[str] = None,
        status_filter: Optional[str] = None,
        confidence_min: Optional[float] = None,
        confidence_max: Optional[float] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> AdminVoiceListResponse:
        # Validate phân trang
        if page < 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tham số 'page' phải lớn hơn hoặc bằng 1")
        if limit < 1 or limit > 100:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tham số 'limit' phải nằm trong khoảng từ 1 đến 100")
        if from_date and to_date and from_date > to_date:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Thời gian bắt đầu 'from' không được lớn hơn thời gian kết thúc 'to'")
        if confidence_min is not None and confidence_max is not None and confidence_min > confidence_max:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="'confidence_min' không được lớn hơn 'confidence_max'")

        records, total_count = AdminVoiceRepository.get_voice_records(
            db=db,
            page=page,
            limit=limit,
            search=search,
            user_id=user_id,
            intent=intent,
            status=status_filter,
            confidence_min=confidence_min,
            confidence_max=confidence_max,
            from_date=from_date,
            to_date=to_date
        )

        items: List[AdminVoiceListItem] = []
        for record, user, transaction, intent_name in records:
            llm_data = cls._extract_llm_data(record.llm_output)

            # Intent ưu tiên từ record.intent -> intent_name (từ Intent table) -> llm_output
            resolved_intent = record.intent or intent_name or llm_data.get("intent")
            resolved_status = record.status or llm_data.get("status") or "SUCCESS"
            resolved_status = resolved_status.upper() if isinstance(resolved_status, str) else "SUCCESS"

            resolved_user_id = user.user_id if user else (record.user_id or (transaction.user_id if transaction else None))
            resolved_user_name = user.full_name if user else None

            confidence_val = float(record.confidence) if record.confidence is not None else None
            processing_time_ms = cls._normalize_processing_time_ms(record.processing_time)

            audio_url = (
                record.audio_path
                if (record.audio_path and record.audio_path.startswith(("http://", "https://")))
                else (f"/api/v1/admin/voice-records/{record.voice_id}/audio" if record.audio_path else None)
            )

            items.append(
                AdminVoiceListItem(
                    id=record.voice_id,
                    user_id=resolved_user_id,
                    user_name=resolved_user_name,
                    transcript=record.transcript,
                    intent=resolved_intent,
                    confidence=confidence_val,
                    status=resolved_status,
                    transaction_id=record.transaction_id or (transaction.transaction_id if transaction else None),
                    audio_url=audio_url,
                    processing_time_ms=processing_time_ms,
                    created_at=record.created_at
                )
            )

        total_pages = math.ceil(total_count / limit) if total_count > 0 else 0

        return AdminVoiceListResponse(
            items=items,
            pagination=AdminVoicePagination(
                page=page,
                limit=limit,
                total=total_count,
                total_pages=total_pages
            )
        )

    @classmethod
    def get_voice_record_detail(
        cls,
        db: Session,
        voice_id: int
    ) -> AdminVoiceDetailResponse:
        row = AdminVoiceRepository.get_voice_record_by_id(db, voice_id)
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Không tìm thấy bản ghi xử lý giọng nói với ID: {voice_id}"
            )

        record, user, transaction, intent_name = row
        llm_data = cls._extract_llm_data(record.llm_output)

        # 1. User
        user_obj = None
        resolved_user_id = user.user_id if user else (record.user_id or (transaction.user_id if transaction else None))
        resolved_user_name = user.full_name if user else None
        if resolved_user_id or resolved_user_name:
            user_obj = AdminVoiceDetailUser(
                id=resolved_user_id,
                name=resolved_user_name
            )

        # 2. Audio
        audio_obj = None
        if record.audio_path:
            # An toàn: không để lộ absolute filesystem path ra ngoài API
            audio_url = record.audio_path if record.audio_path.startswith(("http://", "https://")) else f"/api/v1/admin/voice-records/{voice_id}/audio"
            duration = llm_data.get("audio_duration") or llm_data.get("duration")
            if duration is not None:
                try:
                    duration = float(duration)
                except Exception:
                    duration = None
            audio_obj = AdminVoiceDetailAudio(
                url=audio_url,
                duration=duration
            )

        # 3. AI Result
        resolved_intent = record.intent or intent_name or llm_data.get("intent")
        confidence_val = float(record.confidence) if record.confidence is not None else None
        entities = llm_data.get("entities") if isinstance(llm_data.get("entities"), dict) else {}
        ai_result = AdminVoiceDetailAiResult(
            intent=resolved_intent,
            confidence=confidence_val,
            entities=entities
        )

        # 4. Validation
        resolved_status = (record.status or llm_data.get("status") or "SUCCESS").upper()
        validation_status = "VALID"
        validation_errors = []
        if resolved_status in ("FAILED", "ERROR"):
            validation_status = "INVALID"
            if record.error_message:
                validation_errors.append(record.error_message)
            elif llm_data.get("message"):
                validation_errors.append(str(llm_data.get("message")))
        elif llm_data.get("missing_fields"):
            validation_status = "PENDING"
            validation_errors.append(f"Thiếu trường thông tin: {', '.join(llm_data.get('missing_fields'))}")

        validation_obj = AdminVoiceDetailValidation(
            status=validation_status,
            errors=validation_errors
        )

        # 5. Transaction
        tx_obj = None
        if transaction:
            tx_obj = AdminVoiceDetailTransaction(
                id=transaction.transaction_id,
                status=transaction.payment_status or "CREATED"
            )
        elif record.transaction_id:
            tx_obj = AdminVoiceDetailTransaction(
                id=record.transaction_id,
                status="CREATED"
            )

        # 6. Processing
        processing_time_ms = cls._normalize_processing_time_ms(record.processing_time)
        processing_obj = AdminVoiceDetailProcessing(
            status=resolved_status,
            processing_time_ms=processing_time_ms,
            error_message=record.error_message
        )

        # 7. Correction
        from app.services.admin_voice_ai_service import AdminVoiceAiService
        correction_obj = AdminVoiceAiService._detect_user_correction(llm_data, transaction, db)

        return AdminVoiceDetailResponse(
            id=record.voice_id,
            user=user_obj,
            audio=audio_obj,
            transcript=record.transcript,
            ai_result=ai_result,
            validation=validation_obj,
            correction=correction_obj,
            transaction=tx_obj,
            processing=processing_obj,
            created_at=record.created_at,
            updated_at=record.updated_at
        )

    @classmethod
    def get_voice_ai_result(cls, db: Session, voice_id: int) -> AdminVoiceAiResultResponse:
        from app.services.admin_voice_ai_service import AdminVoiceAiService
        return AdminVoiceAiService.get_ai_result(db=db, voice_id=voice_id)

    @classmethod
    def get_audio_file_path(
        cls,
        db: Session,
        voice_id: int
    ) -> tuple[str, str, str]:
        """
        Lấy thông tin file âm thanh để stream bảo mật.
        Trả về: (file_path, media_type, filename)
        """
        row = AdminVoiceRepository.get_voice_record_by_id(db, voice_id)
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Không tìm thấy bản ghi xử lý giọng nói với ID: {voice_id}"
            )

        record, _, _, _ = row
        if not record.audio_path:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không có file ghi âm cho bản ghi này"
            )

        file_path = record.audio_path
        if file_path.startswith(("http://", "https://")):
            filename = os.path.basename(file_path.split("?")[0]) or f"voice_{voice_id}.m4a"
            return file_path, "url", filename

        if not os.path.isabs(file_path):
            file_path = os.path.abspath(file_path)

        if not os.path.isfile(file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File ghi âm không tồn tại trên hệ thống lưu trữ"
            )

        filename = os.path.basename(file_path)
        media_type, _ = mimetypes.guess_type(file_path)
        if not media_type:
            media_type = "audio/mpeg"

        return file_path, media_type, filename
