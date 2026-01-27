"""Notion integration for Nevis assistant."""

import logging
import os
from typing import Any

from notion_client import AsyncClient
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class NotionConfig(BaseModel):
    """Configuration for Notion integration."""

    token: str
    default_database_id: str | None = None


class NotionIntegration:
    """Integration with Notion API for reading and writing data."""

    def __init__(self, config: NotionConfig):
        self.config = config
        self.client = AsyncClient(auth=config.token)
        self._initialized = False

    @classmethod
    def from_env(cls) -> "NotionIntegration":
        """Create integration from environment variables."""
        token = os.getenv("NOTION_TOKEN")
        if not token:
            raise ValueError("NOTION_TOKEN environment variable is required")

        return cls(
            config=NotionConfig(
                token=token,
                default_database_id=os.getenv("NOTION_DEFAULT_DATABASE_ID"),
            )
        )

    async def initialize(self):
        """Initialize the Notion connection."""
        logger.info("Initializing Notion integration...")
        # Verify connection by fetching user info
        try:
            user = await self.client.users.me()
            logger.info(f"Connected to Notion as: {user.get('name', 'Unknown')}")
            self._initialized = True
        except Exception as e:
            logger.error(f"Failed to connect to Notion: {e}")
            raise

    async def shutdown(self):
        """Clean up Notion connection."""
        logger.info("Shutting down Notion integration")
        self._initialized = False

    # Database operations

    async def query_database(
        self,
        database_id: str | None = None,
        filter: dict | None = None,
        sorts: list | None = None,
        page_size: int = 100,
    ) -> list[dict]:
        """Query a Notion database."""
        db_id = database_id or self.config.default_database_id
        if not db_id:
            raise ValueError("No database_id provided and no default configured")

        results = []
        query_params: dict[str, Any] = {"database_id": db_id, "page_size": page_size}

        if filter:
            query_params["filter"] = filter
        if sorts:
            query_params["sorts"] = sorts

        response = await self.client.databases.query(**query_params)
        results.extend(response.get("results", []))

        # Handle pagination
        while response.get("has_more"):
            query_params["start_cursor"] = response["next_cursor"]
            response = await self.client.databases.query(**query_params)
            results.extend(response.get("results", []))

        return results

    async def get_database(self, database_id: str | None = None) -> dict:
        """Get database metadata."""
        db_id = database_id or self.config.default_database_id
        if not db_id:
            raise ValueError("No database_id provided and no default configured")

        return await self.client.databases.retrieve(database_id=db_id)

    # Page operations

    async def get_page(self, page_id: str) -> dict:
        """Get a page by ID."""
        return await self.client.pages.retrieve(page_id=page_id)

    async def create_page(
        self,
        parent: dict,
        properties: dict,
        children: list | None = None,
    ) -> dict:
        """Create a new page."""
        params: dict[str, Any] = {
            "parent": parent,
            "properties": properties,
        }
        if children:
            params["children"] = children

        return await self.client.pages.create(**params)

    async def update_page(self, page_id: str, properties: dict) -> dict:
        """Update a page's properties."""
        return await self.client.pages.update(page_id=page_id, properties=properties)

    # Block operations

    async def get_block_children(self, block_id: str) -> list[dict]:
        """Get children blocks of a block/page."""
        results = []
        response = await self.client.blocks.children.list(block_id=block_id)
        results.extend(response.get("results", []))

        while response.get("has_more"):
            response = await self.client.blocks.children.list(
                block_id=block_id, start_cursor=response["next_cursor"]
            )
            results.extend(response.get("results", []))

        return results

    async def append_blocks(self, block_id: str, children: list[dict]) -> dict:
        """Append children blocks to a block/page."""
        return await self.client.blocks.children.append(
            block_id=block_id, children=children
        )

    # Search

    async def search(
        self,
        query: str,
        filter: dict | None = None,
        sort: dict | None = None,
        page_size: int = 100,
    ) -> list[dict]:
        """Search across all pages and databases."""
        params: dict[str, Any] = {"query": query, "page_size": page_size}

        if filter:
            params["filter"] = filter
        if sort:
            params["sort"] = sort

        response = await self.client.search(**params)
        return response.get("results", [])
