"""Topic filter -- keep agents within allowed domain boundaries."""

from __future__ import annotations

from nevis.guardrails.pipeline import Guardrail, GuardrailResult


class TopicFilter(Guardrail):
    """Filter inputs/outputs to stay within allowed topic boundaries.

    Can operate in allowlist mode (only specified topics) or
    blocklist mode (everything except blocked topics).
    """

    name = "topic_filter"

    def __init__(
        self,
        allowed_topics: list[str] | None = None,
        blocked_topics: list[str] | None = None,
        blocked_keywords: list[str] | None = None,
    ):
        self._allowed = [t.lower() for t in (allowed_topics or [])]
        self._blocked = [t.lower() for t in (blocked_topics or [])]
        self._blocked_keywords = [k.lower() for k in (blocked_keywords or [])]

    async def check(self, text: str, direction: str = "input") -> GuardrailResult:
        text_lower = text.lower()

        # Check blocked keywords
        for kw in self._blocked_keywords:
            if kw in text_lower:
                return GuardrailResult(
                    passed=False,
                    guardrail_name=self.name,
                    message=f"Blocked keyword detected: '{kw}'",
                    metadata={"blocked_keyword": kw},
                )

        # Check blocked topics
        for topic in self._blocked:
            if topic in text_lower:
                return GuardrailResult(
                    passed=False,
                    guardrail_name=self.name,
                    message=f"Blocked topic detected: '{topic}'",
                    metadata={"blocked_topic": topic},
                )

        # If allowlist is set, check that at least one allowed topic is present
        if self._allowed:
            found = any(topic in text_lower for topic in self._allowed)
            if not found:
                return GuardrailResult(
                    passed=False,
                    guardrail_name=self.name,
                    message="Input does not match any allowed topics",
                    metadata={"allowed_topics": self._allowed},
                )

        return GuardrailResult(passed=True, guardrail_name=self.name)
