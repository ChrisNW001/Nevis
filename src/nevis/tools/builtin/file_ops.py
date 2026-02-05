"""Built-in file operation tools."""

from __future__ import annotations

import os

from nevis.tools.base import tool

_MAX_READ = 100_000  # chars


@tool(name="read_file", description="Read the contents of a file at the given path.")
async def read_file_tool(path: str) -> dict:
    """Read file contents."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(_MAX_READ)
        return {"path": path, "content": content, "truncated": len(content) >= _MAX_READ}
    except Exception as e:
        return {"path": path, "error": str(e)}


@tool(name="write_file", description="Write content to a file at the given path.")
async def write_file_tool(path: str, content: str) -> dict:
    """Write content to a file."""
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return {"path": path, "bytes_written": len(content.encode("utf-8"))}
    except Exception as e:
        return {"path": path, "error": str(e)}


@tool(name="list_dir", description="List files and directories at the given path.")
async def list_dir_tool(path: str = ".") -> dict:
    """List directory contents."""
    try:
        entries = []
        for entry in sorted(os.listdir(path)):
            full = os.path.join(path, entry)
            entries.append({
                "name": entry,
                "type": "directory" if os.path.isdir(full) else "file",
                "size": os.path.getsize(full) if os.path.isfile(full) else None,
            })
        return {"path": path, "entries": entries}
    except Exception as e:
        return {"path": path, "error": str(e)}
