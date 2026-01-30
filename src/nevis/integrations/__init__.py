"""Service integrations for Nevis assistant."""

from nevis.integrations.fireflies import FirefliesIntegration, FirefliesConfig
from nevis.integrations.notion import NotionIntegration, NotionConfig

__all__ = [
    "FirefliesIntegration",
    "FirefliesConfig",
    "NotionIntegration",
    "NotionConfig",
]
