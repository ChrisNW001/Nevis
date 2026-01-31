"""Slack integration for Nevis Master Agent.

Enables Nevis to receive commands and respond via Slack.
Uses Slack Bolt for handling events and commands.
"""

import logging
import os
import re
from dataclasses import dataclass
from typing import Any, Callable, Awaitable

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class SlackConfig(BaseModel):
    """Configuration for Slack integration."""

    bot_token: str
    app_token: str  # For Socket Mode
    signing_secret: str | None = None


@dataclass
class SlackMessage:
    """Represents a Slack message."""

    channel: str
    user: str
    text: str
    ts: str  # timestamp/message ID
    thread_ts: str | None = None


@dataclass
class SlackCommand:
    """Parsed command from a Slack message."""

    name: str
    args: dict[str, Any]
    raw_text: str


class SlackIntegration:
    """Integration with Slack for the Nevis Master Agent.

    Supports:
    - Receiving direct messages
    - Responding to @mentions
    - Slash commands
    - Posting messages and updates
    """

    def __init__(self, config: SlackConfig):
        self.config = config
        self._app = None
        self._client = None
        self._initialized = False
        self._command_handlers: dict[str, Callable] = {}
        self._default_handler: Callable | None = None

    @classmethod
    def from_env(cls) -> "SlackIntegration":
        """Create integration from environment variables."""
        bot_token = os.getenv("SLACK_BOT_TOKEN")
        app_token = os.getenv("SLACK_APP_TOKEN")
        signing_secret = os.getenv("SLACK_SIGNING_SECRET")

        if not bot_token:
            raise ValueError("SLACK_BOT_TOKEN environment variable is required")
        if not app_token:
            raise ValueError("SLACK_APP_TOKEN environment variable is required")

        return cls(
            config=SlackConfig(
                bot_token=bot_token,
                app_token=app_token,
                signing_secret=signing_secret,
            )
        )

    def initialize(self):
        """Initialize the Slack connection using Bolt."""
        try:
            from slack_bolt import App
            from slack_bolt.adapter.socket_mode import SocketModeHandler
        except ImportError:
            raise ImportError(
                "slack_bolt is required. Install with: pip install slack-bolt"
            )

        logger.info("Initializing Slack integration...")

        self._app = App(token=self.config.bot_token)
        self._client = self._app.client

        # Register event handlers
        self._setup_handlers()

        self._initialized = True
        logger.info("Slack integration initialized successfully")

    def _setup_handlers(self):
        """Set up Slack event handlers."""

        @self._app.event("app_mention")
        def handle_mention(event, say):
            """Handle when the bot is mentioned."""
            message = SlackMessage(
                channel=event["channel"],
                user=event["user"],
                text=event["text"],
                ts=event["ts"],
                thread_ts=event.get("thread_ts"),
            )
            self._process_message(message, say)

        @self._app.event("message")
        def handle_message(event, say):
            """Handle direct messages."""
            # Only process DMs (channel starts with D)
            if event.get("channel_type") == "im":
                message = SlackMessage(
                    channel=event["channel"],
                    user=event["user"],
                    text=event["text"],
                    ts=event["ts"],
                    thread_ts=event.get("thread_ts"),
                )
                self._process_message(message, say)

    def _process_message(self, message: SlackMessage, say: Callable):
        """Process an incoming message and route to handlers."""
        # Remove bot mention from text
        text = re.sub(r"<@[A-Z0-9]+>", "", message.text).strip()

        # Parse command
        command = self._parse_command(text)

        if command and command.name in self._command_handlers:
            handler = self._command_handlers[command.name]
            try:
                response = handler(command, message)
                if response:
                    say(text=response, thread_ts=message.thread_ts or message.ts)
            except Exception as e:
                logger.error(f"Error handling command {command.name}: {e}")
                say(
                    text=f"Fehler bei der Verarbeitung: {str(e)}",
                    thread_ts=message.thread_ts or message.ts,
                )
        elif self._default_handler:
            try:
                response = self._default_handler(text, message)
                if response:
                    say(text=response, thread_ts=message.thread_ts or message.ts)
            except Exception as e:
                logger.error(f"Error in default handler: {e}")
                say(
                    text=f"Fehler: {str(e)}",
                    thread_ts=message.thread_ts or message.ts,
                )
        else:
            say(
                text="Ich verstehe diesen Befehl nicht. Schreibe 'hilfe' fuer eine Liste der verfuegbaren Befehle.",
                thread_ts=message.thread_ts or message.ts,
            )

    def _parse_command(self, text: str) -> SlackCommand | None:
        """Parse a command from message text."""
        text = text.strip().lower()

        # Known command patterns
        command_patterns = {
            "hilfe": r"^(hilfe|help|commands?)$",
            "status": r"^status$",
            "analyse": r"^analyse\s+(.+)$",
            "fireflies": r"^fireflies\s+(.+)$",
            "meeting": r"^meeting\s+(.+)$",
            "suche": r"^suche\s+(.+)$",
        }

        for cmd_name, pattern in command_patterns.items():
            match = re.match(pattern, text, re.IGNORECASE)
            if match:
                args = {"matches": match.groups()} if match.groups() else {}
                return SlackCommand(name=cmd_name, args=args, raw_text=text)

        return None

    def register_command(self, name: str, handler: Callable):
        """Register a command handler."""
        self._command_handlers[name] = handler
        logger.info(f"Registered command handler: {name}")

    def set_default_handler(self, handler: Callable):
        """Set the default handler for unrecognized messages."""
        self._default_handler = handler

    def send_message(self, channel: str, text: str, thread_ts: str | None = None):
        """Send a message to a Slack channel."""
        if not self._initialized:
            raise RuntimeError("Slack integration not initialized")

        self._client.chat_postMessage(
            channel=channel,
            text=text,
            thread_ts=thread_ts,
        )

    def send_blocks(
        self,
        channel: str,
        blocks: list[dict],
        text: str = "",
        thread_ts: str | None = None,
    ):
        """Send a message with Block Kit blocks."""
        if not self._initialized:
            raise RuntimeError("Slack integration not initialized")

        self._client.chat_postMessage(
            channel=channel,
            blocks=blocks,
            text=text,
            thread_ts=thread_ts,
        )

    def update_message(self, channel: str, ts: str, text: str):
        """Update an existing message."""
        if not self._initialized:
            raise RuntimeError("Slack integration not initialized")

        self._client.chat_update(
            channel=channel,
            ts=ts,
            text=text,
        )

    def add_reaction(self, channel: str, ts: str, emoji: str):
        """Add a reaction to a message."""
        if not self._initialized:
            raise RuntimeError("Slack integration not initialized")

        self._client.reactions_add(
            channel=channel,
            timestamp=ts,
            name=emoji,
        )

    def run(self):
        """Start the Slack bot using Socket Mode."""
        if not self._initialized:
            raise RuntimeError("Slack integration not initialized. Call initialize() first.")

        try:
            from slack_bolt.adapter.socket_mode import SocketModeHandler
        except ImportError:
            raise ImportError(
                "slack_bolt is required. Install with: pip install slack-bolt"
            )

        handler = SocketModeHandler(self._app, self.config.app_token)
        logger.info("Starting Slack bot in Socket Mode...")
        handler.start()
