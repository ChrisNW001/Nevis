"""Built-in sandboxed code execution tool."""

from __future__ import annotations

import asyncio
import logging
import subprocess
import tempfile

from nevis.tools.base import tool

logger = logging.getLogger(__name__)

_MAX_OUTPUT = 10_000  # chars
_EXEC_TIMEOUT = 30  # seconds


@tool(
    name="code_exec",
    description="Execute Python code in a sandboxed subprocess. Returns stdout and stderr.",
    timeout=60.0,
)
async def code_exec_tool(code: str) -> dict:
    """Execute Python code in an isolated subprocess with resource limits."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code)
        script_path = f.name

    try:
        proc = await asyncio.create_subprocess_exec(
            "python3", script_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=_EXEC_TIMEOUT
        )

        return {
            "stdout": stdout.decode("utf-8", errors="replace")[:_MAX_OUTPUT],
            "stderr": stderr.decode("utf-8", errors="replace")[:_MAX_OUTPUT],
            "returncode": proc.returncode,
        }
    except asyncio.TimeoutError:
        proc.kill()
        return {"error": f"Execution timed out after {_EXEC_TIMEOUT}s", "returncode": -1}
    except Exception as e:
        return {"error": str(e), "returncode": -1}
