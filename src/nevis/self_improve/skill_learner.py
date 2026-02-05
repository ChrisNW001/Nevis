"""Skill learner -- discover and save effective tool-call sequences."""

from __future__ import annotations

import logging
from typing import Any

from nevis.memory.procedural import ProceduralMemory, Skill
from nevis.observability.audit import AuditLogger

logger = logging.getLogger(__name__)


class SkillLearner:
    """Monitors agent activity and learns reusable skills from successful sequences.

    When the agent completes a task successfully using a sequence of tool calls,
    the learner can save that sequence as a named skill for future reuse.
    """

    def __init__(
        self,
        procedural_memory: ProceduralMemory,
        audit_logger: AuditLogger,
        min_steps: int = 2,
    ):
        self.memory = procedural_memory
        self.audit = audit_logger
        self.min_steps = min_steps

    async def learn_from_session(
        self,
        task_description: str,
        agent_id: str = "",
        success: bool = True,
    ) -> Skill | None:
        """Analyze recent audit entries and save a skill if the pattern is useful."""
        if not success:
            return None

        # Get recent tool calls for this agent
        entries = self.audit.get_entries(agent_id=agent_id, action="tool_call", limit=50)

        if len(entries) < self.min_steps:
            return None

        # Build the step sequence
        steps = []
        for entry in entries:
            steps.append({
                "tool": entry.tool,
                "arguments": entry.input_data,
                "expected_output_keys": list(entry.output_data.keys()) if entry.output_data else [],
            })

        # Check if a similar skill already exists
        existing = await self.memory.find_skill(task_description)
        if existing:
            # Update success count on existing skill
            best = existing[0]
            await self.memory.record_outcome(best.name, success=True)
            return best

        # Create new skill
        skill_name = self._generate_name(task_description)
        skill = Skill(
            name=skill_name,
            description=task_description,
            steps=steps,
            success_count=1,
            tags=self._extract_tags(steps),
        )

        await self.memory.save_skill(skill)
        logger.info(f"Learned new skill: '{skill_name}' ({len(steps)} steps)")
        return skill

    async def suggest_skill(self, task: str) -> Skill | None:
        """Suggest a previously learned skill for a given task."""
        matches = await self.memory.find_skill(task)
        if matches and matches[0].success_rate >= 0.5:
            return matches[0]
        return None

    def _generate_name(self, description: str) -> str:
        """Generate a short name from a task description."""
        words = description.lower().split()[:4]
        return "_".join(w for w in words if w.isalnum())

    def _extract_tags(self, steps: list[dict[str, Any]]) -> list[str]:
        """Extract tags from tool names in a step sequence."""
        return list({step["tool"] for step in steps if "tool" in step})
