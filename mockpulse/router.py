"""
MockPulse - Routing and URL Matching Engine.
Zero external dependencies.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
import re
from typing import Callable, Any, Dict, Optional, Tuple, List
from urllib.parse import urlparse, parse_qs


class MatchStatus(Enum):
    MATCHED = auto()
    METHOD_NOT_ALLOWED = auto()
    NOT_FOUND = auto()


@dataclass
class RequestContext:
    """Represents an incoming parsed HTTP request."""
    method: str
    raw_path: str
    path: str
    query_params: Dict[str, List[str]]
    headers: Dict[str, str]
    body: Optional[bytes] = None
    path_params: Dict[str, str] = field(default_factory=dict)


@dataclass
class ResponseContext:
    """Represents an outgoing HTTP response."""
    status_code: int = 200
    headers: Dict[str, str] = field(default_factory=dict)
    body: Any = None  # Can be dict, str, or bytes


# Type alias for route handler function
RouteHandler = Callable[[RequestContext], ResponseContext]


@dataclass
class Route:
    method: str
    path_pattern: str
    handler: RouteHandler
    _regex: re.Pattern = field(init=False)

    def __post_init__(self):
        # Convert path pattern like '/users/{id}' to regex named group
        # e.g., '/users/(?P<id>[^/]+)'
        pattern = self.path_pattern
        regex_pattern = re.sub(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}", r"(?P<\1>[^/]+)", pattern)
        self._regex = re.compile(f"^{regex_pattern}$")

    def match(self, path: str) -> Optional[Dict[str, str]]:
        m = self._regex.match(path)
        if m:
            return m.groupdict()
        return None


class Router:
    """
    Central request dispatcher.
    Matches (method, path) to registered handlers with RFC-compliant 404/405 distinction.
    """

    def __init__(self):
        self._routes: List[Route] = []

    def add_route(self, method: str, path_pattern: str, handler: RouteHandler) -> None:
        """Register a route with an HTTP method, path pattern, and handler callable."""
        self._routes.append(Route(method=method.upper(), path_pattern=path_pattern, handler=handler))

    def get(self, path_pattern: str):
        """Decorator for GET routes."""
        def decorator(handler: RouteHandler):
            self.add_route("GET", path_pattern, handler)
            return handler
        return decorator

    def post(self, path_pattern: str):
        """Decorator for POST routes."""
        def decorator(handler: RouteHandler):
            self.add_route("POST", path_pattern, handler)
            return handler
        return decorator

    def resolve(self, method: str, path: str) -> Tuple[MatchStatus, Optional[Route], Dict[str, str], List[str]]:
        """
        Resolves an incoming request path & method.

        Returns:
            Tuple of:
            - MatchStatus (MATCHED, METHOD_NOT_ALLOWED, NOT_FOUND)
            - Matched Route (or None)
            - Extracted path parameters dict
            - List of allowed methods for this path (useful for 405 'Allow' header)
        """
        method = method.upper()
        allowed_methods_for_path = []
        path_matched_route = None
        matched_params = {}

        for route in self._routes:
            params = route.match(path)
            if params is not None:
                allowed_methods_for_path.append(route.method)
                if route.method == method:
                    return MatchStatus.MATCHED, route, params, allowed_methods_for_path
                elif path_matched_route is None:
                    path_matched_route = route
                    matched_params = params

        if allowed_methods_for_path:
            return MatchStatus.METHOD_NOT_ALLOWED, None, matched_params, allowed_methods_for_path

        return MatchStatus.NOT_FOUND, None, {}, []
