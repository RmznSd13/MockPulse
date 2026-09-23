"""
Unit tests for MockPulse TerminalLogger.
"""

import unittest

from mockpulse.logger import TerminalLogger


class TestTerminalLogger(unittest.TestCase):

    def test_logger_badges_formatting(self):
        logger = TerminalLogger(enabled=True)

        badge_get = logger.method_badge("GET")
        self.assertIn("GET", badge_get)

        badge_post = logger.method_badge("POST")
        self.assertIn("POST", badge_post)

        status_200 = logger.status_badge(200)
        self.assertIn("200", status_200)

        status_500 = logger.status_badge(500)
        self.assertIn("500", status_500)

    def test_logger_disabled_mode(self):
        logger = TerminalLogger(enabled=False)
        # Should execute silently without exception
        logger.log_request("GET", "/health", 200, 1.2)


if __name__ == "__main__":
    unittest.main()
