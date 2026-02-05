"""Tests for observability system."""

import pytest
from nevis.observability.tracing import Tracer
from nevis.observability.audit import AuditLogger
from nevis.observability.metrics import MetricsCollector


class TestTracer:
    def test_span_creation(self):
        tracer = Tracer()
        with tracer.span("test_op", key="value") as span:
            span.set_attribute("extra", 42)
        spans = tracer.get_spans()
        assert len(spans) == 1
        assert spans[0].name == "test_op"
        assert spans[0].attributes["extra"] == 42
        assert spans[0].duration_ms > 0

    def test_nested_spans(self):
        tracer = Tracer()
        with tracer.span("parent") as parent:
            with tracer.span("child") as child:
                pass
        spans = tracer.get_spans()
        assert len(spans) == 2
        child_span = spans[0]
        parent_span = spans[1]
        assert child_span.parent_span_id == parent_span.span_id

    def test_error_span(self):
        tracer = Tracer()
        with pytest.raises(ValueError):
            with tracer.span("failing") as span:
                raise ValueError("boom")
        spans = tracer.get_spans()
        assert spans[0].status == "error"


class TestAuditLogger:
    def test_log_tool_call(self, tmp_path):
        logger = AuditLogger(log_path=str(tmp_path / "audit.jsonl"))
        entry = logger.log_tool_call(
            tool_name="web_search",
            input_data={"query": "test"},
            output_data={"results": []},
            duration_ms=150.0,
        )
        assert entry.action == "tool_call"
        assert entry.tool == "web_search"

    def test_summary(self, tmp_path):
        logger = AuditLogger(log_path=str(tmp_path / "audit.jsonl"))
        logger.log_tool_call("t1", {}, {}, 10.0)
        logger.log_llm_call("claude", 100, 50, 200.0, cost_usd=0.001)
        summary = logger.summary()
        assert summary["total_entries"] == 2
        assert "tool_call" in summary["actions"]
        assert "llm_call" in summary["actions"]


class TestMetricsCollector:
    def test_counter(self):
        m = MetricsCollector()
        m.increment("calls", 1)
        m.increment("calls", 2)
        assert m.get_counter("calls") == 3

    def test_histogram(self):
        m = MetricsCollector()
        for v in [10, 20, 30, 40, 50]:
            m.record("latency", v)
        stats = m.get_histogram_stats("latency")
        assert stats["count"] == 5
        assert stats["mean"] == 30.0
        assert stats["min"] == 10.0
        assert stats["max"] == 50.0

    def test_tool_success_rate(self):
        m = MetricsCollector()
        m.record_tool_call("search", 10.0, success=True)
        m.record_tool_call("search", 20.0, success=True)
        m.record_tool_call("search", 15.0, success=False)
        rate = m.tool_success_rate("search")
        assert abs(rate - 2 / 3) < 0.01

    def test_snapshot(self):
        m = MetricsCollector()
        m.increment("x")
        m.gauge("active", 5)
        m.record("lat", 100)
        snap = m.snapshot()
        assert "counters" in snap
        assert "gauges" in snap
        assert "histograms" in snap
