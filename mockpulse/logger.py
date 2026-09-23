"""
MockPulse - ANSI Terminal Logger & Visual Monitor.
Zero external dependencies.
"""

from datetime import datetime
import os
import sys
from typing import Optional


class ANSI:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Foreground
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    GRAY = "\033[90m"

    # Background
    BG_RED = "\033[41m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"


class TerminalLogger:
    """
    Colorized terminal logger for HTTP requests and Chaos events.
    Respects NO_COLOR standard.
    """

    def __init__(self, enabled: bool = True):
        # Disable ANSI if NO_COLOR environment variable exists or not a tty
        self.no_color = "NO_COLOR" in os.environ or not sys.stdout.isatty()
        self.enabled = enabled

    def _c(self, text: str, color_code: str) -> str:
        if self.no_color:
            return text
        return f"{color_code}{text}{ANSI.RESET}"

    def method_badge(self, method: str) -> str:
        method = method.upper()
        colors = {
            "GET": ANSI.CYAN,
            "POST": ANSI.GREEN,
            "PUT": ANSI.YELLOW,
            "DELETE": ANSI.RED,
            "PATCH": ANSI.MAGENTA,
            "OPTIONS": ANSI.BLUE,
            "HEAD": ANSI.GRAY
        }
        color = colors.get(method, ANSI.WHITE)
        return self._c(f"{method:<6}", ANSI.BOLD + color)

    def status_badge(self, status: int) -> str:
        status_str = f" {status} "
        if 200 <= status < 300:
            return self._c(status_str, ANSI.GREEN)
        if 300 <= status < 400:
            return self._c(status_str, ANSI.CYAN)
        if 400 <= status < 500:
            return self._c(status_str, ANSI.YELLOW)
        return self._c(status_str, ANSI.RED + ANSI.BOLD)

    def log_request(
        self,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
        delay_ms: float = 0.0,
        fault_injected: bool = False
    ) -> None:
        """Logs a single HTTP request transaction."""
        if not self.enabled:
            return

        now = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        time_tag = self._c(f"[{now}]", ANSI.GRAY)
        method_str = self.method_badge(method)
        path_str = self._c(f"{path:<30}", ANSI.BOLD)
        status_str = self.status_badge(status_code)
        duration_str = self._c(f"{duration_ms:>6.1f}ms", ANSI.DIM)

        tags = []
        if delay_ms > 0:
            tags.append(self._c(f"[⏱️  +{delay_ms:.0f}ms delay]", ANSI.YELLOW))
        if fault_injected:
            tags.append(self._c(f"[💥 FAULT INJECTED]", ANSI.RED + ANSI.BOLD))

        extra_info = " ".join(tags)
        print(f"{time_tag} {method_str} {path_str} -> {status_str} in {duration_str} {extra_info}".strip())

    def print_banner(self, host: str, port: int, routes_count: int, hot_reload: bool) -> None:
        """Prints the visual MockPulse startup banner."""
        b_cyan = lambda s: self._c(s, ANSI.BOLD + ANSI.CYAN)
        b_green = lambda s: self._c(s, ANSI.BOLD + ANSI.GREEN)
        b_yellow = lambda s: self._c(s, ANSI.BOLD + ANSI.YELLOW)
        gray = lambda s: self._c(s, ANSI.GRAY)

        print("\n" + gray("═" * 70))
        print(f" {b_cyan('⚡ MockPulse')} {b_green('v0.2.0')} - {gray('Zero-Dependency API Mock & Chaos Engine')}")
        print(gray("─" * 70))
        print(f"  {gray('•')} {b_cyan('Address:')}    http://{host}:{port}")
        print(f"  {gray('•')} {b_cyan('Routes:')}     {b_green(str(routes_count))} active endpoints loaded")
        print(f"  {gray('•')} {b_cyan('Engine:')}     ThreadingHTTPServer (Thread-per-request Concurrency)")
        print(f"  {gray('•')} {b_cyan('Telemetry:')}  http://{host}:{port}/_mockpulse/metrics")
        print(f"  {gray('•')} {b_cyan('Hot-Reload:')} {b_green('Enabled') if hot_reload else b_yellow('Disabled')}")
        print(gray("─" * 70))
        print(f"  {gray('Ready for requests. Press Ctrl+C to terminate.')}")
        print(gray("═" * 70) + "\n")
