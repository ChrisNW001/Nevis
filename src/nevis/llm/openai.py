"""OpenAI GPT LLM provider."""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, AsyncIterator

from nevis.llm.base import LLMConfig, LLMProvider, LLMResponse, Message, ToolCall, UsageStats

logger = logging.getLogger(__name__)

_DEFAULT_COST = {"input": 2.50, "output": 10.0}  # GPT-4o defaults


class OpenAIConfig(LLMConfig):
    """Configuration for OpenAI provider."""

    model: str = "gpt-4o"
    api_key: str = ""
    max_tokens: int = 4096

    @classmethod
    def from_env(cls) -> OpenAIConfig:
        api_key = os.getenv("OPENAI_API_KEY", "")
        model = os.getenv("OPENAI_MODEL", "gpt-4o")
        return cls(api_key=api_key, model=model)


class OpenAIProvider(LLMProvider):
    """LLM provider using the OpenAI Chat Completions API."""

    def __init__(self, config: OpenAIConfig):
        super().__init__(config)
        self.openai_config = config
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from openai import AsyncOpenAI
            except ImportError:
                raise ImportError("Install openai: pip install openai")
            self._client = AsyncOpenAI(api_key=self.openai_config.api_key)
        return self._client

    def _format_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        formatted = []
        for msg in messages:
            d: dict[str, Any] = {"role": msg.role, "content": msg.content or ""}
            if msg.role == "assistant" and msg.tool_calls:
                d["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                    }
                    for tc in msg.tool_calls
                ]
                d["content"] = msg.content or None
            if msg.role == "tool":
                d["tool_call_id"] = msg.tool_call_id
            formatted.append(d)
        return formatted

    def _format_tools(self, tools: list[dict[str, Any]] | None) -> list[dict[str, Any]] | None:
        if not tools:
            return None
        return [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("parameters", {"type": "object", "properties": {}}),
                },
            }
            for t in tools
        ]

    async def chat(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        client = self._get_client()
        formatted = self._format_messages(messages)
        openai_tools = self._format_tools(tools)

        params: dict[str, Any] = {
            "model": self.config.model,
            "messages": formatted,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        if openai_tools:
            params["tools"] = openai_tools

        start = time.time()
        response = await client.chat.completions.create(**params)
        latency = (time.time() - start) * 1000

        choice = response.choices[0]
        tool_calls = None
        if choice.message.tool_calls:
            tool_calls = [
                ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=json.loads(tc.function.arguments),
                )
                for tc in choice.message.tool_calls
            ]

        usage_data = response.usage
        usage = UsageStats(
            input_tokens=usage_data.prompt_tokens if usage_data else 0,
            output_tokens=usage_data.completion_tokens if usage_data else 0,
            total_tokens=usage_data.total_tokens if usage_data else 0,
            cost_usd=(
                (usage_data.prompt_tokens * _DEFAULT_COST["input"]
                 + usage_data.completion_tokens * _DEFAULT_COST["output"]) / 1_000_000
                if usage_data else 0.0
            ),
        )
        self._track_usage(usage)

        return LLMResponse(
            message=Message(
                role="assistant",
                content=choice.message.content,
                tool_calls=tool_calls,
            ),
            usage=usage,
            model=response.model or self.config.model,
            finish_reason=choice.finish_reason or "",
            latency_ms=latency,
        )

    async def stream(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        client = self._get_client()
        formatted = self._format_messages(messages)
        openai_tools = self._format_tools(tools)

        params: dict[str, Any] = {
            "model": self.config.model,
            "messages": formatted,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "stream": True,
        }
        if openai_tools:
            params["tools"] = openai_tools

        response = await client.chat.completions.create(**params)
        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
