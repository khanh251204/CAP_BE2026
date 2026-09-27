# app/ai/rag/rag_service.py

from typing import Optional, Dict, Tuple, List, Any
from app.ai.rag.vector_store import VectorStore
from app.ai.rag.normalization_service import NormalizationService


class RAGService:

    def __init__(
        self,
        vector_store: VectorStore,
        normalization_service: Optional[NormalizationService] = None
    ):
        self.vector_store = vector_store
        self.normalizer = normalization_service or NormalizationService(vector_store=vector_store)

    # ========================================================
    # NORMALIZATION LAYER (NEW ARCHITECTURE)
    # ========================================================
    def retrieve_normalization_candidates(self, text: str) -> Dict[str, str]:
        """Trích xuất mapping từ vựng/đơn vị/phương ngữ cho câu nói."""
        return self.normalizer.retrieve_normalization_candidates(text)

    def normalize(self, text: str) -> Tuple[str, Dict[str, str]]:
        """
        Chuẩn hóa câu văn bản trước khi đưa vào LLM:
        Ví dụ: 'Bữa ni tui bán 5 cân cam' -> ('Hôm nay tôi bán 5 kg cam', {'bữa ni': 'hôm nay', 'tui': 'tôi', 'cân': 'kg'})
        """
        return self.normalizer.normalize(text)

    # ========================================================
    # SEARCH KNOWLEDGE (LEGACY COMPATIBILITY)
    # ========================================================
    def search(
        self,
        query: str,
        top_k: int = 2,
        similarity_threshold: float = 0.40
    ) -> list[dict]:
        return self.vector_store.search(
            query=query,
            top_k=top_k,
            similarity_threshold=similarity_threshold
        )

    # ========================================================
    # BUILD CONTEXT FOR LLM (LEGACY COMPATIBILITY)
    # ========================================================
    def build_context(
        self,
        query: str,
        top_k: int = 2,
        similarity_threshold: float = 0.40
    ) -> str:
        results = self.search(
            query=query,
            top_k=top_k,
            similarity_threshold=similarity_threshold
        )

        if not results:
            return ""

        # Format context cực kỳ tinh gọn, không header rườm rà
        context_parts = [r["text"].strip() for r in results if r.get("text")]
        return "\n---\n".join(context_parts)