"""ReAct agent loop -- the core reasoning cycle."""

from __future__ import annotations

import json
import logging
from typing import Any

from nevis.core.conversation import Conversation
from nevis.llm.base import LLMProvider, LLMResponse
from nevis.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

_DEFAULT_MAX_ITERATIONS = 25
_CONTEXT_COMPACT_THRESHOLD = 80_000  # ~80k tokens rough


class AgentLoop:
    """ReAct-style agent loop: Think -> Act -> Observe -> repeat."""

    def __init__(
        self,
        llm: LLMProvider,
        tools: ToolRegistry,
        system_prompt: str = "You are Nevis, a helpful AI assistant.",
        max_iterations: int = _DEFAULT_MAX_ITERATIONS,
    ):
        self.llm = llm
        self.tools = tools
        self.system_prompt = system_prompt
        self.max_iterations = max_iterations

    async def run(self, user_input: str, conversation: Conversation | None = None) -> str:
        """Run the full ReAct loop for a user message. Returns the final text answer."""
        if conversation is None:
            conversation = Conversation()
            conversation.add_system(self.system_prompt)

        conversation.add_user(user_input)
        tool_schemas = self.tools.get_schemas()

        for iteration in range(self.max_iterations):
            logger.info(f"Agent loop iteration {iteration + 1}/{self.max_iterations}")

            # THINK: send conversation to LLM
            response: LLMResponse = await self.llm.chat(
                messages=conversation.get_messages(),
                tools=tool_schemas if tool_schemas else None,
            )

            assistant_msg = response.message
            conversation.add_assistant(assistant_msg)

            # CHECK: if no tool calls, we have a final answer
            if not assistant_msg.tool_calls:
                logger.info("Agent produced final answer")
                return assistant_msg.content or ""

            # ACT + OBSERVE: execute each tool call and feed results back
            for tc in assistant_msg.tool_calls:
                logger.info(f"Executing tool: {tc.name}({tc.arguments})")
                result = await self.tools.execute(tc.name, **tc.arguments)
                result_str = json.dumps(result) if not isinstance(result, str) else result
                conversation.add_tool_result(
                    tool_call_id=tc.id,
                    content=result_str,
                    name=tc.name,
                )

            # Context management: compact if too large
            if conversation.token_estimate() > _CONTEXT_COMPACT_THRESHOLD:
                logger.info("Compacting conversation context")
                summary = await self._summarize(conversation)
                conversation.compact(summary)

        logger.warning("Agent loop hit max iterations")
        return conversation.messages[-1].content or "[Max iterations reached]"

    async def _summarize(self, conversation: Conversation) -> str:
        """Ask the LLM to summarize the conversation so far."""
        summary_conv = Conversation()
        summary_conv.add_system("Summarize the following conversation concisely. "
                                "Preserve key decisions, facts, and unresolved items.")
        content_parts = []
        for m in conversation.messages:
            if m.role != "system":
                content_parts.append(f"{m.role}: {m.content or '[tool call]'}")
        summary_conv.add_user("\n".join(content_parts[-30:]))

        resp = await self.llm.chat(summary_conv.get_messages())
        return resp.message.content or ""

    async def run_streaming(self, user_input: str, conversation: Conversation | None = None):
        """Run a single LLM turn with streaming (no tool loop, for simple responses)."""
        if conversation is None:
            conversation = Conversation()
            conversation.add_system(self.system_prompt)

        conversation.add_user(user_input)

        async for token in self.llm.stream(conversation.get_messages()):
            yield token
