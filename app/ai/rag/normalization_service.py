import json
import re
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional


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
        # Tránh match 'mi' trong 'bánh mì' / 'bánh mi'
        if term.lower() == "mi":
            raw = rf"(?<!bánh\s)(?<!banh\s)(?<![\wÀ-ỹ]){re.escape(term)}(?![\wÀ-ỹ])"
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

        # Chuẩn hóa lại khoảng trắng thừa nếu có
        normalized_text = re.sub(r"\s+", " ", normalized_text).strip()

        return normalized_text, changes_applied

