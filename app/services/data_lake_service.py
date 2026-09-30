import os
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session
from app.models.voice_record_model import VoiceRecord
from app.models.user_model import User
from app.models.transaction_model import Transaction

logger = logging.getLogger(__name__)


class DataLakeService:
    """
    Data Lake Foundation / Prototype Service cho Capstone 1.
    Quản lý lưu trữ tệp và dữ liệu nghiên cứu AI độc lập với MySQL:
      - raw/voice/: Tham chiếu tệp ghi âm gốc và metadata thô
      - processed/ai_result/: Snapshot kết quả phân tích AI (Transcript, Intent, Entities)
      - feedback/correction/: Dữ liệu hiệu chỉnh từ người dùng (Human-in-the-loop)
      - dataset/: Bộ dữ liệu tổng hợp phục vụ AI Evaluation & Research
    """

    BASE_DIR = os.getenv("DATA_LAKE_PATH", "data_lake")

    @classmethod
    def get_base_dir(cls) -> str:
        base = cls.BASE_DIR
        if not os.path.isabs(base):
            base = os.path.abspath(base)
        return base

    @classmethod
    def init_storage(cls) -> None:
        """Đảm bảo các thư mục vùng (zones) trong Data Lake được khởi tạo."""
        base = cls.get_base_dir()
        zones = [
            os.path.join(base, "raw", "voice"),
            os.path.join(base, "processed", "ai_result"),
            os.path.join(base, "feedback", "correction"),
            os.path.join(base, "dataset"),
        ]
        for z in zones:
            os.makedirs(z, exist_ok=True)

    @classmethod
    def _extract_llm_dict(cls, llm_output: Any) -> Dict[str, Any]:
        if isinstance(llm_output, dict):
            return llm_output
        if isinstance(llm_output, str):
            try:
                return json.loads(llm_output)
            except Exception:
                return {}
        return {}

    @classmethod
    def ingest_record(
        cls,
        record: VoiceRecord,
        user: Optional[User] = None,
        transaction: Optional[Transaction] = None,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        Ingest một VoiceRecord vào Data Lake.
        Hoàn toàn độc lập (decoupled), không làm ảnh hưởng hay rollback giao dịch MySQL.
        """
        if not record or not record.voice_id:
            return {
                "success": False,
                "error": "Bản ghi VoiceRecord không hợp lệ: thiếu voice_id",
                "storage_paths": {}
            }

        try:
            from app.middlewares.system_log_middleware import get_current_request_id
            resolved_req_id = get_current_request_id()

            cls.init_storage()
            base = cls.get_base_dir()

            c_date = record.created_at or datetime.now()
            day_folder = c_date.strftime("%Y-%m-%d")
            voice_id = record.voice_id

            llm_data = cls._extract_llm_dict(record.llm_output)
            ai_meta = llm_data.get("_ai_metadata") if isinstance(llm_data.get("_ai_metadata"), dict) else {}
            provider = llm_data.get("provider") or ai_meta.get("llm", {}).get("provider") or ("Groq" if record.processing_time is not None else None)
            model = llm_data.get("model") or ai_meta.get("llm", {}).get("model") or ("whisper-large-v3-turbo" if record.audio_path else None)
            prompt_ver = llm_data.get("prompt_version") or ai_meta.get("prompt_version")
            pipe_ver = llm_data.get("pipeline_version") or ai_meta.get("pipeline_version")

            storage_paths: Dict[str, str] = {}

            # 1. ZONE RAW: Lưu vết tham chiếu âm thanh và thông tin gốc
            raw_dir = os.path.join(base, "raw", "voice", day_folder)
            os.makedirs(raw_dir, exist_ok=True)
            raw_file = os.path.join(raw_dir, f"{voice_id}.json")

            raw_payload = {
                "voice_record_id": voice_id,
                "user_id": record.user_id or (user.user_id if user else None),
                "audio_path": record.audio_path,
                "request_id": resolved_req_id,
                "created_at": c_date.isoformat(),
                "data_classification": "RAW_SOURCE"
            }
            with open(raw_file, "w", encoding="utf-8") as f:
                json.dump(raw_payload, f, ensure_ascii=False, indent=2)
            storage_paths["raw"] = os.path.relpath(raw_file, base).replace("\\", "/")

            # 2. ZONE PROCESSED: Lưu snapshot kết quả xử lý AI
            proc_dir = os.path.join(base, "processed", "ai_result", day_folder)
            os.makedirs(proc_dir, exist_ok=True)
            proc_file = os.path.join(proc_dir, f"{voice_id}.json")

            proc_payload = {
                "voice_record_id": voice_id,
                "transcript": record.transcript,
                "intent": record.intent or llm_data.get("intent"),
                "entities": llm_data.get("entities") or {},
                "confidence": float(record.confidence) if record.confidence is not None else None,
                "processing_time": record.processing_time,
                "provider": provider,
                "model": model,
                "prompt_version": prompt_ver,
                "pipeline_version": pipe_ver,
                "status": record.status,
                "error_message": record.error_message,
                "request_id": resolved_req_id,
                "created_at": c_date.isoformat(),
                "data_classification": "PROCESSED_AI"
            }
            with open(proc_file, "w", encoding="utf-8") as f:
                json.dump(proc_payload, f, ensure_ascii=False, indent=2)
            storage_paths["processed"] = os.path.relpath(proc_file, base).replace("\\", "/")

            # 3. ZONE FEEDBACK: Lưu hiệu chỉnh của người dùng (nếu có)
            from app.services.admin_voice_ai_service import AdminVoiceAiService
            correction = None
            if db:
                correction = AdminVoiceAiService._detect_user_correction(llm_data, transaction, db, voice_id=voice_id)

            if correction:
                fb_dir = os.path.join(base, "feedback", "correction", day_folder)
                os.makedirs(fb_dir, exist_ok=True)
                fb_file = os.path.join(fb_dir, f"{voice_id}.json")
                fb_payload = {
                    "voice_record_id": voice_id,
                    "transaction_id": record.transaction_id,
                    "correction": correction,
                    "request_id": resolved_req_id,
                    "created_at": c_date.isoformat(),
                    "data_classification": "USER_FEEDBACK"
                }
                with open(fb_file, "w", encoding="utf-8") as f:
                    json.dump(fb_payload, f, ensure_ascii=False, indent=2)
                storage_paths["feedback"] = os.path.relpath(fb_file, base).replace("\\", "/")

            # 4. ZONE DATASET: Mẫu dữ liệu hoàn chỉnh phục vụ nghiên cứu & AI evaluation
            ds_dir = os.path.join(base, "dataset", day_folder)
            os.makedirs(ds_dir, exist_ok=True)
            ds_file = os.path.join(ds_dir, f"{voice_id}.json")

            dataset_payload = {
                "dataset_id": f"DS-{voice_id}",
                "voice_record_id": voice_id,
                "audio_source": record.audio_path,
                "transcript": record.transcript,
                "intent": record.intent or llm_data.get("intent"),
                "entities": llm_data.get("entities") or {},
                "confidence": float(record.confidence) if record.confidence is not None else None,
                "provider": provider,
                "model": model,
                "prompt_version": prompt_ver,
                "pipeline_version": pipe_ver,
                "user_correction": correction,
                "status": record.status,
                "request_id": resolved_req_id,
                "created_at": c_date.isoformat(),
                "ingested_at": datetime.now().isoformat(),
                "data_classification": "RESEARCH_DATASET"
            }
            with open(ds_file, "w", encoding="utf-8") as f:
                json.dump(dataset_payload, f, ensure_ascii=False, indent=2)
            storage_paths["dataset"] = os.path.relpath(ds_file, base).replace("\\", "/")

            logger.info(f"Data Lake ingested voice_record_id={voice_id} successfully")
            return {
                "success": True,
                "voice_record_id": voice_id,
                "storage_paths": storage_paths
            }

        except Exception as e:
            logger.error(f"Lỗi khi ingest vào Data Lake cho record {record.voice_id}: {e}", exc_info=True)
            return {
                "success": False,
                "voice_record_id": record.voice_id,
                "error": str(e),
                "storage_paths": {}
            }

    @classmethod
    def get_storage_meta(cls, voice_id: int, created_at: Optional[datetime]) -> Dict[str, Any]:
        """Tính toán metadata đường dẫn trong Data Lake cho bản ghi."""
        base = cls.get_base_dir()
        c_date = created_at or datetime.now()
        day_folder = c_date.strftime("%Y-%m-%d")
        month_folder = c_date.strftime("%Y-%m")

        def resolve_path(zone_sub: str, fid: Any):
            day_rel = f"{zone_sub}/{day_folder}/{fid}.json"
            day_abs = os.path.join(base, zone_sub, day_folder, f"{fid}.json")
            if os.path.exists(day_abs):
                return day_rel, day_abs
            month_rel = f"{zone_sub}/{month_folder}/{fid}.json"
            month_abs = os.path.join(base, zone_sub, month_folder, f"{fid}.json")
            if os.path.exists(month_abs):
                return month_rel, month_abs
            return day_rel, day_abs

        raw_rel, raw_abs = resolve_path(os.path.join("raw", "voice"), voice_id)
        proc_rel, proc_abs = resolve_path(os.path.join("processed", "ai_result"), voice_id)
        fb_rel, fb_abs = resolve_path(os.path.join("feedback", "correction"), voice_id)
        ds_rel, ds_abs = resolve_path("dataset", voice_id)

        return {
            "storage_type": "LOCAL_FS",
            "raw_path": raw_rel.replace("\\", "/") if os.path.exists(raw_abs) else None,
            "processed_path": proc_rel.replace("\\", "/"),
            "feedback_path": fb_rel.replace("\\", "/") if os.path.exists(fb_abs) else None,
            "dataset_path": ds_rel.replace("\\", "/"),
            "ingested_at": c_date
        }

    @classmethod
    def save_correction_feedback(
        cls,
        voice_record_id: Optional[int],
        ai_result: Dict[str, Any],
        final_transaction: Dict[str, Any],
        diff: Dict[str, Any],
        correction_type: str = "MANUAL_EDIT",
        transaction_id: Optional[int] = None,
        user_id: Optional[int] = None,
        created_at: Optional[datetime] = None
    ) -> Optional[str]:
        """
        Ghi nhận bản hiệu chỉnh của người dùng vào Zone Feedback/Correction trong Data Lake.
        Bảo toàn bản AI hiểu ban đầu (ai_result) và bản người dùng đã sửa (final_transaction),
        kèm phần khác biệt (diff) và kiểu sửa đổi (correction_type).
        """
        try:
            cls.init_storage()
            base = cls.get_base_dir()
            c_date = created_at or datetime.now()
            day_folder = c_date.strftime("%Y-%m-%d")

            fb_dir = os.path.join(base, "feedback", "correction", day_folder)
            os.makedirs(fb_dir, exist_ok=True)

            identifier = voice_record_id or (f"tx_{transaction_id}" if transaction_id else f"corr_{int(c_date.timestamp())}")
            fb_file = os.path.join(fb_dir, f"{identifier}.json")

            from app.middlewares.system_log_middleware import get_current_request_id
            resolved_req_id = get_current_request_id()

            correction_payload = {
                "voice_record_id": voice_record_id,
                "transaction_id": transaction_id,
                "user_id": user_id,
                "ai_result": ai_result,
                "final_transaction": final_transaction,
                "correction": {
                    "ai": diff.get("ai", {}),
                    "correction": diff.get("correction", {})
                },
                "diff": diff,
                "correction_type": correction_type,
                "request_id": resolved_req_id,
                "created_at": c_date.isoformat(),
                "data_classification": "USER_FEEDBACK"
            }

            with open(fb_file, "w", encoding="utf-8") as f:
                json.dump(correction_payload, f, ensure_ascii=False, indent=2)

            rel_path = os.path.relpath(fb_file, base).replace("\\", "/")
            logger.info(f"Saved correction feedback to Data Lake: {rel_path}")
            return rel_path
        except Exception as e:
            logger.warning(f"Không thể ghi nhận correction feedback vào Data Lake: {e}")
            return None
