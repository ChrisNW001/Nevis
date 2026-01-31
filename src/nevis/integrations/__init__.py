"""Service integrations for Nevis assistant."""

from nevis.integrations.fireflies import FirefliesIntegration, FirefliesConfig
from nevis.integrations.notion import NotionIntegration, NotionConfig
from nevis.integrations.slack import SlackIntegration, SlackConfig

__all__ = [
    "FirefliesIntegration",
    "FirefliesConfig",
    "NotionIntegration",
    "NotionConfig",
    "SlackIntegration",
    "SlackConfig",
]
