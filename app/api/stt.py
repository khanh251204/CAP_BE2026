import os
import time
import logging
import asyncio
import tempfile
from typing import Literal, Optional

from fastapi import APIRouter, UploadFile, File, HTTPException, Query, status, Depends
# pyrefly: ignore [missing-import]
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.configs.database import get_db
from app.configs.jwt import get_current_user_id, require_permission

from app.services.audio import (
    AudioPipeline,
    AudioInvalidError,
    AudioTooShortError,
    NoSpeechError,
    SpeakerNotVerifiedError,
    ALLOWED_EXTENSIONS
)
from app.services.groq_service import groq_service
from app.services.gemini_service import gemini_service
from app.services.system_log_service import log_event

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Speech to Text"])

MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB
pipeline = AudioPipeline()


async def _run_stt_pipeline(
    file: UploadFile,
    transcribe_func,
    service_name: str,
    user_id: Optional[int] = None,
    db: Optional[Session] = None
):
    """
    Quy trình tiền xử lý và chuyển giọng nói thành văn bản dùng chung:
    UploadFile -> Temp File -> Audio Preprocessing Pipeline (FFmpeg Decode -> Denoise -> VAD -> Speaker Verification) -> Transcribe -> Cleanup
    """
    start_time = time.time()
    filename = file.filename or "audio.m4a"
    ext = os.path.splitext(filename)[1].lower()

    if not ext:
        ext = ".m4a"

    if ext not in ALLOWED_EXTENSIONS:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "code": "AUDIO_INVALID",
                "message": f"Định dạng file {ext} không được hỗ trợ. Cho phép: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            }
        )

    # 1. Đọc nội dung file và kiểm tra kích thước
    content = await file.read()
    file_size = len(content)

    if file_size == 0:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "code": "AUDIO_INVALID",
                "message": "File âm thanh tải lên rỗng."
            }
        )

    if file_size > MAX_FILE_SIZE_BYTES:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "code": "AUDIO_INVALID",
                "message": f"Dung lượng file vượt quá giới hạn tối đa ({MAX_FILE_SIZE_BYTES // (1024*1024)}MB)."
            }
        )

    logger.info(f"{service_name} STT audio received: filename='{filename}', size={file_size} bytes")

    # 2. Lưu file gốc tạm thời
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as temp_file:
        temp_file.write(content)
        original_temp_path = temp_file.name

    processed_wav_path: Optional[str] = None

    try:
        # 3. Chạy qua Audio Preprocessing Pipeline (Decode -> Denoise -> VAD -> Speaker Verification)
        preprocess_start = time.time()
        processed_wav_path = await asyncio.to_thread(
            pipeline.process,
            original_temp_path
        )
        preprocess_time = time.time() - preprocess_start
        logger.info(f"Audio preprocessing completed in {preprocess_time:.3f}s")

        # 4. Gửi file WAV đã lọc sạch tới Transcription Service
        stt_start = time.time()
        transcribed_text = await asyncio.to_thread(
            transcribe_func,
            processed_wav_path
        )
        stt_latency = time.time() - stt_start
        total_time = time.time() - start_time
        logger.info(f"{service_name} transcription completed in {stt_latency:.3f}s. Total pipeline time: {total_time:.3f}s")

        # 5. Phân tích LLM trích xuất Intent và Thực thể
        llm_output: Optional[dict] = None
        extracted_intent: Optional[str] = None
        if transcribed_text:
            try:
                llm_output = await asyncio.to_thread(groq_service.analyze_transaction, transcribed_text)
                if isinstance(llm_output, dict):
                    extracted_intent = llm_output.get("intent")
            except Exception as le:
                logger.warning(f"Lỗi khi phân tích LLM cho transcript: {le}")

        # 6. Upload Cloudinary và tạo Voice_Record trong cơ sở dữ liệu (theo erd_new.md, trừ confidence)
        audio_url: Optional[str] = None
        voice_id: Optional[int] = None
        try:
            from app.services.cloudinary_service import upload_voice_audio
            c_res = await asyncio.to_thread(upload_voice_audio, content, filename)
            audio_url = c_res.get("secure_url") or c_res.get("url")
        except Exception as ce:
            logger.warning(f"Lỗi khi upload Cloudinary cho STT: {ce}")

        if db is not None:
            try:
                from app.services.voice_record_service import create_voice_record
                total_time = time.time() - start_time
                record = create_voice_record(
                    db=db,
                    user_id=user_id,
                    audio_url=audio_url,
                    transcript=transcribed_text,
                    intent=extracted_intent,
                    llm_output=llm_output,
                    confidence=None,
                    processing_time=round(total_time, 3),
                    status="PROCESSING"
                )
                voice_id = record.voice_id
            except Exception as dbe:
                logger.warning(f"Lỗi khi lưu Voice_Record: {dbe}")

        return {
            "success": True,
            "code": "STT_SUCCESS",
            "text": transcribed_text,
            "voice_id": voice_id,
            "audio_url": audio_url,
            "intent": extracted_intent,
            "llm_output": llm_output
        }

    except NoSpeechError:
        logger.info("VAD detected NO speech in audio.")
        log_event(
            level="WARNING",
            step="STT",
            message=f"{service_name}: Không phát hiện giọng nói (VAD NoSpeech)",
            detail={"service": service_name, "code": "NO_SPEECH"},
            user_id=user_id,
            status_code=200,
            api_path="/api/v1/speech/transcriptions"
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": False,
                "code": "NO_SPEECH",
                "message": "Không phát hiện giọng nói."
            }
        )

    except AudioTooShortError:
        logger.warning("Audio duration too short.")
        log_event(
            level="WARNING",
            step="STT",
            message=f"{service_name}: Đoạn ghi âm quá ngắn",
            detail={"service": service_name, "code": "AUDIO_TOO_SHORT"},
            user_id=user_id,
            status_code=400,
            api_path="/api/v1/speech/transcriptions"
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "code": "AUDIO_TOO_SHORT",
                "message": "Đoạn ghi âm quá ngắn."
            }
        )

    except AudioInvalidError as e:
        logger.warning(f"Audio invalid: {e.message}")
        log_event(
            level="WARNING",
            step="STT",
            message=f"{service_name}: Audio invalid: {e.message}",
            detail={"service": service_name, "code": "AUDIO_INVALID", "error": e.message},
            user_id=user_id,
            status_code=400,
            api_path="/api/v1/speech/transcriptions"
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "code": "AUDIO_INVALID",
                "message": e.message
            }
        )

    except SpeakerNotVerifiedError:
        logger.warning("Speaker verification failed.")
        log_event(
            level="WARNING",
            step="STT",
            message=f"{service_name}: Không xác định được giọng nói người dùng",
            detail={"service": service_name, "code": "SPEAKER_NOT_VERIFIED"},
            user_id=user_id,
            status_code=403,
            api_path="/api/v1/speech/transcriptions"
        )
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "success": False,
                "code": "SPEAKER_NOT_VERIFIED",
                "message": "Không xác định được giọng nói người dùng."
            }
        )

    except Exception as e:
        logger.error(f"Lỗi không xác định khi xử lý {service_name} STT: {e}", exc_info=True)
        log_event(
            level="ERROR",
            step="STT",
            message=f"{service_name}: Lỗi không xác định khi xử lý STT: {str(e)}",
            detail={"service": service_name, "error": str(e)},
            user_id=user_id,
            status_code=500,
            api_path="/api/v1/speech/transcriptions"
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "code": "STT_FAILED",
                "message": f"Lỗi xử lý âm thanh: {str(e)}"
            }
        )

    finally:
        # Bắt buộc dọn dẹp sạch sẽ toàn bộ file tạm: original temp file và processed WAV file
        if os.path.exists(original_temp_path):
            try:
                os.remove(original_temp_path)
            except Exception as e:
                logger.warning(f"Lỗi khi xóa file tạm gốc {original_temp_path}: {e}")

        if processed_wav_path and os.path.exists(processed_wav_path):
            try:
                os.remove(processed_wav_path)
            except Exception as e:
                logger.warning(f"Lỗi khi xóa file tạm WAV sau xử lý {processed_wav_path}: {e}")


STT_PROVIDERS = {
    "groq": (groq_service, "Groq Whisper"),
    "gemini": (gemini_service, "Gemini"),
}


@router.post("/speech/transcriptions", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission("voice:use"))])
async def create_transcription(
    file: UploadFile = File(...),
    provider: Literal["groq", "gemini"] = Query("groq", description="Dịch vụ STT: groq (mặc định) hoặc gemini"),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Tạo bản chép lời (transcription) từ file âm thanh (.m4a, .wav, .mp3, .webm, .aac, .ogg).
    Chạy qua Audio Preprocessing Pipeline (FFmpeg Decode -> Denoise -> VAD -> Optional SV)
    trước khi gửi sang dịch vụ STT, tự động upload Cloudinary và lưu Voice_Record.
    Bắt buộc đăng nhập.
    """
    service, label = STT_PROVIDERS[provider]
    return await _run_stt_pipeline(file, service.transcribe, label, user_id=user_id, db=db)
