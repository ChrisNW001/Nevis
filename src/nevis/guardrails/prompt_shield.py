"""Prompt injection detection guardrail."""

from __future__ import annotations

import re

from nevis.guardrails.pipeline import Guardrail, GuardrailResult

# Common prompt injection patterns
_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"ignore\s+(all\s+)?above",
    r"disregard\s+(all\s+)?previous",
    r"forget\s+(all\s+)?previous",
    r"you\s+are\s+now\s+(?:a\s+)?(?:different|new)",
    r"pretend\s+(?:you\s+are|to\s+be)",
    r"act\s+as\s+(?:if\s+you\s+are|a)",
    r"system\s*:\s*you\s+are",
    r"<\s*system\s*>",
    r"\]\]\s*\[\[system",
    r"override\s+(?:your\s+)?(?:instructions|rules|guidelines)",
    r"bypass\s+(?:your\s+)?(?:safety|restrictions|filters)",
    r"jailbreak",
    r"do\s+anything\s+now",
    r"developer\s+mode",
]


class PromptShield(Guardrail):
    """Detects common prompt injection attempts."""

    name = "prompt_shield"

    def __init__(self, custom_patterns: list[str] | None = None, threshold: float = 0.5):
        self._patterns = [re.compile(p, re.IGNORECASE) for p in _INJECTION_PATTERNS]
        if custom_patterns:
            self._patterns.extend(re.compile(p, re.IGNORECASE) for p in custom_patterns)
        self._threshold = threshold

    async def check(self, text: str, direction: str = "input") -> GuardrailResult:
        if direction != "input":
            return GuardrailResult(passed=True, guardrail_name=self.name)

        matches = []
        for pattern in self._patterns:
            if pattern.search(text):
                matches.append(pattern.pattern)

        # Score based on number of matching patterns
        score = len(matches) / max(len(self._patterns), 1)

        if matches and score >= self._threshold:
            return GuardrailResult(
                passed=False,
                guardrail_name=self.name,
                message=f"Potential prompt injection detected ({len(matches)} pattern matches)",
                metadata={"patterns": matches, "score": round(score, 3)},
            )

        if matches:
            return GuardrailResult(
                passed=True,
                guardrail_name=self.name,
                message=f"Low-confidence injection signal ({len(matches)} weak matches)",
                metadata={"patterns": matches, "score": round(score, 3)},
            )

        return GuardrailResult(passed=True, guardrail_name=self.name)
