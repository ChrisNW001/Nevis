"""Plan-and-execute: decompose complex goals into sub-tasks."""

from __future__ import annotations

import json
import logging
import uuid
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from nevis.llm.base import LLMProvider, Message

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class SubTask(BaseModel):
    """A single sub-task in a plan."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    description: str
    dependencies: list[str] = Field(default_factory=list)  # IDs of tasks this depends on
    tools: list[str] = Field(default_factory=list)  # suggested tools
    success_criteria: str = ""
    status: TaskStatus = TaskStatus.PENDING
    result: str = ""


class Plan(BaseModel):
    """A plan consisting of ordered sub-tasks forming a DAG."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    goal: str
    tasks: list[SubTask] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def get_ready_tasks(self) -> list[SubTask]:
        """Get tasks whose dependencies are all completed."""
        completed_ids = {t.id for t in self.tasks if t.status == TaskStatus.COMPLETED}
        return [
            t for t in self.tasks
            if t.status == TaskStatus.PENDING
            and all(dep in completed_ids for dep in t.dependencies)
        ]

    def is_complete(self) -> bool:
        return all(t.status in (TaskStatus.COMPLETED, TaskStatus.SKIPPED) for t in self.tasks)

    def has_failed(self) -> bool:
        return any(t.status == TaskStatus.FAILED for t in self.tasks)

    def summary(self) -> str:
        lines = [f"Plan: {self.goal}"]
        for t in self.tasks:
            marker = {"pending": "[ ]", "in_progress": "[~]", "completed": "[x]",
                       "failed": "[!]", "skipped": "[-]"}[t.status]
            lines.append(f"  {marker} {t.description}")
        return "\n".join(lines)


_DECOMPOSE_PROMPT = """You are a planning agent. Break down the following goal into concrete, \
ordered sub-tasks. Each sub-task should be a single actionable step.

Return a JSON array of objects with these fields:
- "description": what to do
- "dependencies": list of indices (0-based) of tasks this depends on
- "tools": list of tool names that might be useful
- "success_criteria": how to verify the task is done

Goal: {goal}

Available tools: {tools}

Return ONLY the JSON array, no other text."""

_REPLAN_PROMPT = """A sub-task has failed. Revise the remaining plan.

Original goal: {goal}
Failed task: {failed_task}
Error: {error}
Remaining tasks: {remaining}

Return a revised JSON array of sub-tasks (same format as before). \
You may add, remove, or modify tasks. Return ONLY the JSON array."""


class Planner:
    """Plan-and-execute: decompose goals into sub-tasks, execute, replan on failure."""

    def __init__(self, llm: LLMProvider, available_tools: list[str] | None = None):
        self.llm = llm
        self.available_tools = available_tools or []

    async def decompose(self, goal: str) -> Plan:
        """Decompose a goal into a plan of sub-tasks."""
        prompt = _DECOMPOSE_PROMPT.format(
            goal=goal,
            tools=", ".join(self.available_tools) if self.available_tools else "none specified",
        )

        response = await self.llm.chat([
            Message(role="system", content="You are a precise planning agent. Return only valid JSON."),
            Message(role="user", content=prompt),
        ])

        tasks = self._parse_tasks(response.message.content or "[]")
        plan = Plan(goal=goal, tasks=tasks)
        logger.info(f"Created plan with {len(tasks)} sub-tasks for: {goal}")
        return plan

    async def replan(self, plan: Plan, failed_task: SubTask, error: str) -> Plan:
        """Revise the plan after a task failure."""
        remaining = [t for t in plan.tasks if t.status == TaskStatus.PENDING]
        prompt = _REPLAN_PROMPT.format(
            goal=plan.goal,
            failed_task=failed_task.description,
            error=error,
            remaining=json.dumps([t.description for t in remaining]),
        )

        response = await self.llm.chat([
            Message(role="system", content="You are a precise planning agent. Return only valid JSON."),
            Message(role="user", content=prompt),
        ])

        new_tasks = self._parse_tasks(response.message.content or "[]")
        # Keep completed tasks, replace pending ones
        completed = [t for t in plan.tasks if t.status == TaskStatus.COMPLETED]
        plan.tasks = completed + new_tasks
        logger.info(f"Replanned: {len(new_tasks)} new tasks")
        return plan

    def _parse_tasks(self, raw: str) -> list[SubTask]:
        """Parse LLM output into SubTask objects."""
        # Strip markdown code fences if present
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
        if raw.endswith("```"):
            raw = raw.rsplit("```", 1)[0]
        raw = raw.strip()

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse plan JSON: {raw[:200]}")
            return [SubTask(description="Execute the goal directly")]

        tasks = []
        for i, item in enumerate(data):
            dep_indices = item.get("dependencies", [])
            tasks.append(SubTask(
                description=item.get("description", f"Task {i}"),
                dependencies=[],  # resolved below
                tools=item.get("tools", []),
                success_criteria=item.get("success_criteria", ""),
            ))

        # Resolve dependency indices to IDs
        for i, item in enumerate(data):
            dep_indices = item.get("dependencies", [])
            tasks[i].dependencies = [
                tasks[j].id for j in dep_indices
                if isinstance(j, int) and 0 <= j < len(tasks)
            ]

        return tasks
