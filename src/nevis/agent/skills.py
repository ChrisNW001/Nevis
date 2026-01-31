"""Nevis Skills - Pluggable capabilities for the master agent."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class SkillResult:
    """Result from executing a skill."""

    success: bool
    message: str
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class NevisSkill(ABC):
    """Base class for Nevis skills.

    A skill is a capability that Nevis can execute, such as:
    - Fireflies meeting analysis
    - Customer segmentation
    - Notion updates
    - etc.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name of the skill."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of what the skill does."""
        pass

    @property
    @abstractmethod
    def commands(self) -> list[str]:
        """List of command keywords that trigger this skill."""
        pass

    @property
    def help_text(self) -> str:
        """Detailed help text for the skill."""
        return self.description

    @abstractmethod
    def execute(self, command: str, args: dict[str, Any], context: dict[str, Any]) -> SkillResult:
        """Execute the skill with the given command and arguments.

        Args:
            command: The command that triggered the skill
            args: Parsed arguments from the command
            context: Additional context (user, channel, etc.)

        Returns:
            SkillResult with the outcome
        """
        pass

    def can_handle(self, text: str) -> bool:
        """Check if this skill can handle the given text."""
        text_lower = text.lower()
        return any(cmd in text_lower for cmd in self.commands)


class SkillRegistry:
    """Registry of all available Nevis skills."""

    def __init__(self):
        self._skills: dict[str, NevisSkill] = {}

    def register(self, skill: NevisSkill):
        """Register a skill."""
        self._skills[skill.name] = skill
        logger.info(f"Registered skill: {skill.name}")

    def get(self, name: str) -> NevisSkill | None:
        """Get a skill by name."""
        return self._skills.get(name)

    def find_for_command(self, text: str) -> NevisSkill | None:
        """Find a skill that can handle the given text."""
        for skill in self._skills.values():
            if skill.can_handle(text):
                return skill
        return None

    def all(self) -> list[NevisSkill]:
        """Get all registered skills."""
        return list(self._skills.values())

    def help_text(self) -> str:
        """Generate help text for all skills."""
        lines = ["*Verfuegbare Nevis Befehle:*\n"]

        for skill in self._skills.values():
            commands = ", ".join(f"`{cmd}`" for cmd in skill.commands)
            lines.append(f"*{skill.name}* ({commands})")
            lines.append(f"  {skill.description}\n")

        return "\n".join(lines)
