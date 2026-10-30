# ChainC2 Sentinel — Zoho Catalyst Cron Function Entrypoint
"""Executed on automated schedule by Zoho Catalyst Cron service."""

import logging
import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(root_dir))

from src.cloudscale.cron_handler import catalyst_cron_handler

logger = logging.getLogger("chainc2_sentinel.cloudscale.cron_entry")


def handler(cron_details: dict = None, context: dict = None) -> dict:
    """Zoho Catalyst Cron handler signature."""
    logger.info("Executing scheduled Sepolia observation and autonomous C2 experiment cycle...")
    return catalyst_cron_handler(event_data=cron_details, context=context)

