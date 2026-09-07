# app/ai/rag/rag_service.py

from app.ai.rag.vector_store import VectorStore


class RAGService:

    def __init__(
        self,
        vector_store: VectorStore
    ):
        self.vector_store = vector_store

    # ========================================================
    # SEARCH KNOWLEDGE
    # ========================================================

    def search(
        self,
        query: str,
        top_k: int = 3
    ) -> list[dict]:

        results = self.vector_store.search(
            query=query,
            top_k=top_k
        )

        return results

    # ========================================================
    # BUILD CONTEXT FOR LLM
    # ========================================================

    def build_context(
            self,
            query: str,
            top_k: int = 3
        ) -> str:

            results = self.search(
                query=query,
                top_k=top_k
            )

            # print("\n========== RAG DEBUG ==========")
            # print("QUERY:", query)
            # print("RESULTS:", results)
            # print("RESULT COUNT:", len(results))
            # print("================================\n")

            if not results:
                return ""

            context_parts = []

            for index, result in enumerate(results, start=1):

                context_parts.append(
                    f"""
        [Knowledge {index}]
        Source: {result["source"]}

        {result["text"]}
        """
                )

            context = "\n".join(context_parts)

            # print("========== RAG CONTEXT ==========")
            # print(context)
            # print("=================================\n")

            return context