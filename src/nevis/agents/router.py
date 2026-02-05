"""Task router -- match tasks to the best agent based on capabilities."""

from __future__ import annotations

import logging
from typing import Any

from nevis.agents.base import AgentConfig

logger = logging.getLogger(__name__)


class TaskRouter:
    """Routes tasks to the most appropriate agent configuration.

    Uses keyword matching and role-capability mapping. Can be upgraded
    to LLM-based routing for complex classification.
    """

    def __init__(self):
        self._routes: list[_Route] = []

    def register_route(
        self,
        keywords: list[str],
        agent_config: AgentConfig,
        priority: int = 0,
    ) -> None:
        """Register a routing rule: if task matches keywords, use this agent config."""
        self._routes.append(_Route(
            keywords=[k.lower() for k in keywords],
            config=agent_config,
            priority=priority,
        ))
        self._routes.sort(key=lambda r: r.priority, reverse=True)

    def route(self, task: str) -> AgentConfig | None:
        """Find the best agent config for a task. Returns None if no match."""
        task_lower = task.lower()
        best_match: _Route | None = None
        best_score = 0

        for route in self._routes:
            score = sum(1 for kw in route.keywords if kw in task_lower)
            if score > best_score:
                best_score = score
                best_match = route

        if best_match:
            logger.info(f"Routed task to agent '{best_match.config.name}' (score={best_score})")
            return best_match.config

        return None

    def route_or_default(self, task: str, default: AgentConfig) -> AgentConfig:
        """Route to best match, or fall back to default."""
        return self.route(task) or default


class _Route:
    __slots__ = ("keywords", "config", "priority")

    def __init__(self, keywords: list[str], config: AgentConfig, priority: int):
        self.keywords = keywords
        self.config = config
        self.priority = priority
