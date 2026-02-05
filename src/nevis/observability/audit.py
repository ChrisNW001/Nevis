"""Structured audit logging -- every agent action as a structured record."""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class AuditEntry(BaseModel):
    """A structured audit log entry."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: float = Field(default_factory=time.time)
    agent_id: str = ""
    conversation_id: str = ""
    action: str  # e.g. "llm_call", "tool_call", "agent_spawn"
    tool: str = ""
    input_data: dict[str, Any] = Field(default_factory=dict)
    output_data: dict[str, Any] = Field(default_factory=dict)
    duration_ms: float = 0.0
    trigger: str = ""  # e.g. "user_request", "agent_loop", "planner"
    success: bool = True
    error: str = ""


class AuditLogger:
    """Structured audit logger that writes to file and/or external sinks."""

    def __init__(self, log_path: str = ".nevis/audit/audit.jsonl"):
        self._log_path = log_path
        self._entries: list[AuditEntry] = []

    def log(self, entry: AuditEntry) -> None:
        """Log an audit entry."""
        self._entries.append(entry)
        self._persist(entry)
        logger.debug(f"[AUDIT] {entry.action} | agent={entry.agent_id} | "
                      f"tool={entry.tool} | {entry.duration_ms:.1f}ms")

    def log_tool_call(
        self,
        tool_name: str,
        input_data: dict[str, Any],
        output_data: dict[str, Any],
        duration_ms: float,
        agent_id: str = "",
        conversation_id: str = "",
        success: bool = True,
        error: str = "",
    ) -> AuditEntry:
        """Convenience: log a tool call."""
        entry = AuditEntry(
            agent_id=agent_id,
            conversation_id=conversation_id,
            action="tool_call",
            tool=tool_name,
            input_data=input_data,
            output_data=output_data,
            duration_ms=duration_ms,
            trigger="agent_loop",
            success=success,
            error=error,
        )
        self.log(entry)
        return entry

    def log_llm_call(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        duration_ms: float,
        cost_usd: float = 0.0,
        agent_id: str = "",
        conversation_id: str = "",
    ) -> AuditEntry:
        """Convenience: log an LLM call."""
        entry = AuditEntry(
            agent_id=agent_id,
            conversation_id=conversation_id,
            action="llm_call",
            tool=model,
            input_data={"input_tokens": input_tokens},
            output_data={"output_tokens": output_tokens, "cost_usd": cost_usd},
            duration_ms=duration_ms,
            trigger="agent_loop",
        )
        self.log(entry)
        return entry

    def _persist(self, entry: AuditEntry) -> None:
        try:
            os.makedirs(os.path.dirname(self._log_path) or ".", exist_ok=True)
            with open(self._log_path, "a") as f:
                f.write(entry.model_dump_json() + "\n")
        except Exception as e:
            logger.warning(f"Failed to persist audit entry: {e}")

    def get_entries(
        self,
        agent_id: str | None = None,
        action: str | None = None,
        limit: int = 100,
    ) -> list[AuditEntry]:
        entries = self._entries
        if agent_id:
            entries = [e for e in entries if e.agent_id == agent_id]
        if action:
            entries = [e for e in entries if e.action == action]
        return entries[-limit:]

    def summary(self) -> dict[str, Any]:
        """Get a summary of audit activity."""
        total = len(self._entries)
        actions = {}
        total_cost = 0.0
        for e in self._entries:
            actions[e.action] = actions.get(e.action, 0) + 1
            total_cost += e.output_data.get("cost_usd", 0.0)
        return {
            "total_entries": total,
            "actions": actions,
            "total_cost_usd": round(total_cost, 6),
        }
