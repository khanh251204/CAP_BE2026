import math
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_

from app.models.voice_record_model import VoiceRecord
from app.models.user_model import User
from app.models.transaction_model import Transaction
from app.models.intent_model import Intent
from app.repositories.admin_voice_repository import AdminVoiceRepository
from app.services.data_lake_service import DataLakeService
from app.services.admin_voice_ai_service import AdminVoiceAiService
from app.schemas.admin_dataset_schema import (
    AdminDatasetListResponse,
    AdminDatasetItem,
    AdminDatasetPagination,
    AdminDatasetDetailResponse,
    AdminDatasetStorageMeta,
    AdminDatasetSummaryResponse,
    AdminDatasetIngestResponse,
)


class AdminDatasetService:

    @classmethod
    def list_dataset(
        cls,
        db: Session,
        page: int = 1,
        limit: int = 20,
        search: Optional[str] = None,
        data_type: Optional[str] = None,
        source_type: Optional[str] = None,
        intent: Optional[str] = None,
        status_filter: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> AdminDatasetListResponse:
        if page < 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="page phải >= 1")
        if limit < 1 or limit > 100:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="limit phải từ 1 đến 100")
        if from_date and to_date and from_date > to_date:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="from không được lớn hơn to")

        records, total_count = AdminVoiceRepository.get_voice_records(
            db=db,
            page=page,
            limit=limit,
            search=search,
            intent=intent,
            status=status_filter,
            from_date=from_date,
            to_date=to_date,
        )

        items: List[AdminDatasetItem] = []
        for record, user, transaction, intent_name in records:
            llm_data = AdminVoiceAiService._extract_llm_data(record.llm_output)
            correction = AdminVoiceAiService._detect_user_correction(llm_data, transaction, db, voice_id=record.voice_id)

            # Phân loại dữ liệu Data Lake
            if correction:
                classified_type = "FEEDBACK"
            elif record.transcript and (record.intent or intent_name or llm_data.get("intent")):
                classified_type = "DATASET"
            elif record.transcript or record.llm_output:
                classified_type = "PROCESSED"
            else:
                classified_type = "RAW"

            if data_type and data_type.upper() != classified_type:
                continue

            storage_meta = DataLakeService.get_storage_meta(record.voice_id, record.created_at)

            items.append(
                AdminDatasetItem(
                    id=record.voice_id,
                    voice_record_id=record.voice_id,
                    data_type=classified_type,
                    source_type="VOICE_PIPELINE",
                    transcript=record.transcript,
                    intent=record.intent or intent_name or llm_data.get("intent"),
                    confidence=float(record.confidence) if record.confidence is not None else None,
                    status=record.status or "SUCCESS",
                    has_correction=bool(correction),
                    storage_path=storage_meta.get("dataset_path"),
                    created_at=record.created_at,
                )
            )

        total_pages = math.ceil(total_count / limit) if total_count > 0 else 0

        return AdminDatasetListResponse(
            items=items,
            pagination=AdminDatasetPagination(
                page=page,
                limit=limit,
                total=total_count,
                total_pages=total_pages,
            ),
        )

    @classmethod
    def get_dataset_detail(cls, db: Session, voice_id: int) -> AdminDatasetDetailResponse:
        row = AdminVoiceRepository.get_voice_record_by_id(db, voice_id)
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Không tìm thấy bản ghi dataset với ID: {voice_id}",
            )

        record, user, transaction, intent_name = row
        llm_data = AdminVoiceAiService._extract_llm_data(record.llm_output)
        ai_result = AdminVoiceAiService.get_ai_result(db, voice_id)
        storage_meta = DataLakeService.get_storage_meta(record.voice_id, record.created_at)

        # Quyết định data_type
        if ai_result.correction:
            data_type = "FEEDBACK"
        elif record.transcript and ai_result.intent:
            data_type = "DATASET"
        elif record.transcript or record.llm_output:
            data_type = "PROCESSED"
        else:
            data_type = "RAW"

        audio_url = None
        if record.audio_path:
            audio_url = record.audio_path if record.audio_path.startswith(("http://", "https://")) else f"/api/v1/admin/voice-processing/{voice_id}/audio"

        tx_dict = None
        if ai_result.transaction:
            tx_dict = ai_result.transaction.model_dump()

        return AdminDatasetDetailResponse(
            id=record.voice_id,
            voice_record_id=record.voice_id,
            data_type=data_type,
            source_type="VOICE_PIPELINE",
            user_id=user.user_id if user else record.user_id,
            user_name=user.full_name if user else None,
            audio_url=audio_url,
            transcript=record.transcript,
            intent=ai_result.intent.name if ai_result.intent else None,
            entities=ai_result.entities,
            confidence=ai_result.confidence.model_dump(),
            validation=ai_result.validation.model_dump(),
            correction=ai_result.correction,
            transaction=tx_dict,
            processing=ai_result.processing.model_dump(),
            storage=AdminDatasetStorageMeta(**storage_meta),
            created_at=record.created_at,
        )

    @classmethod
    def get_summary(cls, db: Session) -> AdminDatasetSummaryResponse:
        total = db.query(func.count(VoiceRecord.voice_id)).scalar() or 0

        raw_count = db.query(func.count(VoiceRecord.voice_id)).filter(
            VoiceRecord.audio_path.isnot(None)
        ).scalar() or 0

        proc_count = db.query(func.count(VoiceRecord.voice_id)).filter(
            or_(VoiceRecord.transcript.isnot(None), VoiceRecord.llm_output.isnot(None))
        ).scalar() or 0

        dataset_count = db.query(func.count(VoiceRecord.voice_id)).filter(
            and_(VoiceRecord.transcript.isnot(None), VoiceRecord.status == "SUCCESS")
        ).scalar() or 0

        # Intent distribution
        intent_rows = db.query(VoiceRecord.intent, func.count(VoiceRecord.voice_id))\
            .filter(VoiceRecord.intent.isnot(None))\
            .group_by(VoiceRecord.intent)\
            .all()
        intents_map = {row[0]: row[1] for row in intent_rows if row[0]}

        # Status distribution
        status_rows = db.query(VoiceRecord.status, func.count(VoiceRecord.voice_id))\
            .group_by(VoiceRecord.status)\
            .all()
        status_map = {row[0]: row[1] for row in status_rows if row[0]}

        # Correction count: bản ghi từ bảng User_Correction hoặc fallback
        from app.models.user_correction_model import UserCorrection
        corr_count = db.query(func.count(func.distinct(UserCorrection.voice_record_id))).scalar()
        if not corr_count:
            corr_count = db.query(func.count(VoiceRecord.voice_id)).filter(
                VoiceRecord.transaction_id.isnot(None)
            ).scalar() or 0

        return AdminDatasetSummaryResponse(
            total_records=total,
            raw_count=raw_count,
            processed_count=proc_count,
            correction_count=corr_count,
            dataset_count=dataset_count,
            intents_breakdown=intents_map,
            status_breakdown=status_map,
        )

    @classmethod
    def ingest_voice_record(cls, db: Session, voice_id: int) -> AdminDatasetIngestResponse:
        row = AdminVoiceRepository.get_voice_record_by_id(db, voice_id)
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Không tìm thấy bản ghi voice processing với ID: {voice_id}",
            )
        record, user, transaction, _ = row
        ingest_res = DataLakeService.ingest_record(record, user, transaction, db)

        if not ingest_res.get("success"):
            return AdminDatasetIngestResponse(
                success=False,
                voice_record_id=voice_id,
                storage_paths={},
                message=f"Ingestion thất bại: {ingest_res.get('error')}",
            )

        return AdminDatasetIngestResponse(
            success=True,
            voice_record_id=voice_id,
            storage_paths=ingest_res.get("storage_paths", {}),
            message="Ingestion vào Data Lake thành công",
        )

    @classmethod
    def export_dataset(
        cls,
        db: Session,
        intent: Optional[str] = None,
        status_filter: Optional[str] = None,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:
        query = db.query(VoiceRecord).filter(
            VoiceRecord.transcript.isnot(None),
            VoiceRecord.status == (status_filter or "SUCCESS"),
        )
        if intent:
            query = query.filter(VoiceRecord.intent == intent)

        records = query.order_by(VoiceRecord.created_at.desc()).limit(limit).all()

        dataset: List[Dict[str, Any]] = []
        for r in records:
            llm_data = AdminVoiceAiService._extract_llm_data(r.llm_output)
            dataset.append({
                "dataset_id": f"DS-{r.voice_id}",
                "voice_record_id": r.voice_id,
                "transcript": r.transcript,
                "intent": r.intent or llm_data.get("intent"),
                "entities": llm_data.get("entities") or {},
                "confidence": float(r.confidence) if r.confidence is not None else None,
                "audio_source": r.audio_path,
                "status": r.status,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            })
        return dataset
