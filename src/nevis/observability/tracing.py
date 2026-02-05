"""Tracing system -- nested spans for tracking agent decisions and tool calls.

Designed for OpenTelemetry compatibility. Uses a lightweight built-in
implementation by default; swap with the OTel SDK for production.
"""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager, contextmanager
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class Span(BaseModel):
    """A single traced operation (LLM call, tool invocation, agent decision)."""

    trace_id: str
    span_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    parent_span_id: str | None = None
    name: str
    attributes: dict[str, Any] = Field(default_factory=dict)
    start_time: float = Field(default_factory=time.time)
    end_time: float | None = None
    status: str = "ok"  # ok, error
    events: list[dict[str, Any]] = Field(default_factory=list)

    @property
    def duration_ms(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time) * 1000
        return 0.0

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        self.events.append({
            "name": name,
            "timestamp": time.time(),
            "attributes": attributes or {},
        })

    def end(self, status: str = "ok") -> None:
        self.end_time = time.time()
        self.status = status

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "name": self.name,
            "attributes": self.attributes,
            "duration_ms": round(self.duration_ms, 2),
            "status": self.status,
            "events": self.events,
        }


class Tracer:
    """Lightweight tracing system with nested span support.

    Usage:
        tracer = Tracer()
        with tracer.span("llm_call", model="claude-3") as span:
            result = await llm.chat(...)
            span.set_attribute("tokens", result.usage.total_tokens)
    """

    def __init__(self, service_name: str = "nevis"):
        self.service_name = service_name
        self._spans: list[Span] = []
        self._active_span: Span | None = None
        self._exporters: list[Any] = []

    @contextmanager
    def span(self, name: str, **attributes: Any):
        """Create a traced span (sync context manager)."""
        trace_id = self._active_span.trace_id if self._active_span else uuid.uuid4().hex[:16]
        parent_id = self._active_span.span_id if self._active_span else None

        s = Span(
            trace_id=trace_id,
            parent_span_id=parent_id,
            name=name,
            attributes={"service": self.service_name, **attributes},
        )
        prev_active = self._active_span
        self._active_span = s

        try:
            yield s
            s.end("ok")
        except Exception as e:
            s.set_attribute("error.message", str(e))
            s.set_attribute("error.type", type(e).__name__)
            s.end("error")
            raise
        finally:
            self._active_span = prev_active
            self._spans.append(s)
            self._export(s)

    @asynccontextmanager
    async def async_span(self, name: str, **attributes: Any):
        """Create a traced span (async context manager)."""
        trace_id = self._active_span.trace_id if self._active_span else uuid.uuid4().hex[:16]
        parent_id = self._active_span.span_id if self._active_span else None

        s = Span(
            trace_id=trace_id,
            parent_span_id=parent_id,
            name=name,
            attributes={"service": self.service_name, **attributes},
        )
        prev_active = self._active_span
        self._active_span = s

        try:
            yield s
            s.end("ok")
        except Exception as e:
            s.set_attribute("error.message", str(e))
            s.set_attribute("error.type", type(e).__name__)
            s.end("error")
            raise
        finally:
            self._active_span = prev_active
            self._spans.append(s)
            self._export(s)

    def _export(self, span: Span) -> None:
        for exporter in self._exporters:
            try:
                exporter(span)
            except Exception as e:
                logger.warning(f"Span export failed: {e}")

    def add_exporter(self, exporter: Any) -> None:
        """Add a span exporter (callable that receives a Span)."""
        self._exporters.append(exporter)

    def get_spans(self, trace_id: str | None = None) -> list[Span]:
        if trace_id:
            return [s for s in self._spans if s.trace_id == trace_id]
        return list(self._spans)

    @property
    def active_span(self) -> Span | None:
        return self._active_span


def console_exporter(span: Span) -> None:
    """Simple console exporter for development."""
    logger.info(
        f"[TRACE] {span.name} | {span.duration_ms:.1f}ms | "
        f"status={span.status} | {span.attributes}"
    )
