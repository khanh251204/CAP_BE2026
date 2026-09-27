import re
from typing import Optional

# Các cụm từ và từ khóa ảo giác phổ biến của Whisper khi gặp im lặng hoặc tạp âm
WHISPER_HALLUCINATION_PATTERNS = [
    r"ghiền\s+mì\s+gõ",
    r"ghien\s+mi\s+go",
    r"mì\s+gõ",
    r"subcribe",
    r"subscribe",
    r"đăng\s+ký\s+kênh",
    r"dang\s+ky\s+kenh",
    r"nhớ\s+đăng\s+ký",
    r"ủng\s+hộ\s+kênh",
    r"kênh\s+của\s+mình",
    r"like\s+và\s+subscribe",
    r"like\s+and\s+subscribe",
    r"like,\s*share",
    r"hãy\s+(?:like|subscribe|subcribe|chia\s+sẻ|bấm\s+chuông|nhấn\s+chuông)",
    r"cảm\s+ơn\s+(?:các\s+bạn|quý\s+vị|mọi\s+người)\s+(?:đã\s+theo\s+dõi|đã\s+xem)",
    r"cảm\s+ơn\s+(?:đã\s+theo\s+dõi|đã\s+xem|đã\s+lắng\s+nghe)",
    r"hẹn\s+gặp\s+lại\s+(?:các\s+bạn|quý\s+vị|trong\s+video)",
    r"chúc\s+các\s+bạn\s+(?:xem\s+video\s+vui\s+vẻ|vui\s+vẻ)",
    r"video\s+tiếp\s+theo",
    r"xem\s+video\s+tiếp\s+theo",
    r"subtitles?\s+by",
    r"transcribed\s+by",
    r"amara\.org",
    r"phụ\s+đề\s+bởi",
    r"bản\s+dịch\s+bởi",
    r"hãy\s+nhấn\s+chuông",
    r"bấm\s+chuông",
]

COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in WHISPER_HALLUCINATION_PATTERNS]


def is_speech_hallucination(text: Optional[str]) -> bool:
    """
    Kiểm tra xem chuỗi văn bản nhận diện được từ STT có phải là:
    1. Chuỗi rỗng hoặc chỉ chứa khoảng trắng, dấu câu.
    2. Ảo giác kinh điển của Whisper (ví dụ: 'Hãy subcribe cho kênh GHiền mì gõ').
    """
    if not text:
        return True

    clean = text.strip()
    if not clean:
        return True

    # Loại bỏ dấu câu
    clean_no_punct = re.sub(r"[.,?!:;…\-~\"'()\[\]{}]+", " ", clean).strip()
    clean_no_punct = re.sub(r"\s+", " ", clean_no_punct)

    # Nếu độ dài quá ngắn không thể cấu thành câu giao dịch
    if len(clean_no_punct) < 2:
        return True

    clean_lower = clean_no_punct.lower()

    for pattern in COMPILED_PATTERNS:
        if pattern.search(clean_lower):
            return True

    return False
