"""Abstract memory store interface."""

from __future__ import annotations

import abc
import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class MemoryEntry(BaseModel):
    """A single memory entry."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    memory_type: str = "generic"
    relevance_score: float = 0.0

    def to_context_string(self) -> str:
        return f"[{self.memory_type} | {self.timestamp.isoformat()}] {self.content}"


class MemoryStore(abc.ABC):
    """Abstract base class for memory stores."""

    @abc.abstractmethod
    async def store(self, entry: MemoryEntry) -> str:
        """Store a memory entry. Returns the entry ID."""

    @abc.abstractmethod
    async def retrieve(self, entry_id: str) -> MemoryEntry | None:
        """Retrieve a specific memory by ID."""

    @abc.abstractmethod
    async def search(self, query: str, limit: int = 10) -> list[MemoryEntry]:
        """Search memories by query string."""

    @abc.abstractmethod
    async def delete(self, entry_id: str) -> bool:
        """Delete a memory entry."""

    @abc.abstractmethod
    async def list_recent(self, limit: int = 20) -> list[MemoryEntry]:
        """List most recent memories."""
