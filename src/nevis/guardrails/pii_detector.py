"""PII detection and masking guardrail."""

from __future__ import annotations

import re

from nevis.guardrails.pipeline import Guardrail, GuardrailResult

# Common PII patterns
_PII_PATTERNS = {
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
    "phone_us": re.compile(r"\b(?:\+1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit_card": re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
    "ip_address": re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"),
}

_MASKS = {
    "email": "[EMAIL]",
    "phone_us": "[PHONE]",
    "ssn": "[SSN]",
    "credit_card": "[CREDIT_CARD]",
    "ip_address": "[IP_ADDRESS]",
}


class PIIDetector(Guardrail):
    """Detects and optionally masks PII in text."""

    name = "pii_detector"

    def __init__(
        self,
        mask: bool = True,
        block: bool = False,
        detect_types: list[str] | None = None,
    ):
        self._mask = mask
        self._block = block
        self._detect_types = detect_types or list(_PII_PATTERNS.keys())

    async def check(self, text: str, direction: str = "input") -> GuardrailResult:
        detections: dict[str, int] = {}
        masked_text = text

        for pii_type in self._detect_types:
            pattern = _PII_PATTERNS.get(pii_type)
            if not pattern:
                continue
            matches = pattern.findall(text)
            if matches:
                detections[pii_type] = len(matches)
                if self._mask:
                    masked_text = pattern.sub(_MASKS.get(pii_type, "[PII]"), masked_text)

        if not detections:
            return GuardrailResult(passed=True, guardrail_name=self.name)

        if self._block:
            return GuardrailResult(
                passed=False,
                guardrail_name=self.name,
                message=f"PII detected and blocked: {detections}",
                metadata={"detections": detections},
            )

        return GuardrailResult(
            passed=True,
            guardrail_name=self.name,
            message=f"PII detected and masked: {detections}",
            modified_text=masked_text if self._mask else None,
            metadata={"detections": detections},
        )
