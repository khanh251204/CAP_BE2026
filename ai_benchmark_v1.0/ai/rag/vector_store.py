# app/ai/rag/vector_store.py

from pathlib import Path
from typing import Any

import chromadb
from sentence_transformers import SentenceTransformer


class VectorStore:

    def __init__(
        self,
        knowledge_path: str = "app/ai/rag/knowledge",
        collection_name: str = "business_knowledge",
        persist_path: str = "app/ai/rag/chroma_db"
    ):
        self.knowledge_path = Path(knowledge_path)

        # ====================================================
        # EMBEDDING MODEL
        # ====================================================
        print("Loading embedding model...")
        self.embedding_model = SentenceTransformer("BAAI/bge-m3")
        print("Embedding model loaded.")

        # ====================================================
        # CHROMA
        # ====================================================
        self.client = chromadb.PersistentClient(path=persist_path)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )

        print(f"Vector store contains {self.collection.count()} chunks.")

        # ====================================================
        # AUTO INGEST IF EMPTY
        # ====================================================
        if self.collection.count() == 0:
            print("Vector store is empty. Starting knowledge ingestion...")
            self.ingest()
        else:
            print("Knowledge already exists. Skip ingestion.")

    # ========================================================
    # LOAD MARKDOWN
    # ========================================================
    def load_documents(self) -> list[dict[str, Any]]:
        documents = []
        for file_path in self.knowledge_path.rglob("*.md"):
            text = file_path.read_text(encoding="utf-8")
            if not text.strip():
                continue
            documents.append({
                "text": text,
                "source": str(file_path)
            })
        return documents

    # ========================================================
    # CHUNK
    # ========================================================
    def chunk_text(
        self,
        text: str,
        chunk_size: int = 600,
        overlap: int = 50
    ) -> list[str]:
        # Ưu tiên tách theo dấu phân tách chunk rõ ràng '---' nếu có
        if "\n---\n" in text:
            raw_parts = [p.strip() for p in text.split("\n---\n") if p.strip()]
            chunks = []
            for part in raw_parts:
                if len(part) <= chunk_size:
                    chunks.append(part)
                else:
                    subparts = [sp.strip() for sp in part.split("\n\n") if sp.strip()]
                    chunks.extend(subparts)
            return chunks

        # Tách theo section markdown hoặc đoạn văn
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        chunks = []
        current_chunk = ""
        for p in paragraphs:
            if not current_chunk:
                current_chunk = p
            elif len(current_chunk) + len(p) + 2 <= chunk_size:
                current_chunk += "\n\n" + p
            else:
                chunks.append(current_chunk)
                current_chunk = p
        if current_chunk:
            chunks.append(current_chunk)
        return chunks

    # ========================================================
    # REINGEST
    # ========================================================
    def reingest(self):
        """Xóa sạch collection và ingest lại từ đầu với tài liệu mới nhất."""
        existing = self.collection.get()
        if existing and existing.get("ids"):
            self.collection.delete(ids=existing["ids"])
            print(f"[*] Da xoa {len(existing['ids'])} chunks cu.")
        self.ingest()

    # ========================================================
    # INGEST KNOWLEDGE
    # ========================================================
    def ingest(self):
        documents = self.load_documents()
        if not documents:
            print("Không tìm thấy file knowledge.")
            return

        ids = []
        texts = []
        metadatas = []

        for document in documents:
            chunks = self.chunk_text(document["text"])
            source = document["source"]

            for index, chunk in enumerate(chunks):
                relative_source = str(
                    Path(source).relative_to(self.knowledge_path)
                )
                chunk_id = f"{relative_source}_{index}"
                ids.append(chunk_id)
                texts.append(chunk)
                metadatas.append({
                    "source": relative_source,
                    "chunk_index": index
                })

        if not texts:
            print("Không có chunk nào để ingest.")
            return

        print(f"Creating embeddings for {len(texts)} chunks...")
        embeddings = self.embedding_model.encode(
            texts,
            normalize_embeddings=True
        ).tolist()

        self.collection.upsert(
            ids=ids,
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas
        )
        print(f"[*] Da ingest {len(texts)} chunks thanh cong.")

    # ========================================================
    # SEARCH
    # ========================================================
    def search(
        self,
        query: str,
        top_k: int = 2,
        similarity_threshold: float = 0.40
    ) -> list[dict]:
        if not query or not query.strip():
            return []

        if self.collection.count() == 0:
            return []

        query_embedding = self.embedding_model.encode(
            query,
            normalize_embeddings=True
        ).tolist()

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, self.collection.count()),
            include=["documents", "metadatas", "distances"]
        )

        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        output = []
        for document, metadata, distance in zip(
            documents, metadatas, distances
        ):
            score = 1 - distance
            # Chỉ lấy các chunk vượt qua ngưỡng tin cậy tương đồng
            if score < similarity_threshold:
                continue

            output.append({
                "text": document,
                "source": metadata.get("source"),
                "chunk_index": metadata.get("chunk_index"),
                "score": score
            })

        return output

    # ========================================================
    # COUNT
    # ========================================================
    def count(self) -> int:
        return self.collection.count()