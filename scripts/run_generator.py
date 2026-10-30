# ChainC2 Sentinel — Standalone Controlled Generator CLI Launcher
"""CLI launcher for running the independent laboratory generator in an isolated process or VM.

Usage:
    python scripts/run_generator.py [--interval 25] [--single-cycle]
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import time
from pathlib import Path

# Add project root to sys.path
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from src.scenarios.generator import ControlledGenerator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("chainc2_sentinel.run_generator")


def main() -> None:
    parser = argparse.ArgumentParser(description="ChainC2 Sentinel Independent C2 Workload Generator")
    parser.add_argument("--interval", type=float, default=25.0, help="Seconds between scenario cycles")
    parser.add_argument("--single-cycle", action="store_true", help="Run a single rotation cycle and exit")
    args = parser.parse_args()

    print("=" * 70)
    print("  ChainC2 Sentinel — Independent Controlled Laboratory Generator")
    print("  Ethereum Sepolia Testnet (11155111) • Harmless Laboratory Telemetry")
    print("=" * 70)

    generator = ControlledGenerator(repo_root=repo_root, cycle_interval_seconds=args.interval)

    if args.single_cycle:
        logger.info("Executing single scenario rotation step...")
        result = generator.step_cycle()
        logger.info("Cycle outcome: %s", result)
        return

    # Handle graceful termination signals
    def _signal_handler(sig, frame):
        logger.info("Received termination signal (%s). Halting generator...", sig)
        generator.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    logger.info("Starting unattended scenario generation loop (interval=%.1fs)...", args.interval)
    generator.start()

    try:
        while generator.is_running:
            time.sleep(1.0)
    except KeyboardInterrupt:
        logger.info("Interrupted by user.")
    finally:
        generator.stop()
        logger.info("Generator stopped cleanly.")


if __name__ == "__main__":
    main()

