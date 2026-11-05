import json
import re
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional


# ---------------------------------------------------------------------------
# Số lượng đọc bằng chữ: "hai chục", "ba ký rưỡi", "năm lăm", "ba mươi lăm"
# ---------------------------------------------------------------------------
_DIGIT_WORDS = {
    "không": 0, "một": 1, "mốt": 1, "hai": 2, "ba": 3, "bốn": 4, "tư": 4, "năm": 5, "lăm": 5,
    "sáu": 6, "bảy": 7, "bẩy": 7, "tám": 8, "chín": 9,
}
# Từ chỉ "chữ số" không đứng làm hàng chục / hàng trăm
_NOT_TENS = ("lăm", "mốt", "tư")
_NUM_WORD_SET = set(_DIGIT_WORDS) | {"mười", "mươi", "trăm", "linh", "lẻ"}
_NUM_WORD_ALT = "|".join(sorted(_NUM_WORD_SET, key=len, reverse=True))
# Một cụm các từ chỉ số liền nhau ("ba mươi lăm", "một trăm hai mươi")
_NUM_PHRASE = rf"(?:{_NUM_WORD_ALT})(?:[ \t]+(?:{_NUM_WORD_ALT}))*"
# Chỉ khi từ đứng ngay sau số là đơn vị hàng mới coi là số lượng ("hai lon", "ba kg"), tránh đổi "chị Ba", "hai lúa"
_QTY_UNITS = (
    "kg|g|l|ml|lon|chai|thùng|gói|hộp|cái|chiếc|bao|bó|ổ|ly|tô|chén|bát|đĩa|con|quả|trái|bịch|túi|lốc|vỉ|két|"
    "cuốn|quyển|bình|hũ|can|phần|suất|lạng|yến|tạ|tấn|mét|m|cây|tờ|đôi|cặp|viên|miếng|lát|khúc|nải|buồng|chùm|"
    "củ|cọng|bông|hòn|bộ|xấp|cuộn|tấm|thanh|lọ|ống|tuýp"
)
_MONEY_CUE = r"(?:giá|hết|tổng cộng|tổng|chi|trả|đóng|thanh toán|nợ|mỗi\s+\w+)"
_MONEY_AFTER = r"(?:nghìn|ngàn|k|đồng|triệu|tr|tiền|cành|củ)(?![\wÀ-ỹ])"


def parse_vi_number(words: List[str]) -> Optional[int]:
    """Đọc cụm từ chỉ số tiếng Việt (0-999). Không chắc chắn thì trả None để giữ nguyên câu."""
    w = [x.lower() for x in words]
    if not w:
        return None
    total = 0
    if len(w) >= 2 and w[1] == "trăm" and w[0] in _DIGIT_WORDS and w[0] not in _NOT_TENS:
        total = _DIGIT_WORDS[w[0]] * 100
        w = w[2:]
        if not w:
            return total
        if len(w) == 1 and w[0] in _DIGIT_WORDS:
            return None  # "hai trăm năm": nói tắt, có thể là 205 hoặc 250 -> không đoán
    if w[0] in ("linh", "lẻ"):
        return total + _DIGIT_WORDS[w[1]] if total and len(w) == 2 and w[1] in _DIGIT_WORDS else None
    if w[0] == "mười":
        if len(w) == 1:
            return total + 10
        if len(w) == 2 and w[1] in _DIGIT_WORDS and w[1] != "không":
            return total + 10 + _DIGIT_WORDS[w[1]]
        return None
    if len(w) >= 2 and w[1] == "mươi" and w[0] in _DIGIT_WORDS and 2 <= _DIGIT_WORDS[w[0]] <= 9 and w[0] not in _NOT_TENS:
        val = _DIGIT_WORDS[w[0]] * 10
        if len(w) == 2:
            return total + val
        if len(w) == 3 and w[2] in _DIGIT_WORDS and w[2] != "không":
            return total + val + _DIGIT_WORDS[w[2]]
        return None
    # Cách nói tắt: "năm lăm" = 55, "hai lăm" = 25
    if len(w) == 2 and w[1] == "lăm" and w[0] in _DIGIT_WORDS and 1 <= _DIGIT_WORDS[w[0]] <= 9 and w[0] not in _NOT_TENS:
        return total + _DIGIT_WORDS[w[0]] * 10 + 5
    if len(w) == 1 and w[0] in _DIGIT_WORDS and total == 0:
        return _DIGIT_WORDS[w[0]]
    return None


