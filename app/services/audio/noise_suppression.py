import os
import shutil
import subprocess
import logging
import tempfile
from abc import ABC, abstractmethod
from typing import Optional

logger = logging.getLogger(__name__)


class NoiseSuppressor(ABC):
    """
    Interface trừu tượng cho các thuật toán Noise Suppression (Khử ồn nền).
    Lưu ý: Volume Normalization KHÔNG phải là Noise Suppression.
    """

    @abstractmethod
    def process(self, input_path: str, output_path: Optional[str] = None) -> str:
        """
        Nhận vào file WAV 16kHz Mono PCM 16-bit, áp dụng thuật toán giảm nhiễu nền
        và trả về đường dẫn file WAV đã được làm sạch.
        """
        pass


class FFmpegNoiseSuppressor(NoiseSuppressor):
    """
    Khử ồn nền sử dụng bộ lọc Fourier Transform Denoise (afftdn) tích hợp trong FFmpeg.
    - afftdn: Phân tích phổ FFT và triệt tiêu tiếng ồn tĩnh (hiss, fan, humming, ambient noise)
    - highpass=f=80: Loại bỏ rung động tần số cực thấp (<80Hz)
    - Giải pháp nhẹ, ổn định, không yêu cầu thư viện C++ phức tạp ngoài FFmpeg sẵn có.
    """

    def __init__(
        self,
        noise_floor_db: float = -25.0,
        ffmpeg_cmd: Optional[str] = None
    ):
        self.noise_floor_db = noise_floor_db
        self.ffmpeg_cmd = ffmpeg_cmd or os.getenv("FFMPEG_PATH") or shutil.which("ffmpeg") or "ffmpeg"

    def process(self, input_path: str, output_path: Optional[str] = None) -> str:
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Input file not found: {input_path}")

        if output_path is None:
            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            tmp.close()
            output_path = tmp.name

        # Bộ lọc khử nhiễu FFT (afftdn) + lọc thông cao loại bỏ tạp âm dưới 80Hz
        filter_str = f"highpass=f=80,afftdn=nf={self.noise_floor_db}:tn=1"

        cmd = [
            self.ffmpeg_cmd,
            "-y",
            "-i", input_path,
            "-af", filter_str,
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
            logger.info(f"Đã hoàn thành khử ồn (FFmpeg afftdn, nf={self.noise_floor_db}dB)")
            return output_path
        except subprocess.CalledProcessError as e:
            err = e.stderr.decode("utf-8", errors="ignore") if e.stderr else str(e)
            logger.warning(f"Lỗi khi chạy FFmpeg afftdn ({err}), fallback sang passthrough input.")
            shutil.copyfile(input_path, output_path)
            return output_path
        except Exception as e:
            logger.warning(f"Không thể áp dụng noise suppression: {e}, fallback sang input.")
            shutil.copyfile(input_path, output_path)
            return output_path


class PassthroughNoiseSuppressor(NoiseSuppressor):
    """Bộ khử ồn passthrough (giữ nguyên âm thanh, dùng cho testing hoặc bypass)."""

    def process(self, input_path: str, output_path: Optional[str] = None) -> str:
        if output_path is None or output_path == input_path:
            return input_path
        shutil.copyfile(input_path, output_path)
        return output_path
