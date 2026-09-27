import os
import logging
from abc import ABC, abstractmethod
from typing import Optional

from app.services.audio.decoder import AudioProcessingError

logger = logging.getLogger(__name__)


class SpeakerNotVerifiedError(AudioProcessingError):
    def __init__(self, message: str = "Không xác định được giọng nói người dùng."):
        super().__init__(message=message, code="SPEAKER_NOT_VERIFIED")


class SpeakerVerifier(ABC):
    """
    Interface trừu tượng cho xác thực người nói (Speaker Verification / Biometrics).
    Hỗ trợ kiểm tra xem giọng nói có khớp với chủ tài khoản hay không trước khi gửi Whisper.
    """

    @abstractmethod
    def verify(self, audio_path: str, user_id: Optional[int] = None) -> bool:
        """
        Trả về True nếu giọng nói hợp lệ hoặc tính năng đang tắt.
        Trả về False nếu giọng nói không khớp với profile của người dùng.
        """
        pass


class DummySpeakerVerifier(SpeakerVerifier):
    """
    Implementation mặc định:
    - SPEAKER_VERIFICATION_ENABLED (mặc định: False)
    - SPEAKER_THRESHOLD (mặc định: 0.75)
    - Khi tắt: luôn cho phép (verify -> True) mà không chặn pipeline.
    - Sẵn sàng adapter để tích hợp mô hình nhúng giọng nói (ECAPA-TDNN, ResNet) sau này.
    """

    def __init__(
        self,
        enabled: Optional[bool] = None,
        threshold: Optional[float] = None
    ):
        if enabled is not None:
            self.enabled = enabled
        else:
            env_val = os.getenv("SPEAKER_VERIFICATION_ENABLED", "false").strip().lower()
            self.enabled = env_val in ("1", "true", "yes", "on")

        if threshold is not None:
            self.threshold = threshold
        else:
            self.threshold = float(os.getenv("SPEAKER_THRESHOLD", "0.75"))

    def verify(self, audio_path: str, user_id: Optional[int] = None) -> bool:
        if not self.enabled:
            logger.debug("Speaker verification đang tắt (disabled), bỏ qua bước xác thực giọng nói.")
            return True

        if not os.path.exists(audio_path):
            logger.warning(f"Speaker verification: File không tồn tại {audio_path}")
            return False

        # Khi tính năng được bật nhưng chưa có profile sinh trắc học cụ thể:
        # Không tự động tạo profile, không tự coi voice đầu là voice owner.
        logger.warning("Speaker verification đang BẬT nhưng chưa có profile vân giọng được đăng ký.")
        return False
