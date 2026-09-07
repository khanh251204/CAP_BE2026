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

        self.embedding_model = SentenceTransformer(
            "BAAI/bge-m3"
        )

        print("Embedding model loaded.")

        # ====================================================
        # CHROMA
        # ====================================================

        self.client = chromadb.PersistentClient(
            path=persist_path
        )

        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={
                "hnsw:space": "cosine"
            }
        )

        print(
            f"Vector store contains "
            f"{self.collection.count()} chunks."
        )

        # ====================================================
        # AUTO INGEST IF EMPTY
        # ====================================================

        if self.collection.count() == 0:

            print("Vector store is empty.")
            print("Starting knowledge ingestion...")

            self.ingest()

        else:

            print(
                "Knowledge already exists. "
                "Skip ingestion."
            )

    # ========================================================
    # LOAD MARKDOWN
    # ========================================================

    def load_documents(self) -> list[dict[str, Any]]:

        documents = []

        for file_path in self.knowledge_path.rglob("*.md"):

            text = file_path.read_text(
                encoding="utf-8"
            )

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
        chunk_size: int = 1000,
        overlap: int = 200
    ) -> list[str]:

        chunks = []

        start = 0

        while start < len(text):

            end = start + chunk_size

            chunk = text[start:end].strip()

            if chunk:
                chunks.append(chunk)

            start += chunk_size - overlap

        return chunks

    # ========================================================
    # INGEST KNOWLEDGE
    # ========================================================

    def ingest(self):

        documents = self.load_documents()

        if not documents:

            print(
                "Không tìm thấy file knowledge."
            )

            return

        ids = []
        texts = []
        metadatas = []

        for document in documents:

            chunks = self.chunk_text(
                document["text"]
            )

            source = document["source"]

            for index, chunk in enumerate(chunks):

                # Dùng path tương đối để ID ổn định
                relative_source = str(
                    Path(source).relative_to(
                        self.knowledge_path
                    )
                )

                chunk_id = (
                    f"{relative_source}_{index}"
                )

                ids.append(chunk_id)

                texts.append(chunk)

                metadatas.append({
                    "source": relative_source,
                    "chunk_index": index
                })

        if not texts:

            print(
                "Không có chunk nào để ingest."
            )

            return

        # ====================================================
        # EMBEDDING
        # ====================================================

        print(
            f"Creating embeddings for "
            f"{len(texts)} chunks..."
        )

        embeddings = self.embedding_model.encode(
            texts,
            normalize_embeddings=True
        )

        embeddings = embeddings.tolist()

        # ====================================================
        # SAVE CHROMA
        # ====================================================

        self.collection.upsert(
            ids=ids,
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas
        )

        print(
            f"Đã ingest {len(texts)} chunks."
        )

    # ========================================================
    # SEARCH
    # ========================================================

    def search(
        self,
        query: str,
        top_k: int = 3
    ) -> list[dict]:

        if not query or not query.strip():

            return []

        # ====================================================
        # CHECK VECTOR STORE
        # ====================================================

        if self.collection.count() == 0:

            print(
                "Vector store is empty."
            )

            return []

        # ====================================================
        # EMBEDDING QUERY
        # ====================================================

        query_embedding = self.embedding_model.encode(
            query,
            normalize_embeddings=True
        )

        query_embedding = query_embedding.tolist()

        # ====================================================
        # VECTOR SEARCH
        # ====================================================

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=min(
                top_k,
                self.collection.count()
            ),
            include=[
                "documents",
                "metadatas",
                "distances"
            ]
        )

        documents = results.get(
            "documents",
            [[]]
        )[0]

        metadatas = results.get(
            "metadatas",
            [[]]
        )[0]

        distances = results.get(
            "distances",
            [[]]
        )[0]

        output = []

        for document, metadata, distance in zip(
            documents,
            metadatas,
            distances
        ):

            output.append({
                "text": document,
                "source": metadata.get("source"),
                "chunk_index": metadata.get(
                    "chunk_index"
                ),
                "score": 1 - distance
            })

        return output

    # ========================================================
    # COUNT
    # ========================================================

    def count(self) -> int:

        return self.collection.count()