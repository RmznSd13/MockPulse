"""
Unit tests for MockPulse ConfigManager and Hot-Reloading.
"""

import json
import os
import tempfile
import time
import unittest

from mockpulse.config import ConfigManager
from mockpulse.router import MatchStatus, RequestContext


class TestConfigManager(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = os.path.join(self.temp_dir.name, "test_routes.json")

    def tearDown(self):
        self.temp_dir.cleanup()

    def _write_config(self, data):
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(data, f)

    def test_load_basic_routes(self):
        self._write_config({
            "routes": [
                {
                    "method": "GET",
                    "path": "/api/test",
                    "status_code": 200,
                    "response": {"message": "hello"}
                },
                {
                    "method": "POST",
                    "path": "/api/items",
                    "status_code": 201,
                    "response": {"status": "created"}
                }
            ]
        })

        mgr = ConfigManager(self.config_path, hot_reload=True)
        self.assertEqual(len(mgr.route_definitions), 2)

        # Verify GET route
        status, route, params, allowed = mgr.router.resolve("GET", "/api/test")
        self.assertEqual(status, MatchStatus.MATCHED)
        resp = route.handler(RequestContext("GET", "/api/test", "/api/test", {}, {}))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.body, {"message": "hello"})

        # Verify POST route
        status, route, params, allowed = mgr.router.resolve("POST", "/api/items")
        self.assertEqual(status, MatchStatus.MATCHED)
        resp = route.handler(RequestContext("POST", "/api/items", "/api/items", {}, {}))
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.body, {"status": "created"})

    def test_parameter_template_interpolation(self):
        self._write_config({
            "routes": [
                {
                    "method": "GET",
                    "path": "/users/{user_id}",
                    "status_code": 200,
                    "response": {"id": "{user_id}", "profile": "user_{user_id}"}
                }
            ]
        })

        mgr = ConfigManager(self.config_path)
        status, route, params, allowed = mgr.router.resolve("GET", "/users/usr_456")
        self.assertEqual(status, MatchStatus.MATCHED)
        self.assertEqual(params, {"user_id": "usr_456"})

        req = RequestContext("GET", "/users/usr_456", "/users/usr_456", {}, {}, path_params=params)
        resp = route.handler(req)
        self.assertEqual(resp.body["id"], "usr_456")
        self.assertEqual(resp.body["profile"], "user_usr_456")

    def test_hot_reloading(self):
        self._write_config({
            "routes": [
                {"method": "GET", "path": "/v1", "response": {"version": 1}}
            ]
        })

        mgr = ConfigManager(self.config_path, hot_reload=True)
        self.assertEqual(len(mgr.route_definitions), 1)

        # Update file with new route and altered mtime
        time.sleep(0.05)
        self._write_config({
            "routes": [
                {"method": "GET", "path": "/v1", "response": {"version": 1}},
                {"method": "GET", "path": "/v2", "response": {"version": 2}}
            ]
        })
        # Explicitly ensure mtime changes
        os.utime(self.config_path, (time.time() + 1, time.time() + 1))

        reloaded = mgr.reload_if_needed()
        self.assertTrue(reloaded)
        self.assertEqual(len(mgr.route_definitions), 2)

        status, route, _, _ = mgr.router.resolve("GET", "/v2")
        self.assertEqual(status, MatchStatus.MATCHED)


if __name__ == "__main__":
    unittest.main()
