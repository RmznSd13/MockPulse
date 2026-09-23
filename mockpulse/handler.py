"""
MockPulse - HTTP Request Handler Pipeline.
Bridges BaseHTTPRequestHandler with Router, ChaosEngine, Metrics, and Logger.
Provides Universal CORS and Integration Test Spying.
Zero external dependencies.
"""

from http.server import BaseHTTPRequestHandler
import json
import time
import traceback
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse, parse_qs

from mockpulse.chaos import ChaosEngine
from mockpulse.router import Router, MatchStatus, RequestContext, ResponseContext
from mockpulse.metrics import MetricsRegistry
from mockpulse.logger import TerminalLogger


class MockPulseRequestHandler(BaseHTTPRequestHandler):
    """
    Core request pipeline handler.
    Executes in a dedicated thread per connection under ThreadingHTTPServer.
    """
    server_version = "MockPulse/0.3"

    @property
    def config_manager(self):
        return getattr(self.server, "config_manager", None)

    @property
    def router(self) -> Optional[Router]:
        if self.config_manager:
            return self.config_manager.router
        return getattr(self.server, "router", None)

    @property
    def metrics(self) -> Optional[MetricsRegistry]:
        return getattr(self.server, "metrics", None)

    @property
    def logger(self) -> Optional[TerminalLogger]:
        return getattr(self.server, "terminal_logger", None)

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def do_PUT(self):
        self._dispatch("PUT")

    def do_DELETE(self):
        self._dispatch("DELETE")

    def do_PATCH(self):
        self._dispatch("PATCH")

    def do_OPTIONS(self):
        self._dispatch("OPTIONS")

    def do_HEAD(self):
        self._dispatch("HEAD")

    def _dispatch(self, method: str) -> None:
        start_time = time.perf_counter()
        delay_applied_ms = 0.0
        fault_injected = False
        status_code = 500
        headers_dict = {}
        query_params = {}
        body_str: Optional[str] = None

        try:
            # 1. Automatic Universal CORS Preflight Handling
            if method == "OPTIONS":
                self.send_response(204)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, PATCH, OPTIONS, HEAD")
                self.send_header("Access-Control-Allow-Headers", "*")
                self.send_header("Access-Control-Max-Age", "86400")
                self.send_header("Content-Length", "0")
                self.end_headers()
                status_code = 204
                return

            # 2. Hot-reload check on incoming request if configured
            if self.config_manager:
                if self.config_manager.reload_if_needed():
                    if self.logger:
                        print(f"\n[MockPulse] 🔄 Configuration change detected! Routes reloaded successfully.\n")

            # 3. URL and Header Parsing
            parsed_url = urlparse(self.path)
            path = parsed_url.path
            query_params = parse_qs(parsed_url.query)
            headers_dict = {k: v for k, v in self.headers.items()}

            # 4. Built-in MockPulse Telemetry & Spy Verification Endpoints
            if path == "/_mockpulse/metrics" and method == "GET":
                snapshot = self.metrics.snapshot() if self.metrics else {}
                resp = ResponseContext(status_code=200, body=snapshot)
                self._send_response_context(resp)
                status_code = 200
                return

            if path == "/_mockpulse/routes" and method == "GET":
                routes_info = []
                if self.config_manager:
                    for r in self.config_manager.route_definitions:
                        routes_info.append({
                            "method": r.method,
                            "path": r.path,
                            "status_code": r.status_code,
                            "latency_enabled": r.latency.is_enabled if r.latency else False,
                            "fault_enabled": r.fault.is_enabled if r.fault else False
                        })
                resp = ResponseContext(status_code=200, body={"routes": routes_info, "total": len(routes_info)})
                self._send_response_context(resp)
                status_code = 200
                return

            # Spy history endpoints for integration testing assertions
            if path == "/_mockpulse/history":
                if method == "GET":
                    history = self.metrics.get_history() if self.metrics else []
                    resp = ResponseContext(status_code=200, body={"requests": history, "total": len(history)})
                    self._send_response_context(resp)
                    status_code = 200
                    return
                elif method == "DELETE":
                    if self.metrics:
                        self.metrics.clear_history()
                    resp = ResponseContext(status_code=200, body={"status": "cleared", "message": "History buffer reset"})
                    self._send_response_context(resp)
                    status_code = 200
                    return

            # 5. Read request body if present
            body_bytes: Optional[bytes] = None
            content_length_header = self.headers.get("Content-Length")
            if content_length_header:
                try:
                    content_length = int(content_length_header)
                    body_bytes = self.rfile.read(content_length)
                    if body_bytes:
                        try:
                            body_str = body_bytes.decode("utf-8")
                        except UnicodeDecodeError:
                            body_str = f"<binary: {len(body_bytes)} bytes>"
                except (ValueError, IOError):
                    body_bytes = None

            # Build RequestContext
            request_ctx = RequestContext(
                method=method,
                raw_path=self.path,
                path=path,
                query_params=query_params,
                headers=headers_dict,
                body=body_bytes
            )

            # 6. Resolve Route in Router
            current_router = self.router
            if not current_router:
                status_code = 500
                self._send_raw_response(500, {"error": "Router not initialized on server"})
                return

            match_status, route, path_params, allowed_methods = current_router.resolve(method, path)

            if match_status == MatchStatus.NOT_FOUND:
                status_code = 404
                self._send_raw_response(
                    status_code=404,
                    body={"error": "Not Found", "path": path, "method": method}
                )
                return

            if match_status == MatchStatus.METHOD_NOT_ALLOWED:
                status_code = 405
                allowed_str = ", ".join(sorted(set(allowed_methods)))
                self._send_raw_response(
                    status_code=405,
                    headers={"Allow": allowed_str},
                    body={
                        "error": "Method Not Allowed",
                        "path": path,
                        "method": method,
                        "allowed_methods": allowed_methods
                    }
                )
                return

            # 7. Apply Chaos / Fault Injection (if configured for this route)
            if self.config_manager:
                lat_cfg, flt_cfg = self.config_manager.get_chaos_config(method, path)
                if lat_cfg or flt_cfg:
                    chaos_res = ChaosEngine.execute(lat_cfg, flt_cfg)
                    delay_applied_ms = chaos_res.delay_applied_ms
                    if chaos_res.fault_injected:
                        fault_injected = True
                        status_code = chaos_res.injected_status_code or 500
                        fault_resp = ResponseContext(
                            status_code=status_code,
                            headers=chaos_res.injected_headers,
                            body=chaos_res.injected_body
                        )
                        self._send_response_context(fault_resp)
                        return

            # 8. Execute Route Handler
            request_ctx.path_params = path_params
            resp_ctx: ResponseContext = route.handler(request_ctx)
            if not isinstance(resp_ctx, ResponseContext):
                raise TypeError(f"Handler must return ResponseContext, got {type(resp_ctx).__name__}")

            status_code = resp_ctx.status_code
            self._send_response_context(resp_ctx, is_head=(method == "HEAD"))

        except Exception as exc:
            status_code = 500
            traceback.print_exc()
            self._send_raw_response(
                status_code=500,
                body={"error": "InternalServerError", "message": str(exc), "type": exc.__class__.__name__}
            )

        finally:
            # High-precision duration calculation
            duration_ms = (time.perf_counter() - start_time) * 1000.0

            # 9. Record Telemetry Metrics and Integration Test History
            if self.metrics:
                self.metrics.record(
                    method=method,
                    path=self.path,
                    status_code=status_code,
                    duration_ms=duration_ms,
                    delay_injected_ms=delay_applied_ms,
                    fault_injected=fault_injected,
                    headers=headers_dict,
                    query_params=query_params,
                    body_str=body_str
                )

            # 10. ANSI Console Output
            if self.logger:
                self.logger.log_request(
                    method=method,
                    path=self.path,
                    status_code=status_code,
                    duration_ms=duration_ms,
                    delay_ms=delay_applied_ms,
                    fault_injected=fault_injected
                )

    def _send_response_context(self, resp: ResponseContext, is_head: bool = False) -> None:
        """Serializes and sends a ResponseContext object with automatic CORS."""
        body_bytes, content_type = self._serialize_body(resp.body)

        self.send_response(resp.status_code)

        headers = dict(resp.headers)
        # Always inject CORS header for seamless frontend/browser testing
        if "Access-Control-Allow-Origin" not in headers:
            headers["Access-Control-Allow-Origin"] = "*"

        if content_type and "Content-Type" not in headers:
            headers["Content-Type"] = content_type
        if "Content-Length" not in headers:
            headers["Content-Length"] = str(len(body_bytes))

        for header_name, header_val in headers.items():
            self.send_header(header_name, header_val)
        self.end_headers()

        if not is_head and body_bytes:
            self.wfile.write(body_bytes)

    def _send_raw_response(self, status_code: int, body: Any, headers: Optional[Dict[str, str]] = None) -> None:
        resp = ResponseContext(status_code=status_code, headers=headers or {}, body=body)
        self._send_response_context(resp)

    @staticmethod
    def _serialize_body(body: Any) -> Tuple[bytes, Optional[str]]:
        if body is None:
            return b"", None
        if isinstance(body, (dict, list)):
            return json.dumps(body, indent=2).encode("utf-8"), "application/json"
        if isinstance(body, str):
            return body.encode("utf-8"), "text/plain; charset=utf-8"
        if isinstance(body, bytes):
            return body, "application/octet-stream"
        return str(body).encode("utf-8"), "text/plain; charset=utf-8"

    def log_message(self, format: str, *args):
        """Suppress default BaseHTTPRequestHandler stderr logging in favor of TerminalLogger."""
        pass