def _fmt_number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:g}"


class NormalizationService:
    """
    Dịch vụ chuẩn hóa từ vựng, đơn vị tính, từ lóng và phương ngữ (Normalization RAG).
    Hoạt động như một retrieval/dictionary layer độc lập, không nhồi context dài vào LLM.
    """

    DEFAULT_DATA_PATH = Path(__file__).resolve().parent / "knowledge" / "normalization_data.json"

    def __init__(self, data_path: Optional[str | Path] = None):
        self.data_path = Path(data_path or self.DEFAULT_DATA_PATH)
        self.knowledge_entries: List[Dict[str, Any]] = []
        # (entry, compiled_pattern) đã sắp xếp cụm từ dài trước — build 1 lần thay vì mỗi request
        self._compiled_entries: List[Tuple[Dict[str, Any], "re.Pattern[str]"]] = []
        self._load_knowledge()

    @staticmethod
    def _term_pattern(term: str) -> "re.Pattern[str]":
        # Tránh match 'mi' trong 'bánh mì' / 'bánh mi' / 'áo sơ mi'
        if term.lower() == "mi":
            raw = rf"(?<!bánh\s)(?<!banh\s)(?<!sơ\s)(?<!so\s)(?<![\wÀ-ỹ]){re.escape(term)}(?![\wÀ-ỹ])"
        else:
            raw = rf"(?<![\wÀ-ỹ]){re.escape(term)}(?![\wÀ-ỹ])"
        return re.compile(raw, flags=re.IGNORECASE)

    def _build_patterns(self):
        sorted_entries = sorted(
            self.knowledge_entries,
            key=lambda item: len(item["term"]),
            reverse=True
        )
        self._compiled_entries = [
            (entry, self._term_pattern(entry["term"].strip()))
            for entry in sorted_entries
        ]

    def _load_knowledge(self):
        """Nạp danh mục mapping chuẩn hóa từ JSON."""
        if not self.data_path.exists():
            print(f"[Warning] Không tìm thấy tệp chuẩn hóa tại {self.data_path}")
            self.knowledge_entries = []
            return

        try:
            with open(self.data_path, "r", encoding="utf-8") as f:
                self.knowledge_entries = json.load(f)
        except Exception as e:
            print(f"[Warning] Lỗi khi đọc {self.data_path}: {e}")
            self.knowledge_entries = []

        self._build_patterns()

    def retrieve_normalization_candidates(self, text: str) -> Dict[str, str]:
        """
        Trích xuất các ứng viên chuẩn hóa (term -> normalized) xuất hiện trong câu.
        Ví dụ: '20 cân cam' -> {'cân': 'kg'}
               'Bữa ni tui bán 5 cân cam' -> {'bữa ni': 'hôm nay', 'tui': 'tôi', 'cân': 'kg'}
        """
        if not text or not text.strip():
            return {}

        candidates: Dict[str, str] = {}
        for entry, pattern in self._compiled_entries:
            if pattern.search(text):
                candidates[entry["term"].strip()] = entry["normalized"].strip()

        return candidates

    def retrieve_candidates_metadata(self, text: str) -> List[Dict[str, Any]]:
        """Trả về toàn bộ metadata của các candidate xuất hiện trong text."""
        if not text or not text.strip():
            return []

        return [entry for entry, pattern in self._compiled_entries if pattern.search(text)]

    def _normalize_money(self, text: str) -> Tuple[str, Dict[str, str]]:
        """
        Chuẩn hóa các biểu thức tiền tệ tiếng Việt trong câu thoại thành số nguyên VND + đồng.
        Bảo vệ token tiền tệ khỏi việc bị quantity parser nhận nhầm thành số lượng hàng.
        """
        if not text or not text.strip():
            return text, {}

        normalized_text = text
        changes = {}

        # 0. Cách nói tiền đời thường. Chạy TRƯỚC các mẫu bên dưới để "3 nghìn rưỡi" không bị cắt thành "3 nghìn".
        def repl_amount(factor, extra=0):
            def _repl(match):
                orig = match.group(0)
                res = f"{int(match.group(1)) * factor + extra} đồng"
                changes[orig] = res
                return res
            return _repl

        def repl_prefixed(factor):
            # Giữ lại từ báo hiệu giá ("giá", "hết", "tổng"...) để không nhầm với số lượng
            def _repl(match):
                orig = match.group(0)
                raw = match.group(2).lower()
                n = int(raw) if raw.isdigit() else parse_vi_number([raw])
                if n is None:
                    return orig
                res = f"{n * factor} đồng"
                changes[orig] = f"{match.group(1)} {res}"
                return f"{match.group(1)} {res}"
            return _repl

        def repl_tram(match):
            orig = match.group(0)
            value = int(match.group(2)) * 100000
            tail = match.group(3)
            if tail:
                value += 50000 if tail.lower() == "rưỡi" else int(tail) * 10000
            res = f"{value} đồng"
            changes[orig] = f"{match.group(1)} {res}"
            return f"{match.group(1)} {res}"

        price_cue = r"(giá|hết|tổng cộng|tổng|mỗi\s+\w+)"
        # 3 nghìn rưỡi / 2k rưỡi -> 3500 / 2500
        normalized_text = re.sub(
            r"\b(\d+)\s*(?:k|nghìn|ngàn|cành)\s*rưỡi\b", repl_amount(1000, 500), normalized_text, flags=re.IGNORECASE
        )
        # 30 cành -> 30000 (cành = nghìn)
        normalized_text = re.sub(r"\b(\d+)\s*cành\b", repl_amount(1000), normalized_text, flags=re.IGNORECASE)
        # 1 củ rưỡi -> 1500000; "1 củ" chỉ tính là tiền khi đứng cuối câu hoặc trước "đồng" (tránh "5 củ cải")
        normalized_text = re.sub(
            r"\b(\d+)\s*củ\s*rưỡi\b", repl_amount(1000000, 500000), normalized_text, flags=re.IGNORECASE
        )
        normalized_text = re.sub(
            r"\b(\d+)\s*củ(?=\s*(?:đồng\b|[.,!?]*\s*$))", repl_amount(1000000), normalized_text, flags=re.IGNORECASE
        )
        # 5 trăm nghìn -> 500000
        normalized_text = re.sub(
            r"\b(\d+)\s*trăm\s*(?:nghìn|ngàn)\b", repl_amount(100000), normalized_text, flags=re.IGNORECASE
        )
        # "Chi 3 lít tiền sửa máy lạnh": lít + "tiền" là tiền (1 lít = 100 nghìn), không phải thể tích
        normalized_text = re.sub(r"\b(\d+)\s*lít(?=\s+tiền\b)", repl_amount(100000), normalized_text, flags=re.IGNORECASE)
        # giá 1 xị / giá một xị -> 100000
        normalized_text = re.sub(
            rf"\b{price_cue}\s+(\d+|một|hai|ba|bốn|năm|sáu|bảy|tám|chín)\s*xị\b",
            repl_prefixed(100000), normalized_text, flags=re.IGNORECASE
        )
        # giá 2 trăm 5 -> 250000; hết 1 trăm 8 -> 180000; giá 2 trăm rưỡi -> 250000
        normalized_text = re.sub(
            rf"\b{price_cue}\s+(\d+)\s*trăm(?:\s+(rưỡi|\d))?(?!\d)"
            r"(?!\s*(?:nghìn|ngàn|k\b|triệu|tr\b|đồng|cái|chai|lon|thùng|gói|con|bao|hộp|kg|ký|kí|lít|người))",
            repl_tram, normalized_text, flags=re.IGNORECASE
        )

        # 0b. Số tiền kiểu 'củ' / 'trăm' khi có từ chỉ tiền
        money_verb = r"(chi|trả|đóng|thanh toán|ghi nợ|nợ|giá|hết|tổng cộng|tổng)"
        veggie = r"(?!\s*(?:cải|hành|tỏi|gừng|nghệ|sen|năng|khoai|kiệu|đậu|dền|sắn|su|riềng|gấc))"

        def repl_cu(match):
            orig = match.group(0)
            value = int(match.group(2)) * 1000000
            tail = match.group(3)
            if tail:
                value += 500000 if tail.lower() == "rưỡi" else int(tail) * 100000
            res = f"{value} đồng"
            changes[orig] = f"{match.group(1)} {res}"
            return f"{match.group(1)} {res}"

        # "Chi 1 củ sửa tủ lạnh" -> 1000000; "nợ 2 củ rưỡi" -> 2500000; "1 củ 2" -> 1200000
        normalized_text = re.sub(
            rf"\b{money_verb}\s+(\d+)\s*củ(?:\s+(rưỡi|\d))?(?!\d)" + veggie,
            repl_cu, normalized_text, flags=re.IGNORECASE
        )

        # "Đóng tiền internet 2 trăm" (kết thúc câu, không có danh từ phía sau) -> 200000
        def repl_tram_end(match):
            orig = match.group(0)
            value = int(match.group(1)) * 100000
            tail = match.group(2)
            if tail:
                value += 50000 if tail.lower() == "rưỡi" else int(tail) * 10000
            res = f"{value} đồng"
            changes[orig] = res
            return res

        if re.search(r"\b(?:chi|trả|đóng|thanh toán|tiền|nợ|giá|hết|tổng)\b", normalized_text, flags=re.IGNORECASE):
            normalized_text = re.sub(
                r"\b(\d+)\s*trăm(?:\s+(rưỡi|\d))?(?=\s*[.,!?]*\s*$)",
                repl_tram_end, normalized_text, flags=re.IGNORECASE
            )

        # 1. Pattern 1 triệu rưỡi / 1tr rưỡi / một triệu rưỡi
        def repl_ruoi(match):
            orig = match.group(0)
            prefix = match.group(1).lower() if match.group(1) else "1"
            word_digits = {"một": 1, "mot": 1, "hai": 2, "ba": 3, "bốn": 4, "năm": 5}
            millions = word_digits[prefix] if prefix in word_digits else int(prefix)
            val = millions * 1000000 + 500000
            res = f"{val} đồng"
            changes[orig] = res
            return res

        normalized_text = re.sub(
            r"\b(1|2|3|4|5|6|7|8|9|một|hai|ba|bốn|năm)\s*(?:triệu|tr)\s*rưỡi\b",
            repl_ruoi, normalized_text, flags=re.IGNORECASE
        )

        # 2. Pattern X triệu Y / XtrY (không theo sau bởi đơn vị hàng)
        def repl_x_tr_y(match):
            orig = match.group(0)
            x = int(match.group(1))
            y_str = match.group(2)
            if len(y_str) == 1:
                y = int(y_str) * 100000
            elif len(y_str) == 2:
                y = int(y_str) * 10000
            elif len(y_str) == 3:
                y = int(y_str) * 1000
            else:
                y = int(y_str)
            val = x * 1000000 + y
            res = f"{val} đồng"
            changes[orig] = res
            return res

        normalized_text = re.sub(
            r"\b(\d+)\s*(?:triệu|tr)\s*(\d{1,3})\b(?!\s*kg|\s*ký|\s*kí|\s*con|\s*cái|\s*bao|\s*thùng|\s*gói|\s*lạng)",
            repl_x_tr_y, normalized_text, flags=re.IGNORECASE
        )

        # 3. Pattern X triệu / Xtr (kể cả có hoặc không có chữ đồng)
        def repl_tr(match):
            orig = match.group(0)
            x = int(match.group(1))
            res = f"{x * 1000000} đồng"
            changes[orig] = res
            return res

        normalized_text = re.sub(r"\b(\d+)\s*(?:triệu|tr)(?:\s*đồng)?\b", repl_tr, normalized_text, flags=re.IGNORECASE)

        # 4. Pattern Xk / X nghìn / X ngàn (kể cả có hoặc không có chữ đồng)
        def repl_k(match):
            orig = match.group(0)
            x = int(match.group(1))
            res = f"{x * 1000} đồng"
            changes[orig] = res
            return res

        normalized_text = re.sub(r"\b(\d+)\s*(?:k|nghìn|ngàn)(?:\s*đồng)?\b", repl_k, normalized_text, flags=re.IGNORECASE)

        # 5. Chữ viết số tiền lớn
        word_money_patterns = [
            (r"\bmột\s*triệu\b", 1000000),
            (r"\bhai\s*triệu\b", 2000000),
            (r"\bba\s*triệu\b", 3000000),
            (r"\bbốn\s*triệu\b", 4000000),
            (r"\bnăm\s*triệu\b", 5000000),
            (r"\btám\s*triệu\b", 8000000),
            (r"\bmười\s*triệu\b", 10000000),
            (r"\bmười\s*lăm\s*triệu\b", 15000000),
            (r"\bhai\s*mươi\s*triệu\b", 20000000),
            (r"\bnăm\s*trăm\s*nghìn\b", 500000),
            (r"\bnăm\s*trăm\s*ngàn\b", 500000),
            (r"\bmột\s*trăm\s*nghìn\b", 100000),
            (r"\bmột\s*trăm\s*ngàn\b", 100000),
        ]
        for pat, val in word_money_patterns:
            def repl_word(m, v=val):
                orig = m.group(0)
                res = f"{v} đồng"
                changes[orig] = res
                return res
            normalized_text = re.sub(pat, repl_word, normalized_text, flags=re.IGNORECASE)

        normalized_text = re.sub(r"đồng\s+đồng", "đồng", normalized_text)
        return normalized_text, changes

    def _normalize_quantities(self, text: str) -> Tuple[str, Dict[str, str]]:
        """
        Số lượng nói kiểu đời thường -> chữ số (chạy SAU bước tiền và từ điển, nên "ký" đã thành "kg"):
          "hai chục trứng" -> "20 trứng"      "hai tá bút" -> "24 bút"
          "ba kg rưỡi" -> "3.5 kg"            "năm lăm kg" -> "55 kg"       "ba mươi lăm cái ly" -> "35 cái ly"
        Chỉ đổi khi chắc chắn là SỐ LƯỢNG HÀNG: số bằng chữ phải đứng ngay trước đơn vị / "chục" / "tá";
        "chục" đứng sau từ báo giá ("giá hai chục") hoặc trước "nghìn/đồng" là tiền nên giữ nguyên.
        """
        if not text or not text.strip():
            return text, {}
        changes: Dict[str, str] = {}

        def number_of(raw: str) -> Optional[int]:
            raw = raw.strip()
            if raw.isdigit():
                return int(raw)
            return parse_vi_number(raw.lower().split())

        def record(orig: str, res: str) -> str:
            changes[orig.strip()] = res.strip()
            return res

        # 1. "<số> chục" / "<số> tá"
        def repl_group(factor: int):
            def _repl(m: "re.Match[str]") -> str:
                before = m.string[max(0, m.start() - 24):m.start()]
                after = m.string[m.end():m.end() + 24]
                if re.search(rf"{_MONEY_CUE}\s*$", before, flags=re.IGNORECASE) or re.match(
                    rf"\s*{_MONEY_AFTER}", after, flags=re.IGNORECASE
                ):
                    return m.group(0)
                n = number_of(m.group("num"))
                if n is None:
                    return m.group(0)
                return record(m.group(0), f"{n * factor}")
            return _repl

        out = text
        for word, factor in (("chục", 10), ("tá", 12)):
            out = re.sub(
                rf"(?<![\wÀ-ỹ])(?P<num>\d+|{_NUM_PHRASE})[ \t]+{word}(?![\wÀ-ỹ])",
                repl_group(factor), out, flags=re.IGNORECASE
            )

        # 2. số bằng chữ đứng ngay trước đơn vị hàng -> chữ số
        def repl_words(m: "re.Match[str]") -> str:
            # "giá 20000 đồng một chai": "một" là đơn giá cho MỘT đơn vị, giữ nguyên cho LLM đọc
            if m.group("num").lower() in ("một", "mốt") and re.search(
                r"(?:đồng|nghìn|ngàn|triệu|giá|mỗi|k|chục)\s*$", m.string[max(0, m.start() - 16):m.start()], flags=re.IGNORECASE
            ):
                return m.group(0)
            n = number_of(m.group("num"))
            if n is None:
                return m.group(0)
            record(m.group("num"), f"{n}")
            return f"{n}{m.group('tail')}"

        out = re.sub(
            rf"(?<![\wÀ-ỹ])(?P<num>{_NUM_PHRASE})(?P<tail>[ \t]+(?:{_QTY_UNITS})(?![\wÀ-ỹ]))",
            repl_words, out, flags=re.IGNORECASE
        )

        # 3. "3 kg rưỡi" -> "3.5 kg"
        def repl_half(m: "re.Match[str]") -> str:
            whole = float(m.group("n").replace(",", "."))
            return record(m.group(0), f"{_fmt_number(whole + 0.5)} {m.group('u')}")

        out = re.sub(
            r"(?<![\wÀ-ỹ])(?P<n>\d+(?:[.,]\d+)?)\s*(?P<u>kg|l|g|ml|yến|tạ|tấn|mét|m)\s+rưỡi(?![\wÀ-ỹ])",
            repl_half, out, flags=re.IGNORECASE
        )
        return out, changes

    def normalize(self, text: str) -> Tuple[str, Dict[str, str]]:
        """
        Chuẩn hóa câu văn bản một cách thận trọng (conservative):
        1. Chuẩn hóa an toàn tiền tệ (money expressions)
        2. Chuẩn hóa từ vựng, đơn vị và phương ngữ từ dictionary
        
        Trả về:
            (normalized_text, changes_dict)
        """
        if not text or not text.strip():
            return text, {}

        normalized_text = text
        changes_applied = {}

        # 1. Chuẩn hóa money
        normalized_text, money_changes = self._normalize_money(normalized_text)
        changes_applied.update(money_changes)

        # 2. Trích xuất các candidate chuẩn hóa dictionary
        candidates = self.retrieve_normalization_candidates(normalized_text)
        if candidates:
            # Sắp xếp theo độ dài giảm dần để cụm từ dài được thay thế trước
            sorted_terms = sorted(candidates.keys(), key=lambda t: len(t), reverse=True)

            for term in sorted_terms:
                target_norm = candidates[term]

                pattern = self._term_pattern(term)

                def replace_fn(match):
                    original_chunk = match.group(0)
                    if original_chunk and original_chunk[0].isupper():
                        return target_norm.capitalize()
                    return target_norm

                new_text, count = pattern.subn(replace_fn, normalized_text)
                if count > 0:
                    normalized_text = new_text
                    changes_applied[term] = target_norm

        # 3. Số lượng nói kiểu đời thường (hai chục, ba kg rưỡi, năm lăm...)
        normalized_text, qty_changes = self._normalize_quantities(normalized_text)
        changes_applied.update(qty_changes)

        # Chuẩn hóa lại khoảng trắng thừa nếu có
        normalized_text = re.sub(r"\s+", " ", normalized_text).strip()

        return normalized_text, changes_applied

