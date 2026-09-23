"""
Unit tests for MockPulse Router.
"""

import unittest
from mockpulse.router import Router, MatchStatus, RequestContext, ResponseContext


class TestMockPulseRouter(unittest.TestCase):

    def setUp(self):
        self.router = Router()

    def test_exact_route_matching(self):
        @self.router.get("/health")
        def health_check(req: RequestContext) -> ResponseContext:
            return ResponseContext(status_code=200, body={"status": "UP"})

        status, route, params, allowed = self.router.resolve("GET", "/health")
        self.assertEqual(status, MatchStatus.MATCHED)
        self.assertEqual(params, {})
        resp = route.handler(RequestContext("GET", "/health", "/health", {}, {}))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.body, {"status": "UP"})

    def test_parameterized_route_matching(self):
        @self.router.get("/api/v1/users/{id}")
        def get_user(req: RequestContext) -> ResponseContext:
            return ResponseContext(status_code=200, body=req.path_params)

        status, route, params, allowed = self.router.resolve("GET", "/api/v1/users/42")
        self.assertEqual(status, MatchStatus.MATCHED)
        self.assertEqual(params, {"id": "42"})

    def test_rfc_405_method_not_allowed(self):
        @self.router.get("/metrics")
        def metrics(req: RequestContext) -> ResponseContext:
            return ResponseContext(status_code=200, body="ok")

        status, route, params, allowed = self.router.resolve("POST", "/metrics")
        self.assertEqual(status, MatchStatus.METHOD_NOT_ALLOWED)
        self.assertIsNone(route)
        self.assertIn("GET", allowed)

    def test_rfc_404_not_found(self):
        status, route, params, allowed = self.router.resolve("GET", "/undefined-path")
        self.assertEqual(status, MatchStatus.NOT_FOUND)
        self.assertIsNone(route)


if __name__ == "__main__":
    unittest.main()
