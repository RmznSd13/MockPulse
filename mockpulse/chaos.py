"""
MockPulse - Chaos & Fault Injection Engine.
Zero external dependencies.
"""

from dataclasses import dataclass, field
import random
import time
from typing import Any, Dict, Optional, Tuple


@dataclass
class LatencyConfig:
    """Configures artificial latency delay with optional jitter."""
    delay_ms: float = 0.0          # Fixed delay in milliseconds
    jitter_min_ms: float = 0.0     # Minimum delay if using random range
    jitter_max_ms: float = 0.0     # Maximum delay if using random range

    @property
    def is_enabled(self) -> bool:
        return self.delay_ms > 0 or (self.jitter_max_ms > self.jitter_min_ms and self.jitter_max_ms > 0)

    def calculate_delay_ms(self) -> float:
        """Computes the target delay in milliseconds based on fixed or jitter configuration."""
        if self.jitter_max_ms > self.jitter_min_ms and self.jitter_max_ms > 0:
            return random.uniform(self.jitter_min_ms, self.jitter_max_ms)
        return max(0.0, self.delay_ms)


@dataclass
class FaultConfig:
    """Configures probabilistic failure injection (e.g. 20% chance of 503)."""
    rate: float = 0.0              # 0.0 to 1.0 (e.g. 0.2 = 20% failure probability)
    status_code: int = 500         # HTTP status code to inject upon fault
    response: Any = None           # Custom response body for the fault
    headers: Dict[str, str] = field(default_factory=dict)

    @property
    def is_enabled(self) -> bool:
        return self.rate > 0.0

    def should_fault(self) -> bool:
        """Determines probabilistically whether this request should fail."""
        if not self.is_enabled:
            return False
        return random.random() < self.rate


@dataclass
class ChaosExecutionResult:
    """Summary of chaos actions applied to a request."""
    delay_applied_ms: float = 0.0
    fault_injected: bool = False
    injected_status_code: Optional[int] = None
    injected_body: Any = None
    injected_headers: Dict[str, str] = field(default_factory=dict)


class ChaosEngine:
    """
    Evaluates and applies latency delays and fault injections.
    Thread-safe and deterministic when seeded.
    """

    @staticmethod
    def execute(latency_cfg: Optional[LatencyConfig], fault_cfg: Optional[FaultConfig]) -> ChaosExecutionResult:
        result = ChaosExecutionResult()

        # 1. Apply Latency Simulation
        if latency_cfg and latency_cfg.is_enabled:
            target_delay_ms = latency_cfg.calculate_delay_ms()
            if target_delay_ms > 0:
                time.sleep(target_delay_ms / 1000.0)
                result.delay_applied_ms = target_delay_ms

        # 2. Apply Fault Injection
        if fault_cfg and fault_cfg.is_enabled:
            if fault_cfg.should_fault():
                result.fault_injected = True
                result.injected_status_code = fault_cfg.status_code
                result.injected_body = fault_cfg.response or {
                    "error": "FaultInjected",
                    "status": fault_cfg.status_code,
                    "message": "Chaos fault injection triggered by MockPulse",
                    "injected_rate": fault_cfg.rate
                }
                result.injected_headers = dict(fault_cfg.headers)

        return result
