"""Tests de observabilidad: logging a stderr y metricas en memoria."""

from __future__ import annotations

import structlog

from autocad_mcp.obs import Metrics, configure_logging


def test_logs_go_to_stderr_not_stdout(capsys) -> None:
    """stdout es exclusivo del protocolo MCP; los logs deben ir a stderr."""
    configure_logging("INFO")
    fresh = structlog.get_logger("test-obs-stderr")
    fresh.info("hola", foo=1)

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "hola" in captured.err


def test_metrics_snapshot_counts_calls_and_errors() -> None:
    metrics = Metrics(enabled=True)
    metrics.record_call(0.1)
    metrics.record_call(0.3)
    metrics.record_error()

    snap = metrics.snapshot()
    assert snap["calls_total"] == 2
    assert snap["errors_total"] == 1
    assert snap["average_latency_seconds"] == 0.2
