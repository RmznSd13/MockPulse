"""
MockPulse - Zero-Dependency Local API Mocking & Fault Injection Engine.
Staff Engineer Portfolio Project.
"""

import argparse
import os
import sys

from mockpulse.config import ConfigManager
from mockpulse.server import MockPulseServer


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="⚡ MockPulse: Zero-Dependency Local API Mocking & Chaos Fault Injection Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 main.py
  python3 main.py --port 9000 --config routes.json
  python3 main.py --host 0.0.0.0 --port 8080 --no-hot-reload
        """
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host address to bind the HTTP socket to (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="TCP port to listen on (default: 8080)"
    )
    parser.add_argument(
        "--config",
        type=str,
        default="routes.json",
        help="Path to routes configuration JSON file (default: routes.json)"
    )
    parser.add_argument(
        "--no-hot-reload",
        action="store_true",
        help="Disable automatic filesystem watcher / hot-reloading of routes.json"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-request ANSI console logging"
    )
    return parser


def main():
    parser = build_arg_parser()
    args = parser.parse_args()

    config_path = os.path.abspath(args.config)
    if not os.path.exists(config_path):
        print(f"❌ Error: Config file not found at '{config_path}'", file=sys.stderr)
        sys.exit(1)

    try:
        config_manager = ConfigManager(
            config_path=config_path,
            hot_reload=not args.no_hot_reload
        )
    except Exception as exc:
        print(f"❌ Configuration Error: Failed to parse '{config_path}': {exc}", file=sys.stderr)
        sys.exit(1)

    server = MockPulseServer(
        host=args.host,
        port=args.port,
        config_manager=config_manager,
        enable_logging=not args.quiet
    )

    server.start()


if __name__ == "__main__":
    main()
