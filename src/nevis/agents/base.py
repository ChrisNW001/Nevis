"""Base agent definition for the multi-agent system."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from pydantic import BaseModel, Field

from nevis.core.agent_loop import AgentLoop
from nevis.core.conversation import Conversation
from nevis.llm.base import LLMProvider
from nevis.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class AgentConfig(BaseModel):
    """Configuration for a specialized agent."""

    name: str
    role: str  # e.g. "researcher", "coder", "reviewer"
    system_prompt: str = ""
    allowed_tools: list[str] = Field(default_factory=list)
    max_iterations: int = 15
    timeout: float = 300.0  # seconds


class AgentResult(BaseModel):
    """Result from an agent execution."""

    agent_name: str
    success: bool
    output: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class BaseAgent:
    """A specialized agent with a role, tools, and system prompt."""

    def __init__(
        self,
        config: AgentConfig,
        llm: LLMProvider,
        tools: ToolRegistry,
    ):
        self.id = uuid.uuid4().hex[:8]
        self.config = config
        self.llm = llm
        self.conversation = Conversation()

        # Filter tools to only those allowed for this agent
        self.tools = ToolRegistry()
        if config.allowed_tools:
            for tool in tools.list_tools():
                if tool.name in config.allowed_tools:
                    self.tools.register(tool)
        else:
            # No restrictions: grant all tools
            for tool in tools.list_tools():
                self.tools.register(tool)

        system = config.system_prompt or f"You are {config.name}, a {config.role} agent."
        self._loop = AgentLoop(
            llm=llm,
            tools=self.tools,
            system_prompt=system,
            max_iterations=config.max_iterations,
        )

    async def run(self, task: str) -> AgentResult:
        """Execute a task and return the result."""
        logger.info(f"Agent '{self.config.name}' starting task: {task[:100]}")
        try:
            output = await self._loop.run(task, self.conversation)
            return AgentResult(
                agent_name=self.config.name,
                success=True,
                output=output,
            )
        except Exception as e:
            logger.error(f"Agent '{self.config.name}' failed: {e}")
            return AgentResult(
                agent_name=self.config.name,
                success=False,
                output=str(e),
                metadata={"error_type": type(e).__name__},
            )
