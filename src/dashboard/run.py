# ChainC2 Sentinel — Master Dashboard CLI Entry Point
"""Runs the local Master Dashboard server on 127.0.0.1."""

import argparse
import logging
import sys

from src.dashboard.app import create_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("chainc2_sentinel.dashboard")


def main() -> None:
    parser = argparse.ArgumentParser(description="ChainC2 Sentinel Master Dashboard Server")
    parser.add_argument("--host", default="127.0.0.1", help="Binding host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5000, help="Binding port (default: 5000)")
    parser.add_argument("--debug", action="store_true", help="Enable Flask debug mode")
    args = parser.parse_args()

    # Safety enforcement: strictly restrict default binding to localhost
    if args.host != "127.0.0.1" and args.host != "localhost":
        logger.warning(
            "Binding to non-localhost address '%s'. Laboratory safety recommends 127.0.0.1.",
            args.host,
        )

    app = create_app()

    print("=" * 70)
    print("  ChainC2 Sentinel — Master Research Dashboard")
    print("  Cybersecurity Framework for Blockchain-Mediated C2 Detection")
    print("=" * 70)
    print(f"  Local Address: http://{args.host}:{args.port}")
    print("  Environment:   Controlled Laboratory (Offline/Localhost)")
    print("  Phases:        Phase 1 — Detection | Phase 2 — Protection")
    print("=" * 70)
    print("  Press CTRL+C to stop the dashboard server.")
    print("=" * 70)

    try:
        app.run(host=args.host, port=args.port, debug=args.debug)
    except KeyboardInterrupt:
        print("\nStopping ChainC2 Sentinel Master Dashboard...")
        sys.exit(0)


if __name__ == "__main__":
    main()
