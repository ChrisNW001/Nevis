"""Guardrail pipeline -- chain of pre/post checks around LLM calls."""

from __future__ import annotations

import abc
import logging
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class GuardrailResult(BaseModel):
    """Result from a guardrail check."""

    passed: bool
    guardrail_name: str
    message: str = ""
    modified_text: str | None = None  # if the guardrail rewrites the text
    metadata: dict[str, Any] = Field(default_factory=dict)


class Guardrail(abc.ABC):
    """Abstract base class for a guardrail check."""

    name: str = "base_guardrail"

    @abc.abstractmethod
    async def check(self, text: str, direction: str = "input") -> GuardrailResult:
        """Check text. direction is 'input' (pre-LLM) or 'output' (post-LLM)."""


class GuardrailPipeline:
    """Chain of guardrail checks applied before and/or after LLM calls."""

    def __init__(self):
        self._input_guards: list[Guardrail] = []
        self._output_guards: list[Guardrail] = []

    def add_input_guard(self, guard: Guardrail) -> None:
        self._input_guards.append(guard)

    def add_output_guard(self, guard: Guardrail) -> None:
        self._output_guards.append(guard)

    def add_guard(self, guard: Guardrail) -> None:
        """Add a guard to both input and output pipelines."""
        self._input_guards.append(guard)
        self._output_guards.append(guard)

    async def check_input(self, text: str) -> tuple[bool, str, list[GuardrailResult]]:
        """Run all input guardrails. Returns (passed, possibly_modified_text, results)."""
        return await self._run_pipeline(self._input_guards, text, "input")

    async def check_output(self, text: str) -> tuple[bool, str, list[GuardrailResult]]:
        """Run all output guardrails. Returns (passed, possibly_modified_text, results)."""
        return await self._run_pipeline(self._output_guards, text, "output")

    async def _run_pipeline(
        self, guards: list[Guardrail], text: str, direction: str
    ) -> tuple[bool, str, list[GuardrailResult]]:
        results = []
        current_text = text

        for guard in guards:
            result = await guard.check(current_text, direction)
            results.append(result)

            if not result.passed:
                logger.warning(f"Guardrail '{guard.name}' blocked {direction}: {result.message}")
                return False, current_text, results

            if result.modified_text is not None:
                current_text = result.modified_text

        return True, current_text, results
