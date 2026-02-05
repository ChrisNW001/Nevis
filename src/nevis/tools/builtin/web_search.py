"""Built-in web search tool."""

from __future__ import annotations

import logging

import httpx

from nevis.tools.base import tool

logger = logging.getLogger(__name__)


@tool(name="web_search", description="Search the web for information. Returns a list of results.")
async def web_search_tool(query: str, num_results: int = 5) -> dict:
    """Search the web using an HTTP-based search API."""
    # Uses a simple HTTP GET; swap the URL for any search API backend
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                "https://api.duckduckgo.com/",
                params={"q": query, "format": "json", "no_redirect": 1},
            )
            response.raise_for_status()
            data = response.json()

        results = []
        for item in data.get("RelatedTopics", [])[:num_results]:
            if "Text" in item:
                results.append({
                    "text": item["Text"],
                    "url": item.get("FirstURL", ""),
                })

        return {"query": query, "results": results}
    except Exception as e:
        logger.error(f"Web search failed: {e}")
        return {"query": query, "results": [], "error": str(e)}
