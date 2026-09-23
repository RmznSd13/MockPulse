"""
MockPulse - Declarative Configuration & Hot-Reload Engine.
Zero external dependencies.
"""

from dataclasses import dataclass, field
import json
import os
import threading
from typing import Any, Dict, List, Optional, Tuple

from mockpulse.chaos import LatencyConfig, FaultConfig
from mockpulse.router import Router, RequestContext, ResponseContext


@dataclass
class RouteDefinition:
    method: str
    path: str
    status_code: int = 200
    headers: Dict[str, str] = field(default_factory=dict)
    response: Any = None
    latency: Optional[LatencyConfig] = None
    fault: Optional[FaultConfig] = None


class ConfigManager:
    """
    Loads, validates, and builds Routers from JSON configuration files.
    Supports atomic hot-reloading on file modification.
    """

    def __init__(self, config_path: str, hot_reload: bool = True):
        self.config_path = os.path.abspath(config_path)
        self.hot_reload_enabled = hot_reload
        self._lock = threading.Lock()
        self._last_mtime: float = 0.0
        self._router: Optional[Router] = None
        self._route_definitions: List[RouteDefinition] = []
        self._route_chaos_map: Dict[Tuple[str, str], Tuple[Optional[LatencyConfig], Optional[FaultConfig]]] = {}

        # Initial load
        self.reload_if_needed(force=True)

    @property
    def router(self) -> Router:
        with self._lock:
            return self._router

    @property
    def route_definitions(self) -> List[RouteDefinition]:
        with self._lock:
            return list(self._route_definitions)

    def get_chaos_config(self, method: str, path: str) -> Tuple[Optional[LatencyConfig], Optional[FaultConfig]]:
        """Retrieves the (latency, fault) configuration for a route, if configured."""
        with self._lock:
            # First check exact match
            key = (method.upper(), path)
            if key in self._route_chaos_map:
                return self._route_chaos_map[key]
            # Next check pattern matches
            for (m, p), chaos_pair in self._route_chaos_map.items():
                if m == method.upper():
                    # Check route match
                    # (Quick check for parameterized paths)
                    if "{" in p and self._path_matches(p, path):
                        return chaos_pair
            return None, None

    @staticmethod
    def _path_matches(pattern: str, actual: str) -> bool:
        import re
        regex = "^" + re.sub(r"\{[a-zA-Z_][a-zA-Z0-9_]*\}", r"[^/]+", pattern) + "$"
        return bool(re.match(regex, actual))

    def reload_if_needed(self, force: bool = False) -> bool:
        """
        Checks file modification timestamp. If modified or force=True,
        reloads the configuration and swaps the router atomically.
        """
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

        try:
            current_mtime = os.stat(self.config_path).st_mtime
        except OSError:
            return False

        if not force and not self.hot_reload_enabled:
            return False

        if force or current_mtime > self._last_mtime:
            return self._load_and_compile(current_mtime)

        return False

    def _load_and_compile(self, mtime: float) -> bool:
        """Parses the JSON file and atomically updates internal routing tables."""
        with open(self.config_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        new_router = Router()
        new_definitions: List[RouteDefinition] = []
        new_chaos_map: Dict[Tuple[str, str], Tuple[Optional[LatencyConfig], Optional[FaultConfig]]] = {}

        routes_data = data.get("routes", [])
        if not isinstance(routes_data, list):
            raise ValueError("'routes' key must be a list of route definitions")

        for item in routes_data:
            method = item.get("method", "GET").upper()
            path = item.get("path")
            if not path:
                continue

            status_code = int(item.get("status_code", 200))
            headers = item.get("headers", {})
            response_body = item.get("response", {})

            # Parse Latency
            latency_cfg = None
            if "latency" in item and isinstance(item["latency"], dict):
                lat = item["latency"]
                latency_cfg = LatencyConfig(
                    delay_ms=float(lat.get("delay_ms", 0)),
                    jitter_min_ms=float(lat.get("jitter_min_ms", 0)),
                    jitter_max_ms=float(lat.get("jitter_max_ms", 0))
                )

            # Parse Fault
            fault_cfg = None
            if "fault" in item and isinstance(item["fault"], dict):
                flt = item["fault"]
                fault_cfg = FaultConfig(
                    rate=float(flt.get("rate", 0)),
                    status_code=int(flt.get("status_code", 500)),
                    response=flt.get("response"),
                    headers=flt.get("headers", {})
                )

            route_def = RouteDefinition(
                method=method,
                path=path,
                status_code=status_code,
                headers=headers,
                response=response_body,
                latency=latency_cfg,
                fault=fault_cfg
            )
            new_definitions.append(route_def)
            new_chaos_map[(method, path)] = (latency_cfg, fault_cfg)

            # Create closure for handler
            def make_handler(resp_code: int, resp_headers: Dict[str, str], resp_body: Any):
                def handler(req: RequestContext) -> ResponseContext:
                    # If body is dict and contains template references, interpolate path params
                    body_copy = resp_body
                    if isinstance(resp_body, dict) and req.path_params:
                        # Simple replacement for matched path params in string values
                        body_copy = json.loads(json.dumps(resp_body))
                        for k, v in req.path_params.items():
                            for bk, bv in body_copy.items():
                                if isinstance(bv, str) and f"{{{k}}}" in bv:
                                    body_copy[bk] = bv.replace(f"{{{k}}}", v)

                    return ResponseContext(
                        status_code=resp_code,
                        headers=resp_headers,
                        body=body_copy
                    )
                return handler

            new_router.add_route(
                method=method,
                path_pattern=path,
                handler=make_handler(status_code, headers, response_body)
            )

        # Atomic swap
        with self._lock:
            self._router = new_router
            self._route_definitions = new_definitions
            self._route_chaos_map = new_chaos_map
            self._last_mtime = mtime

        return True
