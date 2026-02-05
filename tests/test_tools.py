"""Tests for the tool system."""

import pytest
from nevis.tools.base import Tool, tool
from nevis.tools.registry import ToolRegistry


@tool(name="add", description="Add two numbers.")
async def add_tool(a: int, b: int) -> int:
    return a + b


@tool(name="greet", description="Greet someone.")
async def greet_tool(name: str) -> str:
    return f"Hello, {name}!"


class TestTool:
    async def test_tool_decorator_creates_tool(self):
        assert isinstance(add_tool, Tool)
        assert add_tool.name == "add"
        assert add_tool.description == "Add two numbers."

    async def test_tool_execute(self):
        result = await add_tool.execute(a=2, b=3)
        assert result == 5

    async def test_tool_schema(self):
        schema = add_tool.to_schema()
        assert schema["name"] == "add"
        assert "a" in schema["parameters"]["properties"]
        assert "b" in schema["parameters"]["properties"]

    async def test_tool_error_handling(self):
        @tool(name="fail", description="Always fails.")
        async def fail_tool():
            raise ValueError("boom")

        result = await fail_tool.execute()
        assert "error" in result


class TestToolRegistry:
    async def test_register_and_get(self):
        registry = ToolRegistry()
        registry.register(add_tool)
        assert registry.get("add") is add_tool
        assert len(registry) == 1

    async def test_execute_tool(self):
        registry = ToolRegistry()
        registry.register(greet_tool)
        result = await registry.execute("greet", name="World")
        assert result == "Hello, World!"

    async def test_unknown_tool(self):
        registry = ToolRegistry()
        result = await registry.execute("nonexistent")
        assert "error" in result

    async def test_get_schemas(self):
        registry = ToolRegistry()
        registry.register(add_tool)
        registry.register(greet_tool)
        schemas = registry.get_schemas()
        assert len(schemas) == 2
        names = {s["name"] for s in schemas}
        assert names == {"add", "greet"}
