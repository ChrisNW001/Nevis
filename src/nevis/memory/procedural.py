"""Procedural memory -- learned skills and reusable action sequences."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from pydantic import BaseModel, Field

from nevis.memory.base import MemoryEntry, MemoryStore

logger = logging.getLogger(__name__)


class Skill(BaseModel):
    """A named, reusable action sequence the agent has learned."""

    name: str
    description: str
    steps: list[dict[str, Any]]  # ordered tool calls + arguments
    success_count: int = 0
    failure_count: int = 0
    version: int = 1
    tags: list[str] = Field(default_factory=list)

    @property
    def success_rate(self) -> float:
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.0


class ProceduralMemory(MemoryStore):
    """Stores learned skills -- effective tool-call sequences that can be replayed.

    Skills are named action sequences with success tracking and versioning.
    """

    def __init__(self, storage_path: str = ".nevis/memory/procedural.jsonl"):
        self._storage_path = storage_path
        self._entries: list[MemoryEntry] = []
        self._skills: dict[str, Skill] = {}
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
                        if "skill" in data:
                            skill = Skill.model_validate(data["skill"])
                            self._skills[skill.name] = skill
                        if "entry" in data:
                            self._entries.append(MemoryEntry.model_validate(data["entry"]))
        self._loaded = True

    def _persist_skill(self, skill: Skill) -> None:
        os.makedirs(os.path.dirname(self._storage_path) or ".", exist_ok=True)
        with open(self._storage_path, "a") as f:
            f.write(json.dumps({"skill": json.loads(skill.model_dump_json())}) + "\n")

    async def save_skill(self, skill: Skill) -> str:
        """Save or update a skill."""
        await self._ensure_loaded()
        self._skills[skill.name] = skill
        self._persist_skill(skill)

        entry = MemoryEntry(
            content=f"Skill '{skill.name}': {skill.description}",
            metadata={"skill_name": skill.name, "version": skill.version},
            memory_type="procedural",
        )
        self._entries.append(entry)
        return skill.name

    async def get_skill(self, name: str) -> Skill | None:
        await self._ensure_loaded()
        return self._skills.get(name)

    async def list_skills(self) -> list[Skill]:
        await self._ensure_loaded()
        return list(self._skills.values())

    async def record_outcome(self, skill_name: str, success: bool) -> None:
        """Record whether a skill execution succeeded or failed."""
        await self._ensure_loaded()
        skill = self._skills.get(skill_name)
        if skill:
            if success:
                skill.success_count += 1
            else:
                skill.failure_count += 1

    async def find_skill(self, query: str) -> list[Skill]:
        """Find skills matching a query by name, description, or tags."""
        await self._ensure_loaded()
        query_lower = query.lower()
        matches = []
        for skill in self._skills.values():
            if (
                query_lower in skill.name.lower()
                or query_lower in skill.description.lower()
                or any(query_lower in tag.lower() for tag in skill.tags)
            ):
                matches.append(skill)
        return sorted(matches, key=lambda s: s.success_rate, reverse=True)

    # MemoryStore interface
    async def store(self, entry: MemoryEntry) -> str:
        await self._ensure_loaded()
        entry.memory_type = "procedural"
        self._entries.append(entry)
        return entry.id

    async def retrieve(self, entry_id: str) -> MemoryEntry | None:
        await self._ensure_loaded()
        for entry in self._entries:
            if entry.id == entry_id:
                return entry
        return None

    async def search(self, query: str, limit: int = 10) -> list[MemoryEntry]:
        await self._ensure_loaded()
        query_lower = query.lower()
        return [
            e for e in self._entries
            if query_lower in e.content.lower()
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
