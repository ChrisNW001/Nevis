"""Cross-session continuity -- persist and restore agent state between sessions."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SessionNotes(BaseModel):
    """Structured notes persisted between sessions."""

    session_id: str
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    key_decisions: list[str] = Field(default_factory=list)
    open_tasks: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    user_preferences: dict[str, Any] = Field(default_factory=dict)
    project_context: str = ""
    summary: str = ""


class SessionContinuity:
    """Manages cross-session state persistence.

    Saves structured notes at the end of each session and loads relevant
    context at the start of the next session.
    """

    def __init__(self, storage_dir: str = ".nevis/sessions"):
        self._storage_dir = storage_dir
        os.makedirs(storage_dir, exist_ok=True)

    async def save_session(self, notes: SessionNotes) -> str:
        """Save session notes to disk."""
        path = os.path.join(self._storage_dir, f"{notes.session_id}.json")
        with open(path, "w") as f:
            f.write(notes.model_dump_json(indent=2))
        logger.info(f"Saved session notes: {notes.session_id}")
        return path

    async def load_session(self, session_id: str) -> SessionNotes | None:
        """Load notes from a specific session."""
        path = os.path.join(self._storage_dir, f"{session_id}.json")
        if not os.path.exists(path):
            return None
        with open(path, "r") as f:
            return SessionNotes.model_validate_json(f.read())

    async def get_recent_sessions(self, limit: int = 5) -> list[SessionNotes]:
        """Load the most recent session notes."""
        files = []
        for fname in os.listdir(self._storage_dir):
            if fname.endswith(".json"):
                path = os.path.join(self._storage_dir, fname)
                files.append((os.path.getmtime(path), path))

        files.sort(reverse=True)
        sessions = []
        for _, path in files[:limit]:
            with open(path, "r") as f:
                sessions.append(SessionNotes.model_validate_json(f.read()))
        return sessions

    async def build_context(self, limit: int = 3) -> str:
        """Build a context string from recent sessions for injection into system prompt."""
        sessions = await self.get_recent_sessions(limit)
        if not sessions:
            return ""

        parts = ["## Context from previous sessions\n"]
        for s in sessions:
            parts.append(f"### Session {s.session_id} ({s.timestamp})")
            if s.summary:
                parts.append(f"Summary: {s.summary}")
            if s.key_decisions:
                parts.append("Key decisions: " + "; ".join(s.key_decisions))
            if s.open_tasks:
                parts.append("Open tasks: " + "; ".join(s.open_tasks))
            if s.blockers:
                parts.append("Blockers: " + "; ".join(s.blockers))
            if s.user_preferences:
                parts.append(f"User preferences: {json.dumps(s.user_preferences)}")
            parts.append("")

        return "\n".join(parts)

    async def track_feedback(
        self,
        session_id: str,
        feedback_type: str,
        details: str = "",
    ) -> None:
        """Track user feedback for preference learning."""
        notes = await self.load_session(session_id)
        if notes is None:
            notes = SessionNotes(session_id=session_id)

        prefs = notes.user_preferences
        feedback_key = f"feedback_{feedback_type}"
        if feedback_key not in prefs:
            prefs[feedback_key] = []
        prefs[feedback_key].append(details)

        await self.save_session(notes)
