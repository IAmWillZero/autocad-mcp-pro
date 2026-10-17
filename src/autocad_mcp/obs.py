"""Observabilidad: logging estructurado y metricas minimas."""

from __future__ import annotations

import logging
from typing import Any

import structlog

log = structlog.get_logger("autocad-mcp")


def configure_logging(level: str = "INFO") -> None:
    """Configura structlog con salida JSON."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


_prom: dict[str, Any] | None = None


def _prometheus() -> dict[str, Any] | None:
    """Inicializa (una sola vez) los objetos de prometheus_client si estan disponibles."""
    global _prom
    if _prom is not None:
        return _prom
    try:
        from prometheus_client import Counter, Gauge
    except Exception:  # pragma: no cover - dependencia opcional en runtime
        return None
    _prom = {
        "calls": Counter("autocad_mcp_calls_total", "Total MCP tool calls"),
        "errors": Counter("autocad_mcp_errors_total", "Total MCP tool errors"),
        "latency": Gauge("autocad_mcp_average_latency_seconds", "Average MCP tool latency (s)"),
    }
    return _prom


class Metrics:
    """Contadores en memoria, replicados a prometheus_client si esta presente."""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self.calls_total = 0
        self.errors_total = 0
        self.latency_sum = 0.0
        self._prom = _prometheus() if enabled else None

    def record_call(self, latency: float) -> None:
        self.calls_total += 1
        self.latency_sum += latency
        if self._prom is not None:
            self._prom["calls"].inc()
            avg = self.latency_sum / self.calls_total
            self._prom["latency"].set(avg)

    def record_error(self) -> None:
        self.errors_total += 1
        if self._prom is not None:
            self._prom["errors"].inc()

    def snapshot(self) -> dict[str, Any]:
        avg = (self.latency_sum / self.calls_total) if self.calls_total else 0.0
        return {
            "calls_total": self.calls_total,
            "errors_total": self.errors_total,
            "average_latency_seconds": round(avg, 6),
        }
