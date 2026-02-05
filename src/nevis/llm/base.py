"""Abstract LLM provider interface."""

from __future__ import annotations

import abc
import time
import uuid
from typing import Any, AsyncIterator

from pydantic import BaseModel, Field


class Message(BaseModel):
    """A single message in a conversation."""

    role: str  # system, user, assistant, tool
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None
    name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"role": self.role}
        if self.content is not None:
            d["content"] = self.content
        if self.tool_calls:
            d["tool_calls"] = [tc.model_dump() for tc in self.tool_calls]
        if self.tool_call_id is not None:
            d["tool_call_id"] = self.tool_call_id
        if self.name is not None:
            d["name"] = self.name
        return d


class ToolCall(BaseModel):
    """A tool call requested by the LLM."""

    id: str = Field(default_factory=lambda: f"call_{uuid.uuid4().hex[:12]}")
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class UsageStats(BaseModel):
    """Token usage statistics for an LLM call."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0


class LLMResponse(BaseModel):
    """Response from an LLM provider."""

    message: Message
    usage: UsageStats = Field(default_factory=UsageStats)
    model: str = ""
    finish_reason: str = ""
    latency_ms: float = 0.0


class LLMConfig(BaseModel):
    """Base configuration for LLM providers."""

    model: str
    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: float = 1.0
    timeout: float = 120.0


class LLMProvider(abc.ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, config: LLMConfig):
        self.config = config
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._total_cost_usd = 0.0
        self._call_count = 0

    @abc.abstractmethod
    async def chat(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Send messages and get a response."""

    @abc.abstractmethod
    async def stream(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Stream a response token by token."""

    def _track_usage(self, usage: UsageStats) -> None:
        self._total_input_tokens += usage.input_tokens
        self._total_output_tokens += usage.output_tokens
        self._total_cost_usd += usage.cost_usd
        self._call_count += 1

    def get_usage_summary(self) -> dict[str, Any]:
        return {
            "total_input_tokens": self._total_input_tokens,
            "total_output_tokens": self._total_output_tokens,
            "total_cost_usd": round(self._total_cost_usd, 6),
            "call_count": self._call_count,
        }

    @staticmethod
    def _now_ms() -> float:
        return time.time() * 1000
