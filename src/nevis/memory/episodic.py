"""Episodic memory -- timestamped log of past agent interactions and outcomes."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from nevis.memory.base import MemoryEntry, MemoryStore

logger = logging.getLogger(__name__)


class EpisodicMemory(MemoryStore):
    """Stores timestamped events: what happened, what worked, what failed.

    Uses a simple JSON-lines file for persistence. Swap with a database
    backend for production.
    """

    def __init__(self, storage_path: str = ".nevis/memory/episodic.jsonl"):
        self._storage_path = storage_path
        self._entries: list[MemoryEntry] = []
        self._loaded = False

    async def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        if os.path.exists(self._storage_path):
            with open(self._storage_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        self._entries.append(MemoryEntry.model_validate_json(line))
        self._loaded = True

    def _persist(self, entry: MemoryEntry) -> None:
        os.makedirs(os.path.dirname(self._storage_path) or ".", exist_ok=True)
        with open(self._storage_path, "a") as f:
            f.write(entry.model_dump_json() + "\n")

    async def store(self, entry: MemoryEntry) -> str:
        await self._ensure_loaded()
        entry.memory_type = "episodic"
        self._entries.append(entry)
        self._persist(entry)
        return entry.id

    async def store_event(
        self,
        action: str,
        outcome: str,
        success: bool,
        details: dict[str, Any] | None = None,
    ) -> str:
        """Convenience method: store an action/outcome event."""
        entry = MemoryEntry(
            content=f"Action: {action}\nOutcome: {outcome}",
            metadata={
                "action": action,
                "outcome": outcome,
                "success": success,
                **(details or {}),
            },
            memory_type="episodic",
        )
        return await self.store(entry)

    async def retrieve(self, entry_id: str) -> MemoryEntry | None:
        await self._ensure_loaded()
        for entry in self._entries:
            if entry.id == entry_id:
                return entry
        return None

    async def search(self, query: str, limit: int = 10) -> list[MemoryEntry]:
        await self._ensure_loaded()
        query_lower = query.lower()
        scored = []
        for entry in self._entries:
            content_lower = entry.content.lower()
            if query_lower in content_lower:
                score = content_lower.count(query_lower) / max(len(content_lower), 1)
                scored.append((score, entry))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [e for _, e in scored[:limit]]

    async def search_by_time(
        self,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 20,
    ) -> list[MemoryEntry]:
        await self._ensure_loaded()
        results = []
        for entry in self._entries:
            if start and entry.timestamp < start:
                continue
            if end and entry.timestamp > end:
                continue
            results.append(entry)
        return sorted(results, key=lambda e: e.timestamp, reverse=True)[:limit]

    async def search_by_success(self, success: bool, limit: int = 10) -> list[MemoryEntry]:
        await self._ensure_loaded()
        return [
            e for e in reversed(self._entries)
            if e.metadata.get("success") == success
        ][:limit]

    async def delete(self, entry_id: str) -> bool:
        await self._ensure_loaded()
        for i, entry in enumerate(self._entries):
            if entry.id == entry_id:
                self._entries.pop(i)
                return True
        return False

    async def list_recent(self, limit: int = 20) -> list[MemoryEntry]:
        await self._ensure_loaded()
        return list(reversed(self._entries[-limit:]))
