import os
import tempfile
import logging
from typing import Optional, List

from app.services.audio.decoder import AudioDecoder, AudioProcessingError, AudioInvalidError, AudioTooShortError
from app.services.audio.noise_suppression import NoiseSuppressor, FFmpegNoiseSuppressor
from app.services.audio.vad import VoiceActivityDetector, NoSpeechError
from app.services.audio.speaker_verification import SpeakerVerifier, DummySpeakerVerifier, SpeakerNotVerifiedError

logger = logging.getLogger(__name__)


class AudioPipeline:
    """
    Orchestration service độc lập cho xử lý âm thanh:
    1. Decode/Convert -> WAV 16kHz Mono PCM 16-bit
    2. Noise Suppression -> Giảm tiếng ồn nền tĩnh (FFmpeg afftdn)
    3. VAD -> Nhận diện và trích xuất phân đoạn giọng nói kèm padding
    4. Optional Speaker Verification -> Xác thực người nói (nếu bật)
    5. Trả về đường dẫn file WAV đã được xử lý chuẩn cho Groq Whisper

    Ràng buộc:
    - Không gọi Groq, không parse intent, không truy cập database.
    - Quản lý và dọn dẹp sạch sẽ toàn bộ file tạm sinh ra.
    """

    def __init__(
        self,
        decoder: Optional[AudioDecoder] = None,
        noise_suppressor: Optional[NoiseSuppressor] = None,
        vad: Optional[VoiceActivityDetector] = None,
        speaker_verifier: Optional[SpeakerVerifier] = None
    ):
        self.decoder = decoder or AudioDecoder()
        self.noise_suppressor = noise_suppressor or FFmpegNoiseSuppressor()
        self.vad = vad or VoiceActivityDetector()
        self.speaker_verifier = speaker_verifier or DummySpeakerVerifier()

    def process(self, input_path: str, user_id: Optional[int] = None) -> str:
        """
        Thực hiện toàn bộ pipeline tiền xử lý audio.
        Trả về đường dẫn file WAV đã qua xử lý.
        Người gọi chịu trách nhiệm xóa file cuối cùng sau khi sử dụng.
        Tất cả các file trung gian (intermediate temp files) được tự động dọn dẹp tại đây.
        """
        intermediate_files: List[str] = []
        final_processed_path: Optional[str] = None

        try:
            logger.info(f"Bắt đầu Audio Pipeline cho file: {os.path.basename(input_path)}")

            # Bước 1: Decode & Normalize format -> WAV 16kHz Mono PCM 16-bit
            tmp_decoded = tempfile.NamedTemporaryFile(suffix="_decoded.wav", delete=False)
            tmp_decoded.close()
            decoded_path = tmp_decoded.name
            intermediate_files.append(decoded_path)

            self.decoder.decode_and_normalize(input_path, decoded_path)
            logger.info("Audio decoded & format normalized")

            # Bước 2: Noise Suppression -> Khử ồn nền
            tmp_denoised = tempfile.NamedTemporaryFile(suffix="_denoised.wav", delete=False)
            tmp_denoised.close()
            denoised_path = tmp_denoised.name
            intermediate_files.append(denoised_path)

            self.noise_suppressor.process(decoded_path, denoised_path)
            logger.info("Noise suppression completed")

            # Bước 3: VAD (Voice Activity Detection) -> Lọc giữ lại giọng nói kèm padding
            tmp_vad = tempfile.NamedTemporaryFile(suffix="_vad.wav", delete=False)
            tmp_vad.close()
            vad_path = tmp_vad.name
            # vad_path sẽ là output cuối cùng nếu mọi bước tiếp theo thành công
            self.vad.process(denoised_path, vad_path)
            logger.info("VAD detected speech")

            # Bước 4: Optional Speaker Verification
            if self.speaker_verifier.verify(vad_path, user_id=user_id) is False:
                logger.warning("Speaker verification failed: Giọng nói không khớp")
                # Đưa vad_path vào danh sách cần dọn dẹp vì bị reject
                intermediate_files.append(vad_path)
                raise SpeakerNotVerifiedError("Không xác định được giọng nói người dùng.")

            logger.info("Speaker verification passed (hoặc đang disabled)")
            final_processed_path = vad_path
            return final_processed_path

        except Exception as e:
            # Nếu có lỗi ở bất kỳ bước nào, xóa luôn cả final_processed_path nếu đã tạo
            if final_processed_path and os.path.exists(final_processed_path):
                try:
                    os.remove(final_processed_path)
                except Exception as ex_del:
                    logger.warning(f"Lỗi khi xóa file tạm {final_processed_path}: {ex_del}")
            raise

        finally:
            # Dọn dẹp sạch sẽ toàn bộ các file trung gian (decoded, denoised)
            for f in intermediate_files:
                if os.path.exists(f):
                    try:
                        os.remove(f)
                    except Exception as ex:
                        logger.warning(f"Lỗi khi dọn dẹp file tạm {f}: {ex}")
