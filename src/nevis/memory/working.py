"""Working memory -- session-scoped scratchpad and key-value store."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class WorkingMemory(BaseModel):
    """Short-term working memory for the current session.

    Holds a scratchpad for intermediate reasoning and a key-value store
    for active variables scoped to the current session.
    """

    scratchpad: str = ""
    variables: dict[str, Any] = Field(default_factory=dict)
    task_stack: list[str] = Field(default_factory=list)

    def write_scratchpad(self, text: str) -> None:
        """Append to the scratchpad."""
        self.scratchpad += text + "\n"

    def clear_scratchpad(self) -> None:
        self.scratchpad = ""

    def set(self, key: str, value: Any) -> None:
        """Set a session variable."""
        self.variables[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Get a session variable."""
        return self.variables.get(key, default)

    def delete(self, key: str) -> None:
        self.variables.pop(key, None)

    def push_task(self, task: str) -> None:
        """Push a task onto the task stack."""
        self.task_stack.append(task)

    def pop_task(self) -> str | None:
        """Pop the current task off the stack."""
        return self.task_stack.pop() if self.task_stack else None

    def current_task(self) -> str | None:
        return self.task_stack[-1] if self.task_stack else None

    def to_context_string(self) -> str:
        """Format working memory for injection into LLM context."""
        parts = []
        if self.scratchpad:
            parts.append(f"Scratchpad:\n{self.scratchpad}")
        if self.variables:
            parts.append(f"Variables: {self.variables}")
        if self.task_stack:
            parts.append(f"Task stack: {' -> '.join(self.task_stack)}")
        return "\n".join(parts)
