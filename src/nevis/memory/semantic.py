"""Semantic memory -- vector-based fact storage and retrieval (RAG-ready)."""

from __future__ import annotations

import hashlib
import json
import logging
import os
from typing import Any

from nevis.memory.base import MemoryEntry, MemoryStore

logger = logging.getLogger(__name__)


class SemanticMemory(MemoryStore):
    """Stores facts and knowledge with vector embeddings for similarity search.

    Default backend: in-memory with simple keyword matching.
    For production: swap in ChromaDB or pgvector via the `backend` parameter.
    """

    def __init__(
        self,
        storage_path: str = ".nevis/memory/semantic.jsonl",
        embedding_fn: Any | None = None,
    ):
        self._storage_path = storage_path
        self._entries: list[MemoryEntry] = []
        self._embeddings: dict[str, list[float]] = {}
        self._embedding_fn = embedding_fn
        self._loaded = False

    async def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        if os.path.exists(self._storage_path):
            with open(self._storage_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        data = json.loads(line)
                        entry = MemoryEntry.model_validate(data["entry"])
                        self._entries.append(entry)
                        if "embedding" in data:
                            self._embeddings[entry.id] = data["embedding"]
        self._loaded = True

    def _persist(self, entry: MemoryEntry, embedding: list[float] | None = None) -> None:
        os.makedirs(os.path.dirname(self._storage_path) or ".", exist_ok=True)
        record: dict[str, Any] = {"entry": json.loads(entry.model_dump_json())}
        if embedding:
            record["embedding"] = embedding
        with open(self._storage_path, "a") as f:
            f.write(json.dumps(record) + "\n")

    async def store(self, entry: MemoryEntry) -> str:
        await self._ensure_loaded()
        entry.memory_type = "semantic"
        embedding = None
        if self._embedding_fn:
            embedding = await self._embedding_fn(entry.content)
            self._embeddings[entry.id] = embedding
        self._entries.append(entry)
        self._persist(entry, embedding)
        return entry.id

    async def store_fact(self, fact: str, source: str | None = None) -> str:
        """Convenience: store a fact with optional source attribution."""
        entry = MemoryEntry(
            content=fact,
            metadata={"source": source} if source else {},
            memory_type="semantic",
        )
        return await self.store(entry)

    async def retrieve(self, entry_id: str) -> MemoryEntry | None:
        await self._ensure_loaded()
        for entry in self._entries:
            if entry.id == entry_id:
                return entry
        return None

    async def search(self, query: str, limit: int = 10) -> list[MemoryEntry]:
        """Search by vector similarity if embeddings available, else keyword."""
        await self._ensure_loaded()

        if self._embedding_fn and self._embeddings:
            return await self._vector_search(query, limit)
        return self._keyword_search(query, limit)

    async def _vector_search(self, query: str, limit: int) -> list[MemoryEntry]:
        query_embedding = await self._embedding_fn(query)
        scored = []
        for entry in self._entries:
            if entry.id in self._embeddings:
                score = self._cosine_similarity(query_embedding, self._embeddings[entry.id])
                scored.append((score, entry))
        scored.sort(key=lambda x: x[0], reverse=True)
        results = []
        for score, entry in scored[:limit]:
            entry.relevance_score = score
            results.append(entry)
        return results

    def _keyword_search(self, query: str, limit: int) -> list[MemoryEntry]:
        query_lower = query.lower()
        query_terms = set(query_lower.split())
        scored = []
        for entry in self._entries:
            content_lower = entry.content.lower()
            # Simple BM25-like scoring: term frequency
            score = sum(1 for term in query_terms if term in content_lower)
            if score > 0:
                scored.append((score, entry))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [e for _, e in scored[:limit]]

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    async def delete(self, entry_id: str) -> bool:
        await self._ensure_loaded()
        for i, entry in enumerate(self._entries):
            if entry.id == entry_id:
                self._entries.pop(i)
                self._embeddings.pop(entry_id, None)
                return True
        return False

    async def list_recent(self, limit: int = 20) -> list[MemoryEntry]:
        await self._ensure_loaded()
        return list(reversed(self._entries[-limit:]))

    async def ingest_document(self, text: str, chunk_size: int = 500, source: str | None = None) -> list[str]:
        """Chunk and ingest a document into semantic memory."""
        chunks = [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]
        ids = []
        for i, chunk in enumerate(chunks):
            entry_id = await self.store_fact(
                fact=chunk.strip(),
                source=f"{source}#chunk{i}" if source else None,
            )
            ids.append(entry_id)
        return ids
