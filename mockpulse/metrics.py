"""
MockPulse - Thread-Safe In-Memory Metrics & Request History Spy.
Zero external dependencies.
"""

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
import threading
import time
from typing import Dict, List, Any, Optional


@dataclass
class RequestRecord:
    timestamp: float
    method: str
    path: str
    status_code: int
    duration_ms: float
    delay_injected_ms: float
    fault_injected: bool


@dataclass
class DetailedRequestRecord:
    id: int
    iso_time: str
    method: str
    path: str
    query_params: Dict[str, List[str]]
    headers: Dict[str, str]
    body: Optional[str]
    status_code: int
    duration_ms: float
    fault_injected: bool


class MetricsRegistry:
    """
    Thread-safe in-memory metrics storage and request verification spy.
    Provides latency percentiles, traffic distribution, and test assertion history.
    """

    def __init__(self, max_records: int = 2000, max_history: int = 500):
        self._lock = threading.Lock()
        self._max_records = max_records
        self._records = deque(maxlen=max_records)
        self._history = deque(maxlen=max_history)
        self._history_counter = 0
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
        fault_injected: bool = False,
        headers: Optional[Dict[str, str]] = None,
        query_params: Optional[Dict[str, List[str]]] = None,
        body_str: Optional[str] = None
    ) -> None:
        """Records an HTTP transaction thread-safely for both telemetry and verification history."""
        now = time.time()
        rec = RequestRecord(
            timestamp=now,
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

            # Detailed history for integration test assertion (Spying)
            # Skip logging internal /_mockpulse routes in history
            if not path.startswith("/_mockpulse"):
                self._history_counter += 1
                detail = DetailedRequestRecord(
                    id=self._history_counter,
                    iso_time=datetime.fromtimestamp(now).isoformat(),
                    method=method,
                    path=path,
                    query_params=query_params or {},
                    headers=headers or {},
                    body=body_str,
                    status_code=status_code,
                    duration_ms=round(duration_ms, 2),
                    fault_injected=fault_injected
                )
                self._history.append(detail)

    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Returns the recent captured requests for test assertion."""
        with self._lock:
            items = list(self._history)
        # Return newest first or chronological? Sliced to limit
        selected = items[-limit:] if limit > 0 else items
        return [
            {
                "id": r.id,
                "timestamp": r.iso_time,
                "method": r.method,
                "path": r.path,
                "query_params": r.query_params,
                "headers": r.headers,
                "body": r.body,
                "status_code": r.status_code,
                "duration_ms": r.duration_ms,
                "fault_injected": r.fault_injected
            }
            for r in selected
        ]

    def clear_history(self) -> None:
        """Clears the request history buffer (ideal between test runs)."""
        with self._lock:
            self._history.clear()

    def snapshot(self) -> Dict[str, Any]:
        """Calculates and returns a thread-safe summary of server performance and chaos statistics."""
        with self._lock:
            total = self._total_requests
            faults = self._faults_injected
            delays = self._delays_applied
            status_copy = dict(self._status_counts)
            durations = [r.duration_ms for r in self._records]
            history_count = len(self._history)
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
            "history_captured_count": history_count,
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
