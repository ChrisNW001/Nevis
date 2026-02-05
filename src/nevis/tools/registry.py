"""Tool registry for discovering and managing tools."""

from __future__ import annotations

import logging
from typing import Any

from nevis.tools.base import Tool

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Central registry for all available tools."""

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool."""
        if tool.name in self._tools:
            logger.warning(f"Overwriting existing tool: {tool.name}")
        self._tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name}")

    def unregister(self, name: str) -> None:
        """Remove a tool from the registry."""
        self._tools.pop(name, None)

    def get(self, name: str) -> Tool | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> list[Tool]:
        """List all registered tools."""
        return list(self._tools.values())

    def get_schemas(self) -> list[dict[str, Any]]:
        """Get JSON schemas for all tools (for LLM function calling)."""
        return [t.to_schema() for t in self._tools.values()]

    async def execute(self, tool_name: str, **kwargs: Any) -> Any:
        """Execute a tool by name."""
        tool = self._tools.get(tool_name)
        if tool is None:
            return {"error": f"Unknown tool: {tool_name}"}
        return await tool.execute(**kwargs)

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools
