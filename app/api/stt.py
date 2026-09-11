import os
import time
import logging
import asyncio
import tempfile
from typing import Optional

# pyrefly: ignore [missing-import]
from fastapi import APIRouter, UploadFile, File, HTTPException, status
from fastapi.responses import JSONResponse

from app.services.audio import (
    AudioPipeline,
    AudioInvalidError,
    AudioTooShortError,
    NoSpeechError,
    SpeakerNotVerifiedError,
    ALLOWED_EXTENSIONS
)
from app.services.groq_service import groq_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Speech to Text"])

MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB
pipeline = AudioPipeline()


@router.post("/stt/groq")
async def stt_groq(file: UploadFile = File(...)):
    """
    Endpoint nhận file âm thanh (.m4a, .wav, .mp3, .webm, .aac, .ogg),
    chạy qua Audio Preprocessing Pipeline (FFmpeg Decode -> Denoise -> VAD -> Optional SV)
    trước khi gửi sang Groq Whisper STT.
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

    logger.info(f"STT audio received: filename='{filename}', size={file_size} bytes")

    # 2. Lưu file gốc tạm thời
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as temp_file:
        temp_file.write(content)
        original_temp_path = temp_file.name

    processed_wav_path: Optional[str] = None

    try:
        # 3. Chạy qua Audio Preprocessing Pipeline (Decode -> Denoise -> VAD -> Speaker Verification)
        # Sử dụng asyncio.to_thread để không block event loop
        preprocess_start = time.time()
        processed_wav_path = await asyncio.to_thread(
            pipeline.process,
            original_temp_path
        )
        preprocess_time = time.time() - preprocess_start
        logger.info(f"Audio preprocessing completed in {preprocess_time:.3f}s")

        # 4. Gửi file WAV đã lọc sạch tới Groq Whisper
        whisper_start = time.time()
        transcribed_text = await asyncio.to_thread(
            groq_service.transcribe,
            processed_wav_path
        )
        whisper_latency = time.time() - whisper_start
        total_time = time.time() - start_time
        logger.info(f"Groq transcription completed in {whisper_latency:.3f}s. Total pipeline time: {total_time:.3f}s")

        return {
            "success": True,
            "code": "STT_SUCCESS",
            "text": transcribed_text
        }

    except NoSpeechError:
        logger.info("VAD detected NO speech in audio.")
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
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "success": False,
                "code": "SPEAKER_NOT_VERIFIED",
                "message": "Không xác định được giọng nói người dùng."
            }
        )

    except Exception as e:
        logger.error(f"Lỗi không xác định khi xử lý STT: {e}", exc_info=True)
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
