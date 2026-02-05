"""Reflection loop -- evaluate, critique, revise agent outputs."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from nevis.llm.base import LLMProvider, Message

logger = logging.getLogger(__name__)

_EVALUATE_PROMPT = """Evaluate the following agent output against the success criteria.

Task: {task}
Output: {output}
Success criteria: {criteria}

Rate the quality from 0.0 to 1.0 and explain your reasoning.
Return JSON: {{"score": <float>, "reasoning": "<text>", "suggestions": ["<improvement>"]}}"""

_CRITIQUE_PROMPT = """You are a critical reviewer. Analyze this output and identify weaknesses.

Task: {task}
Output: {output}

What could be improved? Be specific and actionable.
Return JSON: {{"weaknesses": ["<issue>"], "improvements": ["<suggestion>"]}}"""

_REVISE_PROMPT = """Revise this output based on the feedback.

Original task: {task}
Original output: {output}
Feedback: {feedback}

Produce an improved version that addresses the feedback."""


class ReflectionResult(BaseModel):
    """Result of a reflection cycle."""

    original_output: str
    final_output: str
    score: float = 0.0
    iterations: int = 0
    evaluations: list[dict[str, Any]] = Field(default_factory=list)
    improved: bool = False


class ReflectionLoop:
    """Evaluate -> Critique -> Revise cycle for agent self-improvement.

    Limited to max_iterations (default 2) to control cost and latency.
    """

    def __init__(
        self,
        llm: LLMProvider,
        max_iterations: int = 2,
        quality_threshold: float = 0.8,
    ):
        self.llm = llm
        self.max_iterations = max_iterations
        self.quality_threshold = quality_threshold

    async def reflect(
        self,
        task: str,
        output: str,
        criteria: str = "Accurate, complete, well-structured response",
    ) -> ReflectionResult:
        """Run the full reflection loop on an output."""
        result = ReflectionResult(original_output=output, final_output=output)
        current_output = output

        for i in range(self.max_iterations):
            # EVALUATE
            evaluation = await self._evaluate(task, current_output, criteria)
            result.evaluations.append(evaluation)
            result.score = evaluation.get("score", 0.0)

            logger.info(f"Reflection iteration {i + 1}: score={result.score:.2f}")

            # If quality is good enough, stop
            if result.score >= self.quality_threshold:
                break

            # CRITIQUE
            critique = await self._critique(task, current_output)

            # REVISE
            feedback = "\n".join(
                critique.get("improvements", []) + critique.get("weaknesses", [])
            )
            if not feedback:
                break

            revised = await self._revise(task, current_output, feedback)
            if revised and revised != current_output:
                current_output = revised
                result.improved = True

            result.iterations = i + 1

        result.final_output = current_output
        return result

    async def _evaluate(self, task: str, output: str, criteria: str) -> dict[str, Any]:
        prompt = _EVALUATE_PROMPT.format(task=task, output=output, criteria=criteria)
        response = await self.llm.chat([
            Message(role="system", content="You are a precise evaluator. Return only valid JSON."),
            Message(role="user", content=prompt),
        ])
        return self._parse_json(response.message.content or "{}", {"score": 0.5})

    async def _critique(self, task: str, output: str) -> dict[str, Any]:
        prompt = _CRITIQUE_PROMPT.format(task=task, output=output)
        response = await self.llm.chat([
            Message(role="system", content="You are a critical reviewer. Return only valid JSON."),
            Message(role="user", content=prompt),
        ])
        return self._parse_json(response.message.content or "{}", {})

    async def _revise(self, task: str, output: str, feedback: str) -> str:
        prompt = _REVISE_PROMPT.format(task=task, output=output, feedback=feedback)
        response = await self.llm.chat([
            Message(role="system", content="You produce improved, revised outputs."),
            Message(role="user", content=prompt),
        ])
        return response.message.content or output

    def _parse_json(self, raw: str, default: dict[str, Any]) -> dict[str, Any]:
        import json
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
        if raw.endswith("```"):
            raw = raw.rsplit("```", 1)[0]
        try:
            return json.loads(raw.strip())
        except json.JSONDecodeError:
            return default
