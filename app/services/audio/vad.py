import os
import wave
import logging
import tempfile
import collections
from typing import List, Optional
import webrtcvad

from app.services.audio.decoder import AudioProcessingError, AudioTooShortError

logger = logging.getLogger(__name__)


class NoSpeechError(AudioProcessingError):
    def __init__(self, message: str = "Không phát hiện giọng nói."):
        super().__init__(message=message, code="NO_SPEECH")


class VoiceActivityDetector:
    """
    Phát hiện giọng nói và cắt bỏ các khoảng im lặng / tạp âm bằng WebRTC VAD.
    - Sample Rate: 16,000 Hz
    - Frame Duration: 30 ms (480 samples = 960 bytes)
    - VAD Mode: 2 (Cân bằng độ nhạy)
    - Hangover / Padding: 300 ms trước và sau mỗi đoạn speech để tránh mất âm đầu/âm cuối.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        frame_duration_ms: int = 30,
        vad_mode: int = 2,
        padding_duration_ms: int = 300,
        min_speech_duration_ms: int = 300
    ):
        self.sample_rate = sample_rate
        self.frame_duration_ms = frame_duration_ms
        self.frame_bytes = int(self.sample_rate * (self.frame_duration_ms / 1000.0) * 2)
        self.vad_mode = vad_mode
        self.vad = webrtcvad.Vad(self.vad_mode)
        self.num_padding_frames = int(padding_duration_ms / self.frame_duration_ms)
        self.min_speech_frames = int(min_speech_duration_ms / self.frame_duration_ms)

    def process(self, input_wav_path: str, output_wav_path: Optional[str] = None) -> str:
        """
        Quét file WAV đầu vào, lọc bỏ khoảng lặng và giữ lại các đoạn có giọng nói kèm padding.
        Trả về đường dẫn file WAV chỉ chứa giọng nói.
        Ném NoSpeechError nếu không phát hiện được giọng nói.
        """
        if not os.path.exists(input_wav_path):
            raise FileNotFoundError(f"Input file not found: {input_wav_path}")

        # Đọc dữ liệu audio PCM từ WAV
        pcm_data, sample_rate, num_channels = self._read_wav(input_wav_path)
        if sample_rate != self.sample_rate or num_channels != 1:
            raise AudioProcessingError(f"VAD yêu cầu WAV 16kHz Mono. Nhận được: {sample_rate}Hz, {num_channels}ch.")

        frames = self._frame_generator(pcm_data)
        if not frames:
            raise NoSpeechError("Không phát hiện giọng nói.")

        # Thuật toán Ring-buffer + Hangover để giữ padding trước và sau giọng nói
        kept_frames: List[bytes] = []
        ring_buffer = collections.deque(maxlen=self.num_padding_frames)
        triggered = False
        hangover_counter = 0
        voiced_frames_count = 0

        for frame in frames:
            is_speech = self.vad.is_speech(frame, self.sample_rate)

            if is_speech:
                voiced_frames_count += 1
                if not triggered:
                    # Bắt đầu phát hiện giọng nói: kéo cả buffer đệm âm thanh phía trước (pre-padding)
                    triggered = True
                    kept_frames.extend(ring_buffer)
                    ring_buffer.clear()
                # Reset bộ đếm hangover khi vẫn còn voice
                hangover_counter = self.num_padding_frames
                kept_frames.append(frame)
            else:
                if triggered:
                    # Đang trong trạng thái có giọng nói nhưng gặp frame im lặng
                    if hangover_counter > 0:
                        hangover_counter -= 1
                        kept_frames.append(frame)  # Post-padding giữ đuôi âm thanh
                    else:
                        triggered = False
                        ring_buffer.append(frame)
                else:
                    ring_buffer.append(frame)

        # Kiểm tra điều kiện có giọng nói
        if voiced_frames_count == 0 or not kept_frames:
            logger.info("VAD: Không phát hiện bất kỳ frame giọng nói nào.")
            raise NoSpeechError("Không phát hiện giọng nói.")

        # Kiểm tra độ dài giọng nói tối thiểu
        total_kept_duration_sec = (len(kept_frames) * self.frame_duration_ms) / 1000.0
        if total_kept_duration_sec < 0.3:
            logger.info(f"VAD: Tổng thời lượng giọng nói quá ngắn ({total_kept_duration_sec:.2f}s).")
            raise AudioTooShortError("Đoạn ghi âm quá ngắn.")

        if output_wav_path is None:
            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            tmp.close()
            output_wav_path = tmp.name

        self._write_wav(output_wav_path, b"".join(kept_frames), self.sample_rate)
        logger.info(
            f"VAD phát hiện giọng nói thành công: {voiced_frames_count} voiced frames, "
            f"độ dài sau lọc={total_kept_duration_sec:.2f}s"
        )
        return output_wav_path

    def _frame_generator(self, audio_data: bytes) -> List[bytes]:
        """Chia byte stream PCM thành các frame có kích thước cố định."""
        offset = 0
        frames = []
        while offset + self.frame_bytes <= len(audio_data):
            frames.append(audio_data[offset:offset + self.frame_bytes])
            offset += self.frame_bytes
        return frames

    @staticmethod
    def _read_wav(file_path: str):
        """Đọc raw PCM bytes từ WAV file."""
        with wave.open(file_path, "rb") as wf:
            num_channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            sample_rate = wf.getframerate()
            if sample_width != 2:
                raise AudioProcessingError("VAD chỉ hỗ trợ 16-bit PCM WAV.")
            pcm_data = wf.readframes(wf.getnframes())
            return pcm_data, sample_rate, num_channels

    @staticmethod
    def _write_wav(file_path: str, pcm_data: bytes, sample_rate: int):
        """Ghi raw PCM bytes thành file WAV chuẩn 16-bit mono."""
        with wave.open(file_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm_data)
