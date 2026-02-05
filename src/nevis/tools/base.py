"""Tool definitions and the @tool decorator."""

from __future__ import annotations

import asyncio
import functools
import inspect
import logging
from typing import Any, Callable, get_type_hints

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Python type -> JSON Schema type mapping
_TYPE_MAP: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


class Tool(BaseModel):
    """A callable tool that can be invoked by the agent."""

    name: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=lambda: {
        "type": "object",
        "properties": {},
    })
    fn: Callable[..., Any] | None = None
    timeout: float = 60.0

    model_config = {"arbitrary_types_allowed": True}

    async def execute(self, **kwargs: Any) -> Any:
        """Execute the tool with the given arguments."""
        if self.fn is None:
            raise RuntimeError(f"Tool '{self.name}' has no callable function")
        try:
            if asyncio.iscoroutinefunction(self.fn):
                result = await asyncio.wait_for(self.fn(**kwargs), timeout=self.timeout)
            else:
                loop = asyncio.get_event_loop()
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, functools.partial(self.fn, **kwargs)),
                    timeout=self.timeout,
                )
            return result
        except asyncio.TimeoutError:
            return {"error": f"Tool '{self.name}' timed out after {self.timeout}s"}
        except Exception as e:
            logger.error(f"Tool '{self.name}' failed: {e}")
            return {"error": f"Tool '{self.name}' failed: {str(e)}"}

    def to_schema(self) -> dict[str, Any]:
        """Return the tool as a JSON schema for LLM function calling."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


def _build_json_schema(fn: Callable[..., Any]) -> dict[str, Any]:
    """Auto-generate a JSON schema from function type hints."""
    hints = get_type_hints(fn)
    sig = inspect.signature(fn)
    properties: dict[str, Any] = {}
    required: list[str] = []

    for param_name, param in sig.parameters.items():
        if param_name in ("self", "cls"):
            continue
        param_type = hints.get(param_name, str)

        # Resolve basic types
        json_type = _TYPE_MAP.get(param_type, "string")
        prop: dict[str, Any] = {"type": json_type}

        # Use docstring-style description if available
        properties[param_name] = prop

        if param.default is inspect.Parameter.empty:
            required.append(param_name)

    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def tool(
    name: str | None = None,
    description: str = "",
    timeout: float = 60.0,
) -> Callable[..., Tool]:
    """Decorator to turn an async function into a Tool."""

    def decorator(fn: Callable[..., Any]) -> Tool:
        tool_name = name or fn.__name__
        tool_desc = description or fn.__doc__ or f"Tool: {tool_name}"
        schema = _build_json_schema(fn)

        return Tool(
            name=tool_name,
            description=tool_desc,
            parameters=schema,
            fn=fn,
            timeout=timeout,
        )

    return decorator
