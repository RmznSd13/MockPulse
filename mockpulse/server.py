"""
MockPulse - Server Bootstrap with Multi-Threaded Concurrency.
Zero external dependencies.
"""

from http.server import ThreadingHTTPServer
import sys
from typing import Optional

from mockpulse.router import Router
from mockpulse.handler import MockPulseRequestHandler
from mockpulse.metrics import MetricsRegistry
from mockpulse.logger import TerminalLogger
from mockpulse.config import ConfigManager


class MockPulseServer:
    """
    Multi-threaded HTTP Server orchestrator for MockPulse.
    Spawns an isolated thread per incoming client connection.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8080,
        router: Optional[Router] = None,
        config_manager: Optional[ConfigManager] = None,
        enable_logging: bool = True
    ):
        self.host = host
        self.port = port
        self.router = router or Router()
        self.config_manager = config_manager
        self.metrics = MetricsRegistry()
        self.logger = TerminalLogger(enabled=enable_logging)
        self._server: Optional[ThreadingHTTPServer] = None

    def start(self) -> None:
        """Starts the multi-threaded HTTP server."""
        server_address = (self.host, self.port)
        # ThreadingHTTPServer handles each request in a new thread
        self._server = ThreadingHTTPServer(server_address, MockPulseRequestHandler)

        # Attach dependencies to server instance for handler access
        self._server.router = self.router
        self._server.config_manager = self.config_manager
        self._server.metrics = self.metrics
        self._server.terminal_logger = self.logger

        routes_count = len(self.config_manager.route_definitions) if self.config_manager else len(self.router._routes)
        hot_reload = self.config_manager.hot_reload_enabled if self.config_manager else False

        self.logger.print_banner(
            host=self.host,
            port=self.port,
            routes_count=routes_count,
            hot_reload=hot_reload
        )

        try:
            self._server.serve_forever()
        except KeyboardInterrupt:
            print("\n[MockPulse] 🛑 Shutdown signal received. Closing active threads and socket...")
        finally:
            self.stop()

    def stop(self) -> None:
        """Stops and cleans up the HTTP server socket."""
        if self._server:
            self._server.server_close()
            print("[MockPulse] Server socket closed cleanly. Goodbye!")
            self._server = None
