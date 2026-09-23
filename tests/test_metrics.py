"""
Unit tests for MockPulse MetricsRegistry and Thread-Safety.
"""

import threading
import unittest

from mockpulse.metrics import MetricsRegistry


class TestMetricsRegistry(unittest.TestCase):

    def test_metrics_recording_and_percentiles(self):
        registry = MetricsRegistry(max_records=100)

        # Record deterministic latencies: 10ms, 20ms, 30ms, ... 100ms
        for i in range(1, 101):
            registry.record(
                method="GET",
                path="/test",
                status_code=200 if i <= 90 else 500,
                duration_ms=float(i),
                delay_injected_ms=5.0 if i % 2 == 0 else 0.0,
                fault_injected=True if i > 90 else False
            )

        snapshot = registry.snapshot()
        self.assertEqual(snapshot["total_requests"], 100)
        self.assertEqual(snapshot["status_code_distribution"][200], 90)
        self.assertEqual(snapshot["status_code_distribution"][500], 10)
        self.assertEqual(snapshot["chaos_stats"]["faults_injected"], 10)
        self.assertEqual(snapshot["chaos_stats"]["delays_applied"], 50)
        self.assertEqual(snapshot["chaos_stats"]["fault_rate_actual"], 0.10)

        # Percentiles check
        lat = snapshot["latency_ms"]
        self.assertEqual(lat["min"], 1.0)
        self.assertEqual(lat["max"], 100.0)
        self.assertEqual(lat["p50"], 51.0)
        self.assertEqual(lat["p95"], 96.0)

    def test_concurrent_recording_thread_safety(self):
        registry = MetricsRegistry(max_records=1000)
        num_threads = 10
        records_per_thread = 50

        def worker():
            for _ in range(records_per_thread):
                registry.record("POST", "/concurrent", 201, 12.5)

        threads = [threading.Thread(target=worker) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        snapshot = registry.snapshot()
        self.assertEqual(snapshot["total_requests"], num_threads * records_per_thread)

    def test_request_history_spy(self):
        registry = MetricsRegistry(max_records=100, max_history=50)

        # Record requests
        registry.record(
            method="POST",
            path="/api/v1/orders",
            status_code=201,
            duration_ms=45.2,
            headers={"Content-Type": "application/json"},
            query_params={"source": ["mobile"]},
            body_str='{"order_id": 99}'
        )

        history = registry.get_history()
        self.assertEqual(len(history), 1)
        item = history[0]
        self.assertEqual(item["method"], "POST")
        self.assertEqual(item["path"], "/api/v1/orders")
        self.assertEqual(item["status_code"], 201)
        self.assertEqual(item["headers"]["Content-Type"], "application/json")
        self.assertEqual(item["query_params"]["source"], ["mobile"])
        self.assertEqual(item["body"], '{"order_id": 99}')

        # Clear history
        registry.clear_history()
        self.assertEqual(len(registry.get_history()), 0)


if __name__ == "__main__":
    unittest.main()
