"""
Unit tests for MockPulse Chaos & Fault Injection Engine.
"""

import random
import time
import unittest

from mockpulse.chaos import LatencyConfig, FaultConfig, ChaosEngine


class TestChaosEngine(unittest.TestCase):

    def test_fixed_latency_calculation(self):
        cfg = LatencyConfig(delay_ms=150.0)
        self.assertTrue(cfg.is_enabled)
        self.assertEqual(cfg.calculate_delay_ms(), 150.0)

    def test_jitter_latency_range(self):
        cfg = LatencyConfig(jitter_min_ms=100.0, jitter_max_ms=200.0)
        self.assertTrue(cfg.is_enabled)
        for _ in range(50):
            val = cfg.calculate_delay_ms()
            self.assertGreaterEqual(val, 100.0)
            self.assertLessEqual(val, 200.0)

    def test_fault_rate_statistical_distribution(self):
        # Using a fixed seed for reproducible statistical assertions
        random.seed(42)
        target_rate = 0.30
        cfg = FaultConfig(rate=target_rate, status_code=503)
        self.assertTrue(cfg.is_enabled)

        iterations = 2000
        fault_count = sum(1 for _ in range(iterations) if cfg.should_fault())
        actual_rate = fault_count / iterations

        # Margin of error for binomial distribution with n=2000, p=0.3 is ~0.03
        self.assertAlmostEqual(actual_rate, target_rate, delta=0.035)

    def test_deterministic_full_fault_injection(self):
        cfg = FaultConfig(
            rate=1.0,
            status_code=503,
            response={"error": "Down"},
            headers={"Retry-After": "5"}
        )
        res = ChaosEngine.execute(latency_cfg=None, fault_cfg=cfg)
        self.assertTrue(res.fault_injected)
        self.assertEqual(res.injected_status_code, 503)
        self.assertEqual(res.injected_body, {"error": "Down"})
        self.assertEqual(res.injected_headers, {"Retry-After": "5"})

    def test_zero_fault_when_disabled(self):
        cfg = FaultConfig(rate=0.0)
        self.assertFalse(cfg.is_enabled)
        res = ChaosEngine.execute(latency_cfg=None, fault_cfg=cfg)
        self.assertFalse(res.fault_injected)


if __name__ == "__main__":
    unittest.main()
