"""Slack integration for Nevis assistant."""

import logging
import os
from typing import Any

from pydantic import BaseModel
from slack_sdk.web.async_client import AsyncWebClient

logger = logging.getLogger(__name__)


class SlackConfig(BaseModel):
    """Configuration for Slack integration."""

    bot_token: str
    default_channel: str | None = None


class SlackIntegration:
    """Integration with Slack API for messaging and channel management."""

    def __init__(self, config: SlackConfig):
        self.config = config
        self.client = AsyncWebClient(token=config.bot_token)
        self._initialized = False

    @classmethod
    def from_env(cls) -> "SlackIntegration":
        """Create integration from environment variables."""
        bot_token = os.getenv("SLACK_BOT_TOKEN")
        if not bot_token:
            raise ValueError("SLACK_BOT_TOKEN environment variable is required")

        return cls(
            config=SlackConfig(
                bot_token=bot_token,
                default_channel=os.getenv("SLACK_DEFAULT_CHANNEL"),
            )
        )

    async def initialize(self):
        """Initialize the Slack connection."""
        logger.info("Initializing Slack integration...")
        try:
            response = await self.client.auth_test()
            logger.info(f"Connected to Slack as: {response.get('user', 'Unknown')}")
            self._initialized = True
        except Exception as e:
            logger.error(f"Failed to connect to Slack: {e}")
            raise

    async def shutdown(self):
        """Clean up Slack connection."""
        logger.info("Shutting down Slack integration")
        self._initialized = False

    # Messaging

    async def send_message(
        self,
        text: str,
        channel: str | None = None,
        blocks: list[dict] | None = None,
        thread_ts: str | None = None,
    ) -> dict:
        """Send a message to a channel."""
        ch = channel or self.config.default_channel
        if not ch:
            raise ValueError("No channel provided and no default configured")

        kwargs: dict[str, Any] = {"channel": ch, "text": text}
        if blocks:
            kwargs["blocks"] = blocks
        if thread_ts:
            kwargs["thread_ts"] = thread_ts

        response = await self.client.chat_postMessage(**kwargs)
        return response.data

    async def update_message(
        self,
        channel: str,
        ts: str,
        text: str,
        blocks: list[dict] | None = None,
    ) -> dict:
        """Update an existing message."""
        kwargs: dict[str, Any] = {"channel": channel, "ts": ts, "text": text}
        if blocks:
            kwargs["blocks"] = blocks

        response = await self.client.chat_update(**kwargs)
        return response.data

    async def delete_message(self, channel: str, ts: str) -> dict:
        """Delete a message."""
        response = await self.client.chat_delete(channel=channel, ts=ts)
        return response.data

    # Reactions

    async def add_reaction(self, channel: str, ts: str, name: str) -> dict:
        """Add a reaction to a message."""
        response = await self.client.reactions_add(channel=channel, timestamp=ts, name=name)
        return response.data

    # Channels

    async def list_channels(self, limit: int = 200) -> list[dict]:
        """List public channels."""
        results = []
        cursor = None

        while True:
            kwargs: dict[str, Any] = {"limit": limit}
            if cursor:
                kwargs["cursor"] = cursor

            response = await self.client.conversations_list(**kwargs)
            results.extend(response.get("channels", []))

            cursor = response.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break

        return results

    async def get_channel_history(
        self,
        channel: str,
        limit: int = 100,
    ) -> list[dict]:
        """Get recent messages from a channel."""
        response = await self.client.conversations_history(channel=channel, limit=limit)
        return response.get("messages", [])

    async def get_thread_replies(self, channel: str, ts: str) -> list[dict]:
        """Get replies in a message thread."""
        response = await self.client.conversations_replies(channel=channel, ts=ts)
        return response.get("messages", [])

    # Users

    async def get_user_info(self, user_id: str) -> dict:
        """Get information about a user."""
        response = await self.client.users_info(user=user_id)
        return response.get("user", {})

    async def list_users(self, limit: int = 200) -> list[dict]:
        """List workspace users."""
        results = []
        cursor = None

        while True:
            kwargs: dict[str, Any] = {"limit": limit}
            if cursor:
                kwargs["cursor"] = cursor

            response = await self.client.users_list(**kwargs)
            results.extend(response.get("members", []))

            cursor = response.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break

        return results
