#!/usr/bin/env python3
"""Launch the Nevis Meeting Analyzer web interface.

Usage:
    python scripts/run_web.py
    python scripts/run_web.py --port 8080
    python scripts/run_web.py --test  # Use test/mock data
"""

import argparse
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()


def main():
    parser = argparse.ArgumentParser(description="Run Nevis Meeting Analyzer Web UI")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=5000, help="Port to bind to")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--test", action="store_true", help="Use test database")

    args = parser.parse_args()

    if args.test:
        os.environ["NEVIS_TEST_MODE"] = "1"

    from nevis.web.app import run_app

    print(f"""
    ================================================
    Nevis Meeting Analyzer
    ================================================

    Starting web interface...

    Open your browser to: http://{args.host}:{args.port}

    Press Ctrl+C to stop the server.
    ================================================
    """)

    run_app(host=args.host, port=args.port, debug=args.debug or True)


if __name__ == "__main__":
    main()
