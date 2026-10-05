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

    def __init__(
        self,
        data_path: Optional[str | Path] = None,
        vector_store: Optional[Any] = None
    ):
        self.data_path = Path(data_path or self.DEFAULT_DATA_PATH)
        self.vector_store = vector_store
        self.knowledge_entries: List[Dict[str, Any]] = []
        self._load_knowledge()

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

    def retrieve_normalization_candidates(self, text: str) -> Dict[str, str]:
        """
        Trích xuất các ứng viên chuẩn hóa (term -> normalized) xuất hiện trong câu.
        Ví dụ: '20 cân cam' -> {'cân': 'kg'}
               'Bữa ni tui bán 5 cân cam' -> {'bữa ni': 'hôm nay', 'tui': 'tôi', 'cân': 'kg'}
        """
        if not text or not text.strip():
            return {}

        candidates: Dict[str, str] = {}
        # Sắp xếp ưu tiên các cụm từ dài trước (greedy longest match)
        sorted_entries = sorted(
            self.knowledge_entries,
            key=lambda item: len(item["term"]),
            reverse=True
        )

        for entry in sorted_entries:
            term = entry["term"].strip()
            normalized = entry["normalized"].strip()

            # Tránh match 'mi' trong 'bánh mì' / 'bánh mi'
            if term.lower() == "mi":
                pattern = rf"(?<!bánh\s)(?<!banh\s)(?<![\wÀ-ỹ]){re.escape(term)}(?![\wÀ-ỹ])"
            else:
                pattern = rf"(?<![\wÀ-ỹ]){re.escape(term)}(?![\wÀ-ỹ])"

            if re.search(pattern, text, flags=re.IGNORECASE):
                candidates[term] = normalized

        return candidates

    def retrieve_candidates_metadata(self, text: str) -> List[Dict[str, Any]]:
        """Trả về toàn bộ metadata của các candidate xuất hiện trong text."""
        if not text or not text.strip():
            return []

        matched = []
        sorted_entries = sorted(
            self.knowledge_entries,
            key=lambda item: len(item["term"]),
            reverse=True
        )

        for entry in sorted_entries:
            term = entry["term"].strip()
            if term.lower() == "mi":
                pattern = rf"(?<!bánh\s)(?<!banh\s)(?<![\wÀ-ỹ]){re.escape(term)}(?![\wÀ-ỹ])"
            else:
                pattern = rf"(?<![\wÀ-ỹ]){re.escape(term)}(?![\wÀ-ỹ])"

            if re.search(pattern, text, flags=re.IGNORECASE):
                matched.append(entry)

        return matched

    def normalize(self, text: str) -> Tuple[str, Dict[str, str]]:
        """
        Chuẩn hóa câu văn bản một cách thận trọng (conservative).
        Chỉ thay thế các từ ngữ có mapping rõ ràng từ knowledge base.
        Nếu không có candidate nào, giữ nguyên text ban đầu.
        
        Trả về:
            (normalized_text, changes_dict)
        """
        if not text or not text.strip():
            return text, {}

        candidates = self.retrieve_normalization_candidates(text)
        if not candidates:
            return text, {}

        normalized_text = text
        changes_applied = {}

        # Sắp xếp theo độ dài giảm dần để cụm từ dài được thay thế trước
        sorted_terms = sorted(candidates.keys(), key=lambda t: len(t), reverse=True)

        for term in sorted_terms:
            target_norm = candidates[term]

            if term.lower() == "mi":
                pattern = rf"(?<!bánh\s)(?<!banh\s)(?<![\wÀ-ỹ]){re.escape(term)}(?![\wÀ-ỹ])"
            else:
                pattern = rf"(?<![\wÀ-ỹ]){re.escape(term)}(?![\wÀ-ỹ])"

            def replace_fn(match):
                original_chunk = match.group(0)
                # Giữ nguyên chữ hoa đầu câu nếu từ gốc viết hoa
                if original_chunk and original_chunk[0].isupper():
                    return target_norm.capitalize()
                return target_norm

            new_text, count = re.subn(pattern, replace_fn, normalized_text, flags=re.IGNORECASE)
            if count > 0:
                normalized_text = new_text
                changes_applied[term] = target_norm

        # Chuẩn hóa lại khoảng trắng thừa nếu có
        normalized_text = re.sub(r"\s+", " ", normalized_text).strip()

        return normalized_text, changes_applied
