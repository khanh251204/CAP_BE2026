import os
import shutil
import subprocess
import wave
import logging
from typing import Optional

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".wav", ".m4a", ".mp3", ".webm", ".aac", ".ogg"}
MIN_DURATION_SECONDS = 0.3
MAX_DURATION_SECONDS = 30.0


class AudioProcessingError(Exception):
    """Lỗi chung trong quá trình xử lý audio."""
    def __init__(self, message: str, code: str = "AUDIO_INVALID"):
        super().__init__(message)
        self.message = message
        self.code = code


class AudioInvalidError(AudioProcessingError):
    def __init__(self, message: str = "Không thể xử lý file âm thanh."):
        super().__init__(message=message, code="AUDIO_INVALID")


class AudioTooShortError(AudioProcessingError):
    def __init__(self, message: str = "Đoạn ghi âm quá ngắn."):
        super().__init__(message=message, code="AUDIO_TOO_SHORT")


class AudioDecoder:
    """
    Giải mã và chuẩn hóa audio thành định dạng WAV chuẩn cho Whisper:
    - WAV container
    - PCM 16-bit signed
    - Mono (1 channel)
    - 16,000 Hz
    """

    def __init__(self, ffmpeg_path: Optional[str] = None):
        self.ffmpeg_cmd = ffmpeg_path or os.getenv("FFMPEG_PATH") or shutil.which("ffmpeg")
        if not self.ffmpeg_cmd:
            logger.error("FFmpeg không được tìm thấy trong hệ thống PATH.")
            raise AudioProcessingError("FFmpeg chưa được cài đặt hoặc cấu hình trong PATH hệ thống.")

    def decode_and_normalize(self, input_path: str, output_path: str) -> str:
        """
        Thực hiện convert file âm thanh đầu vào thành WAV 16kHz Mono PCM 16-bit.
        """
        if not os.path.exists(input_path):
            raise AudioInvalidError(f"Không tìm thấy file nguồn: {input_path}")

        file_size = os.path.getsize(input_path)
        if file_size == 0:
            raise AudioInvalidError("File âm thanh rỗng.")

        # Xây dựng lệnh FFmpeg
        cmd = [
            self.ffmpeg_cmd,
            "-y",
            "-i", input_path,
            "-ac", "1",
            "-ar", "16000",
            "-sample_fmt", "s16",
            output_path
        ]

        try:
            res = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True
            )
        except subprocess.CalledProcessError as e:
            err_msg = e.stderr.decode("utf-8", errors="ignore") if e.stderr else str(e)
            logger.error(f"Lỗi khi giải mã audio bằng FFmpeg: {err_msg}")
            raise AudioInvalidError("Không thể xử lý file âm thanh.") from e
        except Exception as e:
            logger.error(f"Lỗi thực thi FFmpeg: {e}")
            raise AudioInvalidError(f"Lỗi thực thi FFmpeg: {str(e)}") from e

        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            raise AudioInvalidError("File âm thanh sau giải mã không hợp lệ.")

        # Kiểm tra độ dài file WAV sau giải mã
        duration = self._get_wav_duration(output_path)
        if duration < MIN_DURATION_SECONDS:
            raise AudioTooShortError("Đoạn ghi âm quá ngắn.")
        if duration > MAX_DURATION_SECONDS:
            raise AudioInvalidError(f"Đoạn ghi âm quá dài ({duration:.1f}s), tối đa cho phép là {MAX_DURATION_SECONDS}s.")

        logger.info(f"Đã giải mã audio thành công: duration={duration:.2f}s, size={os.path.getsize(output_path)} bytes")
        return output_path

    @staticmethod
    def _get_wav_duration(wav_path: str) -> float:
        """Tính thời lượng (giây) của file WAV chuẩn."""
        try:
            with wave.open(wav_path, "rb") as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                if rate <= 0:
                    return 0.0
                return frames / float(rate)
        except Exception as e:
            logger.warning(f"Không thể đọc header wave: {e}")
            # Ước tính từ kích thước data: 16000 Hz * 2 bytes * 1 channel = 32,000 bytes/sec
            size = os.path.getsize(wav_path)
            data_size = max(0, size - 44)
            return data_size / 32000.0
