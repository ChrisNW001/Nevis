"""Anthropic Claude LLM provider."""

from __future__ import annotations

import logging
import os
import time
from typing import Any, AsyncIterator

from pydantic import BaseModel

from nevis.llm.base import LLMConfig, LLMProvider, LLMResponse, Message, ToolCall, UsageStats

logger = logging.getLogger(__name__)

# Cost per million tokens (Claude 3.5 Sonnet defaults)
_DEFAULT_COST = {"input": 3.0, "output": 15.0}


class AnthropicConfig(LLMConfig):
    """Configuration for Anthropic provider."""

    model: str = "claude-sonnet-4-20250514"
    api_key: str = ""
    max_tokens: int = 8192

    @classmethod
    def from_env(cls) -> AnthropicConfig:
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
        return cls(api_key=api_key, model=model)


class AnthropicProvider(LLMProvider):
    """LLM provider using the Anthropic Messages API."""

    def __init__(self, config: AnthropicConfig):
        super().__init__(config)
        self.anthropic_config = config
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from anthropic import AsyncAnthropic
            except ImportError:
                raise ImportError("Install anthropic: pip install anthropic")
            self._client = AsyncAnthropic(api_key=self.anthropic_config.api_key)
        return self._client

    def _format_messages(
        self, messages: list[Message]
    ) -> tuple[str | None, list[dict[str, Any]]]:
        """Split system prompt from messages and format for Anthropic API."""
        system_prompt = None
        formatted = []

        for msg in messages:
            if msg.role == "system":
                system_prompt = msg.content
                continue

            if msg.role == "tool":
                formatted.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": msg.tool_call_id,
                            "content": msg.content or "",
                        }
                    ],
                })
                continue

            if msg.role == "assistant" and msg.tool_calls:
                content: list[dict[str, Any]] = []
                if msg.content:
                    content.append({"type": "text", "text": msg.content})
                for tc in msg.tool_calls:
                    content.append({
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.name,
                        "input": tc.arguments,
                    })
                formatted.append({"role": "assistant", "content": content})
                continue

            formatted.append({"role": msg.role, "content": msg.content or ""})

        return system_prompt, formatted

    def _format_tools(self, tools: list[dict[str, Any]] | None) -> list[dict[str, Any]] | None:
        """Format tools for Anthropic's tool_use API."""
        if not tools:
            return None
        anthropic_tools = []
        for tool in tools:
            anthropic_tools.append({
                "name": tool["name"],
                "description": tool.get("description", ""),
                "input_schema": tool.get("parameters", {"type": "object", "properties": {}}),
            })
        return anthropic_tools

    async def chat(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        client = self._get_client()
        system_prompt, formatted = self._format_messages(messages)
        anthropic_tools = self._format_tools(tools)

        params: dict[str, Any] = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "messages": formatted,
        }
        if system_prompt:
            params["system"] = system_prompt
        if anthropic_tools:
            params["tools"] = anthropic_tools

        start = time.time()
        response = await client.messages.create(**params)
        latency = (time.time() - start) * 1000

        # Parse response
        content_text = ""
        tool_calls = []
        for block in response.content:
            if block.type == "text":
                content_text += block.text
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(
                    id=block.id,
                    name=block.name,
                    arguments=block.input,
                ))

        usage = UsageStats(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            total_tokens=response.usage.input_tokens + response.usage.output_tokens,
            cost_usd=(
                response.usage.input_tokens * _DEFAULT_COST["input"]
                + response.usage.output_tokens * _DEFAULT_COST["output"]
            ) / 1_000_000,
        )
        self._track_usage(usage)

        return LLMResponse(
            message=Message(
                role="assistant",
                content=content_text or None,
                tool_calls=tool_calls or None,
            ),
            usage=usage,
            model=response.model,
            finish_reason=response.stop_reason or "",
            latency_ms=latency,
        )

    async def stream(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        client = self._get_client()
        system_prompt, formatted = self._format_messages(messages)
        anthropic_tools = self._format_tools(tools)

        params: dict[str, Any] = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "messages": formatted,
        }
        if system_prompt:
            params["system"] = system_prompt
        if anthropic_tools:
            params["tools"] = anthropic_tools

        async with client.messages.stream(**params) as stream:
            async for text in stream.text_stream:
                yield text
