"""Monitoring: lightweight in-memory metrics exposed at /metrics (JSON).

A later phase can swap the collector for Prometheus/OpenTelemetry; the
contract (counters/gauges + snapshot endpoint) stays the same.
"""

from __future__ import annotations

import threading
from collections import defaultdict


class Metrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.counters: dict[str, int] = defaultdict(int)
        self.gauges: dict[str, float] = {}
        self.api_errors: dict[str, int] = defaultdict(int)

    def inc(self, name: str, value: int = 1) -> None:
        with self._lock:
            self.counters[name] += value

    def set_gauge(self, name: str, value: float) -> None:
        with self._lock:
            self.gauges[name] = value

    def inc_error(self, status_code: int) -> None:
        with self._lock:
            self.api_errors[str(status_code)] += 1

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "counters": dict(self.counters),
                "gauges": dict(self.gauges),
                "api_errors": dict(self.api_errors),
            }


metrics = Metrics()
