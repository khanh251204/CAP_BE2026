import json
from typing import Optional, Dict, Any, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.voice_record_model import VoiceRecord
from app.models.transaction_model import Transaction
from app.models.transactionDetail_model import TransactionDetail
from app.models.user_model import User
from app.repositories.admin_voice_repository import AdminVoiceRepository
from app.schemas.admin_voice_schema import (
    AdminVoiceAiResultResponse,
    AdminVoiceAiResultTranscript,
    AdminVoiceAiResultIntent,
    AdminVoiceAiResultConfidence,
    AdminVoiceAiResultValidation,
    AdminVoiceAiResultTransaction,
    AdminVoiceAiResultProcessing,
)


class AdminVoiceAiService:

    @staticmethod
    def _extract_llm_data(llm_output: Any) -> Dict[str, Any]:
        if isinstance(llm_output, dict):
            return llm_output
        if isinstance(llm_output, str):
            try:
                return json.loads(llm_output)
            except Exception:
                return {}
        return {}

    @staticmethod
    def _normalize_processing_time_ms(processing_time: Optional[float]) -> Optional[int]:
        if processing_time is None:
            return None
        if processing_time > 100.0:
            return int(round(processing_time))
        return int(round(processing_time * 1000))

    @classmethod
    def _detect_user_correction(
        cls,
        llm_data: Dict[str, Any],
        transaction: Optional[Transaction],
        db: Session,
        voice_id: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        # 0. Kiểm tra trực tiếp bảng User_Correction trong MySQL
        try:
            from app.models.user_correction_model import UserCorrection
            query = db.query(UserCorrection)
            corr_rec = None
            if voice_id:
                corr_rec = query.filter(UserCorrection.voice_record_id == voice_id).order_by(UserCorrection.id.desc()).first()
            if not corr_rec and transaction:
                corr_rec = query.filter(UserCorrection.transaction_id == transaction.transaction_id).order_by(UserCorrection.id.desc()).first()
            if corr_rec and corr_rec.diff:
                return corr_rec.diff
        except Exception:
            pass

        # 1. Nếu llm_data đã lưu rõ user correction từ Human-in-the-Loop
        if "correction" in llm_data and isinstance(llm_data["correction"], dict):
            return llm_data["correction"]
        if "user_correction" in llm_data and isinstance(llm_data["user_correction"], dict):
            return llm_data["user_correction"]

        if not transaction:
            return None

        # 2. So khớp entities trích xuất từ AI với dữ liệu Transaction / TransactionDetail đã commit
        entities = llm_data.get("entities")
        if not isinstance(entities, dict) or not entities:
            return None

        # Lấy TransactionDetail đầu tiên của transaction nếu có
        detail = db.query(TransactionDetail).filter(
            TransactionDetail.transaction_id == transaction.transaction_id
        ).first()

        diff_ai: Dict[str, Any] = {}
        diff_corr: Dict[str, Any] = {}

        if detail and detail.product:
            tx_product = detail.product.product_name
            ai_product = str(entities.get("product") or "").strip()
            if ai_product and tx_product and ai_product.lower() != tx_product.lower():
                diff_ai["product"] = ai_product
                diff_corr["product"] = tx_product

            tx_qty = float(detail.quantity) if detail.quantity is not None else None
            ai_qty = float(entities.get("quantity")) if entities.get("quantity") is not None else None
            if ai_qty is not None and tx_qty is not None and abs(ai_qty - tx_qty) > 1e-4:
                diff_ai["quantity"] = ai_qty
                diff_corr["quantity"] = tx_qty

            tx_price = float(detail.unit_price) if detail.unit_price is not None else None
            ai_price = float(entities.get("price")) if entities.get("price") is not None else None
            if ai_price is not None and tx_price is not None and abs(ai_price - tx_price) > 1e-4:
                diff_ai["price"] = ai_price
                diff_corr["price"] = tx_price

        if diff_ai:
            return {
                "ai": diff_ai,
                "correction": diff_corr
            }

        return None

    @classmethod
    def get_ai_result(cls, db: Session, voice_id: int) -> AdminVoiceAiResultResponse:
        row = AdminVoiceRepository.get_voice_record_by_id(db, voice_id)
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Không tìm thấy bản ghi xử lý giọng nói với ID: {voice_id}"
            )

        record, user, transaction, intent_name = row
        llm_data = cls._extract_llm_data(record.llm_output)

        # Kiểm tra sự tồn tại của kết quả AI
        has_ai_data = bool(
            record.transcript
            or record.intent
            or intent_name
            or (llm_data and (llm_data.get("intent") or llm_data.get("entities") or llm_data.get("text")))
        )
        if not has_ai_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy kết quả AI cho bản ghi giọng nói này"
            )

        # 1. Transcript
        transcript_obj = AdminVoiceAiResultTranscript(text=record.transcript) if record.transcript else None

        # 2. Intent
        resolved_intent = record.intent or intent_name or llm_data.get("intent")
        intent_obj = AdminVoiceAiResultIntent(name=resolved_intent) if resolved_intent else None

        # 3. Entities (trích xuất động, giữ nguyên schema gốc từ AI)
        raw_entities = llm_data.get("entities")
        if isinstance(raw_entities, dict):
            entities_dict = raw_entities
        else:
            # Fallback nếu flat dictionary
            entities_dict = {
                k: v for k, v in llm_data.items()
                if k in ("product", "quantity", "unit", "price", "customer", "supplier", "date", "payment")
                and v is not None
            }

        # 4. Confidence (Chỉ trả confidence thực tế có nguồn, tuyệt đối không tạo số giả)
        intent_conf: Optional[float] = None
        entity_conf: Optional[float] = None
        overall_conf: Optional[float] = None

        raw_conf = llm_data.get("confidence")
        if isinstance(raw_conf, dict):
            intent_conf = float(raw_conf["intent"]) if raw_conf.get("intent") is not None else None
            entity_conf = float(raw_conf["entity"]) if raw_conf.get("entity") is not None else None
            overall_conf = float(raw_conf["overall"]) if raw_conf.get("overall") is not None else None
        elif isinstance(raw_conf, (int, float)):
            overall_conf = float(raw_conf)

        if intent_conf is None and llm_data.get("intent_confidence") is not None:
            intent_conf = float(llm_data["intent_confidence"])
        if entity_conf is None and llm_data.get("entity_confidence") is not None:
            entity_conf = float(llm_data["entity_confidence"])
        if overall_conf is None and llm_data.get("overall_confidence") is not None:
            overall_conf = float(llm_data["overall_confidence"])

        stt_conf = float(record.confidence) if record.confidence is not None else None

        confidence_obj = AdminVoiceAiResultConfidence(
            intent=intent_conf,
            entity=entity_conf,
            overall=overall_conf,
            stt=stt_conf
        )

        # 5. Validation Result
        resolved_status = (record.status or llm_data.get("status") or "SUCCESS").lower()
        val_status = "valid"
        val_errors = []
        val_warnings = []

        if resolved_status in ("failed", "error"):
            val_status = "invalid"
            if record.error_message:
                val_errors.append(record.error_message)
            elif llm_data.get("message"):
                val_errors.append(str(llm_data["message"]))
            if isinstance(llm_data.get("errors"), list):
                for err in llm_data["errors"]:
                    if str(err) not in val_errors:
                        val_errors.append(str(err))

        if llm_data.get("missing_fields"):
            if val_status == "valid":
                val_status = "pending"
            val_warnings.append(f"Thiếu trường thông tin: {', '.join(llm_data['missing_fields'])}")

        validation_obj = AdminVoiceAiResultValidation(
            status=val_status,
            errors=val_errors,
            warnings=val_warnings
        )

        # 6. User Correction
        correction_obj = cls._detect_user_correction(llm_data, transaction, db, voice_id=record.voice_id)

        # 7. Transaction
        tx_obj = None
        if transaction:
            tx_obj = AdminVoiceAiResultTransaction(
                id=transaction.transaction_id,
                status=transaction.payment_status,
                total_amount=float(transaction.total_amount) if transaction.total_amount is not None else None,
                transaction_date=transaction.transaction_date
            )
        elif record.transaction_id:
            tx_obj = AdminVoiceAiResultTransaction(
                id=record.transaction_id,
                status="CREATED"
            )

        # 8. Processing Metadata
        proc_status = (record.status or llm_data.get("status") or "SUCCESS").lower()
        proc_time_ms = cls._normalize_processing_time_ms(record.processing_time)
        ai_meta = llm_data.get("_ai_metadata") if isinstance(llm_data.get("_ai_metadata"), dict) else {}
        provider = llm_data.get("provider") or ai_meta.get("llm", {}).get("provider") or ("Groq" if record.processing_time is not None else None)
        model = llm_data.get("model") or ai_meta.get("llm", {}).get("model") or ("whisper-large-v3-turbo" if record.audio_path else None)
        model_ver = llm_data.get("model_version") or ai_meta.get("llm", {}).get("version")
        prompt_ver = llm_data.get("prompt_version") or ai_meta.get("prompt_version")
        pipe_ver = llm_data.get("pipeline_version") or ai_meta.get("pipeline_version")

        processing_obj = AdminVoiceAiResultProcessing(
            status=proc_status,
            processing_time_ms=proc_time_ms,
            provider=provider,
            model=model,
            model_version=model_ver,
            prompt_version=prompt_ver,
            pipeline_version=pipe_ver,
            error_message=record.error_message
        )

        return AdminVoiceAiResultResponse(
            voice_record_id=record.voice_id,
            transcript=transcript_obj,
            intent=intent_obj,
            entities=entities_dict,
            confidence=confidence_obj,
            validation=validation_obj,
            correction=correction_obj,
            transaction=tx_obj,
            processing=processing_obj
        )
