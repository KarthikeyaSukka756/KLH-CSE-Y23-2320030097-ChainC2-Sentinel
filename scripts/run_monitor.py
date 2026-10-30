# ChainC2 Sentinel — Standalone Sepolia Monitor CLI Launcher
"""CLI launcher for running the unattended continuous Sepolia monitor and detector daemon.

Usage:
    python scripts/run_monitor.py [--interval 15] [--poll-once]
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import time
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from src.blockchain.monitor import SepoliaMonitor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("chainc2_sentinel.run_monitor")


def main() -> None:
    parser = argparse.ArgumentParser(description="ChainC2 Sentinel Unattended Sepolia Monitor Daemon")
    parser.add_argument("--interval", type=float, default=15.0, help="Seconds between Sepolia poll cycles")
    parser.add_argument("--poll-once", action="store_true", help="Poll latest block once and exit")
    args = parser.parse_args()

    print("=" * 70)
    print("  ChainC2 Sentinel — Continuous Sepolia Monitor & Detector Daemon")
    print("  Ethereum Sepolia Testnet (11155111) • Autonomous Defensive Mitigation")
    print("=" * 70)

    monitor = SepoliaMonitor.get_instance(repo_root=repo_root)
    status = monitor.check_connection()
    logger.info("Connection status: %s | Chain ID: %s | Block: %s", status["connection_status"], status["chain_id"], status["latest_block"])

    if args.poll_once:
        txs = monitor.poll_latest_blocks(block_count=1)
        logger.info("Polled %d transactions in single cycle.", len(txs))
        return

    def _signal_handler(sig, frame):
        logger.info("Received termination signal (%s). Halting monitor...", sig)
        monitor.stop_continuous_monitoring()
        sys.exit(0)

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    logger.info("Starting continuous monitor loop (interval=%.1fs)...", args.interval)
    monitor.start_continuous_monitoring(poll_interval_seconds=args.interval)

    try:
        while monitor.monitoring_active:
            time.sleep(1.0)
    except KeyboardInterrupt:
        logger.info("Interrupted by user.")
    finally:
        monitor.stop_continuous_monitoring()
        logger.info("Monitor stopped cleanly.")


if __name__ == "__main__":
    main()

