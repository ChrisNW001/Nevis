"""Metrics collector for agent performance tracking."""

from __future__ import annotations

import statistics
import time
from typing import Any

from pydantic import BaseModel, Field


class MetricsCollector:
    """Collects and aggregates agent performance metrics.

    Tracks: tokens/turn, cost/conversation, latency, tool success rate.
    """

    def __init__(self):
        self._counters: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = {}
        self._gauges: dict[str, float] = {}

    def increment(self, name: str, value: float = 1.0) -> None:
        """Increment a counter."""
        self._counters[name] = self._counters.get(name, 0.0) + value

    def record(self, name: str, value: float) -> None:
        """Record a value in a histogram (for latency, token counts, etc)."""
        if name not in self._histograms:
            self._histograms[name] = []
        self._histograms[name].append(value)

    def gauge(self, name: str, value: float) -> None:
        """Set a gauge value (current state, e.g. active agents)."""
        self._gauges[name] = value

    def get_counter(self, name: str) -> float:
        return self._counters.get(name, 0.0)

    def get_histogram_stats(self, name: str) -> dict[str, float]:
        """Get p50, p95, p99, mean, min, max for a histogram."""
        values = self._histograms.get(name, [])
        if not values:
            return {}
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        return {
            "count": n,
            "mean": round(statistics.mean(sorted_vals), 2),
            "min": round(sorted_vals[0], 2),
            "max": round(sorted_vals[-1], 2),
            "p50": round(sorted_vals[int(n * 0.50)], 2),
            "p95": round(sorted_vals[min(int(n * 0.95), n - 1)], 2),
            "p99": round(sorted_vals[min(int(n * 0.99), n - 1)], 2),
        }

    def get_gauge(self, name: str) -> float:
        return self._gauges.get(name, 0.0)

    # Convenience methods for common agent metrics

    def record_llm_call(self, tokens: int, latency_ms: float, cost_usd: float) -> None:
        self.increment("llm.calls")
        self.increment("llm.tokens.total", tokens)
        self.increment("llm.cost_usd", cost_usd)
        self.record("llm.latency_ms", latency_ms)
        self.record("llm.tokens_per_call", tokens)

    def record_tool_call(self, tool_name: str, latency_ms: float, success: bool) -> None:
        self.increment("tools.calls")
        self.increment(f"tools.{tool_name}.calls")
        self.record("tools.latency_ms", latency_ms)
        if success:
            self.increment("tools.success")
            self.increment(f"tools.{tool_name}.success")
        else:
            self.increment("tools.failure")
            self.increment(f"tools.{tool_name}.failure")

    def record_agent_turn(self, turn_number: int, tokens: int) -> None:
        self.increment("agent.turns")
        self.record("agent.tokens_per_turn", tokens)

    def tool_success_rate(self, tool_name: str | None = None) -> float:
        prefix = f"tools.{tool_name}" if tool_name else "tools"
        success = self.get_counter(f"{prefix}.success")
        total = self.get_counter(f"{prefix}.calls")
        return success / total if total > 0 else 0.0

    def snapshot(self) -> dict[str, Any]:
        """Full metrics snapshot."""
        return {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "histograms": {
                name: self.get_histogram_stats(name) for name in self._histograms
            },
        }
