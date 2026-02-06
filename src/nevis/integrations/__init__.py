"""Service integrations for Nevis assistant."""

from nevis.integrations.notion import NotionIntegration, NotionConfig
from nevis.integrations.slack import SlackIntegration, SlackConfig

__all__ = ["NotionIntegration", "NotionConfig", "SlackIntegration", "SlackConfig"]
