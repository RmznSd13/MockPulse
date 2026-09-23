"""
Unit tests for MockPulse Universal CORS Preflight Handling.
"""

from io import BytesIO
import unittest
from unittest.mock import MagicMock

from mockpulse.handler import MockPulseRequestHandler
from mockpulse.router import Router, RequestContext, ResponseContext


class TestMockPulseCORS(unittest.TestCase):

    def test_options_preflight_response(self):
        # Create a mock server
        mock_server = MagicMock()
        mock_server.router = Router()
        mock_server.metrics = None
        mock_server.config_manager = None
        mock_server.terminal_logger = None

        # Instantiate handler with mock socket
        handler = MockPulseRequestHandler.__new__(MockPulseRequestHandler)
        handler.server = mock_server
        handler.headers = {"Origin": "http://localhost:3000"}
        handler.path = "/api/v1/payments/charge"
        handler.rfile = BytesIO(b"")
        handler.wfile = BytesIO()

        # Mock send_response, send_header, end_headers
        headers_sent = {}
        status_sent = []

        def fake_send_response(code):
            status_sent.append(code)

        def fake_send_header(k, v):
            headers_sent[k] = v

        handler.send_response = fake_send_response
        handler.send_header = fake_send_header
        handler.end_headers = MagicMock()

        handler.do_OPTIONS()

        self.assertEqual(status_sent, [204])
        self.assertEqual(headers_sent.get("Access-Control-Allow-Origin"), "*")
        self.assertIn("POST", headers_sent.get("Access-Control-Allow-Methods", ""))
        self.assertEqual(headers_sent.get("Access-Control-Max-Age"), "86400")


if __name__ == "__main__":
    unittest.main()
