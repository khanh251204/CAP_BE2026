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
        try:
            cls.init_storage()
            base = cls.get_base_dir()

            c_date = record.created_at or datetime.now()
            month_folder = c_date.strftime("%Y-%m")
            voice_id = record.voice_id

            llm_data = cls._extract_llm_dict(record.llm_output)
            storage_paths: Dict[str, str] = {}

            # 1. ZONE RAW: Lưu vết tham chiếu âm thanh và thông tin gốc
            raw_dir = os.path.join(base, "raw", "voice", month_folder)
            os.makedirs(raw_dir, exist_ok=True)
            raw_file = os.path.join(raw_dir, f"{voice_id}.json")

            raw_payload = {
                "voice_record_id": voice_id,
                "user_id": record.user_id or (user.user_id if user else None),
                "audio_path": record.audio_path,
                "created_at": c_date.isoformat(),
                "data_classification": "RAW_SOURCE"
            }
            with open(raw_file, "w", encoding="utf-8") as f:
                json.dump(raw_payload, f, ensure_ascii=False, indent=2)
            storage_paths["raw"] = os.path.relpath(raw_file, base).replace("\\", "/")

            # 2. ZONE PROCESSED: Lưu snapshot kết quả xử lý AI
            proc_dir = os.path.join(base, "processed", "ai_result", month_folder)
            os.makedirs(proc_dir, exist_ok=True)
            proc_file = os.path.join(proc_dir, f"{voice_id}.json")

            proc_payload = {
                "voice_record_id": voice_id,
                "transcript": record.transcript,
                "intent": record.intent or llm_data.get("intent"),
                "entities": llm_data.get("entities") or {},
                "confidence": float(record.confidence) if record.confidence is not None else None,
                "processing_time": record.processing_time,
                "status": record.status,
                "error_message": record.error_message,
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
                correction = AdminVoiceAiService._detect_user_correction(llm_data, transaction, db)

            if correction:
                fb_dir = os.path.join(base, "feedback", "correction", month_folder)
                os.makedirs(fb_dir, exist_ok=True)
                fb_file = os.path.join(fb_dir, f"{voice_id}.json")
                fb_payload = {
                    "voice_record_id": voice_id,
                    "transaction_id": record.transaction_id,
                    "correction": correction,
                    "created_at": c_date.isoformat(),
                    "data_classification": "USER_FEEDBACK"
                }
                with open(fb_file, "w", encoding="utf-8") as f:
                    json.dump(fb_payload, f, ensure_ascii=False, indent=2)
                storage_paths["feedback"] = os.path.relpath(fb_file, base).replace("\\", "/")

            # 4. ZONE DATASET: Mẫu dữ liệu hoàn chỉnh phục vụ nghiên cứu & AI evaluation
            ds_dir = os.path.join(base, "dataset", month_folder)
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
                "user_correction": correction,
                "status": record.status,
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
        month_folder = c_date.strftime("%Y-%m")

        raw_rel = f"raw/voice/{month_folder}/{voice_id}.json"
        proc_rel = f"processed/ai_result/{month_folder}/{voice_id}.json"
        fb_rel = f"feedback/correction/{month_folder}/{voice_id}.json"
        ds_rel = f"dataset/{month_folder}/{voice_id}.json"

        raw_abs = os.path.join(base, "raw", "voice", month_folder, f"{voice_id}.json")
        fb_abs = os.path.join(base, "feedback", "correction", month_folder, f"{voice_id}.json")

        return {
            "storage_type": "LOCAL_FS",
            "raw_path": raw_rel if os.path.exists(raw_abs) else None,
            "processed_path": proc_rel,
            "feedback_path": fb_rel if os.path.exists(fb_abs) else None,
            "dataset_path": ds_rel,
            "ingested_at": c_date
        }
