"""Persistent Chroma vector index.

Wraps langchain-chroma so the rest of the app doesn't touch Chroma directly,
and enforces that one collection is only ever used with one embedding model.
"""

from __future__ import annotations

import logging
from pathlib import Path

import chromadb
from langchain_chroma import Chroma
from langchain_core.embeddings import Embeddings

from app.errors import AppError
from app.rag.chunking import Chunk
from app.resilience import call_openai

logger = logging.getLogger(__name__)


class EmbeddingModelMismatchError(AppError):
    def __init__(self, collection: str, stored: str, configured: str) -> None:
        super().__init__(
            f"The vector index '{collection}' was built with embedding model "
            f"'{stored}', but OPENAI_EMBEDDING_MODEL is '{configured}'. Vectors from "
            "different models are not comparable. Either restore the original model "
            "or rebuild the index: stop the app, delete the CHROMA_PERSIST_DIRECTORY "
            "folder (default storage/vectorstore), clear the documents (delete "
            "storage/study.db), and re-upload your files.",
            status_code=500,
            code="embedding_model_mismatch",
        )


class VectorIndex:
    def __init__(
        self,
        *,
        embeddings: Embeddings,
        persist_directory: Path,
        collection_name: str,
        embedding_model_name: str,
        max_retries: int = 2,
        retry_base_delay: float = 1.0,
    ) -> None:
        self.embedding_model_name = embedding_model_name
        self.collection_name = collection_name
        self._max_retries = max_retries
        self._retry_base_delay = retry_base_delay
        persist_directory.mkdir(parents=True, exist_ok=True)
        self._store = Chroma(
            collection_name=collection_name,
            embedding_function=embeddings,
            persist_directory=str(persist_directory),
            client_settings=chromadb.config.Settings(
                anonymized_telemetry=False, is_persistent=True,
                persist_directory=str(persist_directory),
            ),
            collection_metadata={"embedding_model": embedding_model_name},
            collection_configuration={"hnsw": {"space": "cosine"}},
        )
        self._check_embedding_model()

    def _check_embedding_model(self) -> None:
        stored = (self._store._collection.metadata or {}).get("embedding_model")
        if stored is None:
            return  # collection predates metadata; nothing to compare against
        if stored != self.embedding_model_name:
            raise EmbeddingModelMismatchError(
                self.collection_name, str(stored), self.embedding_model_name
            )

    # ---- writes ----
    def add_chunks(self, chunks: list[Chunk], *, batch_size: int = 64) -> None:
        """Embed and store chunks in bounded batches (upsert by chunk id)."""
        for start in range(0, len(chunks), batch_size):
            batch = chunks[start : start + batch_size]
            call_openai(
                lambda b=batch: self._store.add_texts(
                    texts=[c.text for c in b],
                    metadatas=[c.metadata for c in b],
                    ids=[c.chunk_id for c in b],
                ),
                max_retries=self._max_retries,
                base_delay=self._retry_base_delay,
            )

    def delete_document(self, document_id: str) -> None:
        self._store.delete(where={"document_id": document_id})

    # ---- reads ----
    def count_for_document(self, document_id: str) -> int:
        found = self._store.get(where={"document_id": document_id}, include=[])
        return len(found["ids"])

    def list_chunks(self, document_ids: list[str]) -> list[tuple[str, dict]]:
        """All stored chunks (text, metadata) of the given documents, in document then reading order."""
        order = {doc_id: i for i, doc_id in enumerate(document_ids)}
        where = (
            {"document_id": document_ids[0]} if len(document_ids) == 1
            else {"document_id": {"$in": document_ids}}
        )
        found = self._store.get(where=where, include=["documents", "metadatas"])
        rows = list(zip(found["documents"], found["metadatas"]))
        rows.sort(key=lambda r: (order.get(r[1]["document_id"], 0), int(r[1].get("chunk_index", 0))))
        return [(text, dict(meta)) for text, meta in rows]

    def search(
        self, query: str, *, k: int, document_ids: list[str] | None = None
    ) -> list[tuple[str, dict, float]]:
        """Return (text, metadata, cosine_similarity) sorted best-first.

        The collection uses cosine distance, so similarity = 1 - distance.
        """
        where = None
        if document_ids:
            where = (
                {"document_id": document_ids[0]}
                if len(document_ids) == 1
                else {"document_id": {"$in": document_ids}}
            )
        results = call_openai(
            lambda: self._store.similarity_search_with_score(query, k=k, filter=where),
            max_retries=self._max_retries,
            base_delay=self._retry_base_delay,
        )
        return [(doc.page_content, dict(doc.metadata), 1.0 - float(dist)) for doc, dist in results]
