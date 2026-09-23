"""
MockPulse - Thread-Safe In-Memory Metrics & Telemetry.
Zero external dependencies.
"""

from collections import deque
from dataclasses import dataclass, field
import threading
import time
from typing import Dict, List, Any


@dataclass
class RequestRecord:
    timestamp: float
    method: str
    path: str
    status_code: int
    duration_ms: float
    delay_injected_ms: float
    fault_injected: bool


class MetricsRegistry:
    """
    Thread-safe in-memory metrics storage using a bounded ring buffer.
    Provides latency percentiles and traffic distribution.
    """

    def __init__(self, max_records: int = 2000):
        self._lock = threading.Lock()
        self._max_records = max_records
        self._records = deque(maxlen=max_records)
        self._total_requests = 0
        self._faults_injected = 0
        self._delays_applied = 0
        self._status_counts: Dict[int, int] = {}
        self._start_time = time.time()

    def record(
        self,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
        delay_injected_ms: float = 0.0,
        fault_injected: bool = False
    ) -> None:
        """Records an HTTP transaction thread-safely."""
        rec = RequestRecord(
            timestamp=time.time(),
            method=method,
            path=path,
            status_code=status_code,
            duration_ms=duration_ms,
            delay_injected_ms=delay_injected_ms,
            fault_injected=fault_injected
        )
        with self._lock:
            self._records.append(rec)
            self._total_requests += 1
            self._status_counts[status_code] = self._status_counts.get(status_code, 0) + 1
            if fault_injected:
                self._faults_injected += 1
            if delay_injected_ms > 0:
                self._delays_applied += 1

    def snapshot(self) -> Dict[str, Any]:
        """Calculates and returns a thread-safe summary of server performance and chaos statistics."""
        with self._lock:
            total = self._total_requests
            faults = self._faults_injected
            delays = self._delays_applied
            status_copy = dict(self._status_counts)
            durations = [r.duration_ms for r in self._records]
            uptime_sec = round(time.time() - self._start_time, 2)

        durations.sort()
        n = len(durations)

        def percentile(p: float) -> float:
            if not durations:
                return 0.0
            idx = int(p * n)
            return round(durations[min(idx, n - 1)], 2)

        return {
            "uptime_seconds": uptime_sec,
            "total_requests": total,
            "chaos_stats": {
                "faults_injected": faults,
                "delays_applied": delays,
                "fault_rate_actual": round(faults / total, 4) if total > 0 else 0.0
            },
            "status_code_distribution": status_copy,
            "latency_ms": {
                "sample_size": n,
                "min": round(durations[0], 2) if durations else 0.0,
                "p50": percentile(0.50),
                "p90": percentile(0.90),
                "p95": percentile(0.95),
                "p99": percentile(0.99),
                "max": round(durations[-1], 2) if durations else 0.0
            }
        }
