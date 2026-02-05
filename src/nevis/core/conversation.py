"""Conversation management for Nevis agent."""

from __future__ import annotations

import json
import uuid
from typing import Any

from pydantic import BaseModel, Field

from nevis.llm.base import Message


class Conversation(BaseModel):
    """A conversation holding a list of typed messages."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    messages: list[Message] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    scratchpad: str = ""

    def add_system(self, content: str) -> None:
        self.messages.append(Message(role="system", content=content))

    def add_user(self, content: str) -> None:
        self.messages.append(Message(role="user", content=content))

    def add_assistant(self, message: Message) -> None:
        self.messages.append(message)

    def add_tool_result(self, tool_call_id: str, content: str, name: str | None = None) -> None:
        self.messages.append(Message(
            role="tool",
            content=content,
            tool_call_id=tool_call_id,
            name=name,
        ))

    def get_messages(self) -> list[Message]:
        return list(self.messages)

    def fork(self) -> Conversation:
        """Create a branch of this conversation for parallel exploration."""
        return Conversation(
            messages=[m.model_copy() for m in self.messages],
            metadata={**self.metadata, "forked_from": self.id},
            scratchpad=self.scratchpad,
        )

    def to_json(self) -> str:
        return self.model_dump_json(indent=2)

    @classmethod
    def from_json(cls, data: str) -> Conversation:
        return cls.model_validate_json(data)

    def token_estimate(self) -> int:
        """Rough token estimate (4 chars per token heuristic)."""
        total_chars = sum(len(m.content or "") for m in self.messages)
        return total_chars // 4

    def compact(self, summary: str, keep_recent: int = 5) -> None:
        """Compact conversation by replacing old messages with a summary.

        Keeps the system message(s) and the N most recent messages.
        """
        system_msgs = [m for m in self.messages if m.role == "system"]
        recent = self.messages[-keep_recent:] if len(self.messages) > keep_recent else self.messages

        self.messages = (
            system_msgs
            + [Message(role="user", content=f"[Previous conversation summary]\n{summary}")]
            + [Message(role="assistant", content="Understood. I have the context from our previous conversation.")]
            + recent
        )
